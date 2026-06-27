"""delegate_to_agent tool — lets one agent invoke another agent.

Registered in ToolRegistry so the agent LLM can call it like any other tool.
Supports both direct (sync stub) and async (bound) usage.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from app.agents.tools.registry import get_registry

logger = logging.getLogger(__name__)

registry = get_registry()


class DelegateToAgentInput(BaseModel):
    """Input schema for the delegate_to_agent tool."""

    agent_name: str = Field(
        ..., description="Name of the target agent to invoke (e.g. 'doc-qa', 'chat', 'summarise')"
    )
    query: str = Field(
        ..., description="The query or task to delegate to the target agent", min_length=1
    )
    context: dict[str, Any] | None = Field(
        None, description="Optional context to pass to the target agent"
    )


@registry.register(
    name="delegate_to_agent",
    description=(
        "Delegate a task to another registered agent. Use when the current task "
        "requires a different specialty — for example, delegate summarisation to "
        "the 'summarise' agent or document Q&A to the 'doc-qa' agent. "
        "Returns the target agent's answer as a string."
    ),
    input_schema=DelegateToAgentInput,
    output_example={
        "agent_name": "doc-qa",
        "query": "What contracts expire next month?",
        "answer": "Three contracts expire in the next 30 days...",
        "session_id": "uuid-of-sub-session",
        "iterations": 3,
    },
)
async def delegate_to_agent(
    agent_name: str,
    query: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Delegate a task to another registered agent.

    This is a self-contained async tool that:
    1. Looks up the target agent in AgentRegistry.
    2. Opens a new DB session.
    3. Calls service.run_agent() and returns the result.

    Args:
        agent_name: Target agent name.
        query: Task query.
        context: Optional context dict.

    Returns:
        Dict with the target agent's answer and metadata.
    """
    from app.db.session import get_async_session
    from app.harness.agent_registry import get_agent_registry
    from app.services.agent_service import AgentService

    # Verify the target agent exists
    try:
        registry = get_agent_registry()
        registry.get(agent_name)
    except LookupError:
        return {
            "error": f"Agent '{agent_name}' not found in registry",
            "agent_name": agent_name,
        }

    logger.info(
        "delegate_to_agent: delegating to '%s' query='%s'",
        agent_name,
        query[:100],
    )

    input_data: dict[str, Any] = {
        "query": query,
        "messages": [{"role": "user", "content": query}],
    }
    if context:
        input_data["context"] = context

    try:
        async with get_async_session() as db:
            service = AgentService()
            result = await service.run_agent(
                agent_name=agent_name,
                input_data=input_data,
                db=db,
            )

            return {
                "agent_name": agent_name,
                "query": query,
                "answer": result.answer,
                "session_id": result.session_id,
                "iterations": result.iterations,
                "status": result.status,
                "cost": result.cost,
            }
    except Exception as e:
        logger.exception("delegate_to_agent: execution failed for '%s'", agent_name)
        return {
            "error": str(e),
            "agent_name": agent_name,
            "query": query,
        }
