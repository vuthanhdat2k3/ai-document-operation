"""Multi-agent orchestration — Router, Chain, and Parallel patterns.

Built on top of AgentSpec, AgentRegistry, and delegation tools.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from app.harness.agent_spec import AgentSpec

logger = logging.getLogger(__name__)


# ── shared result types ─────────────────────────────────────────────────


@dataclass
class StepResult:
    """Result from a single agent execution step."""

    agent_name: str
    query: str
    answer: str
    session_id: str = ""
    iterations: int = 0
    status: str = "completed"
    error: str | None = None
    cost: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChainResult:
    """Result from a multi-agent chain or parallel execution."""

    steps: list[StepResult]
    final_answer: str
    total_iterations: int = 0
    total_cost: dict[str, Any] = field(default_factory=dict)


# ── MultiAgentRouter ────────────────────────────────────────────────────

# Default routing rules: keyword → agent name
DEFAULT_ROUTING_RULES: dict[str, str] = {
    "summarise": "summarise",
    "summarize": "summarise",
    "summary": "summarise",
    "chat": "chat",
    "qa": "doc-qa",
    "question": "doc-qa",
    "extract": "doc-extract",
}


class MultiAgentRouter:
    """Classify and route requests to the best-fit agent.

    Uses a lightweight LLM call for classification when available,
    or keyword-based routing as fallback.

    Args:
        rules: Optional custom routing rules (keyword → agent_name).
    """

    def __init__(self, rules: dict[str, str] | None = None) -> None:
        self._rules = {**DEFAULT_ROUTING_RULES, **(rules or {})}

    async def route(
        self,
        query: str,
        available_agents: list[AgentSpec] | None = None,
    ) -> str:
        """Determine the best agent for a given query.

        Args:
            query: The user's query.
            available_agents: Optional list of agents to restrict routing to.
                If None, all registered agents are considered.

        Returns:
            Name of the selected agent.
        """
        from app.harness.agent_registry import get_agent_registry

        registry = get_agent_registry()
        agents = available_agents or registry.list_agents()

        # Fast path: keyword match
        query_lower = query.lower().strip()
        for keyword, agent_name in self._rules.items():
            if keyword in query_lower:
                if any(a.name == agent_name for a in agents):
                    logger.info(
                        "Router: matched keyword '%s' → agent '%s'", keyword, agent_name
                    )
                    return agent_name

        # LLM classification path
        try:
            return await self._classify_with_llm(query, agents)
        except Exception:
            logger.warning("Router: LLM classification failed, using default")

        # Fallback: return first available non-chat agent, or chat
        for a in agents:
            if a.name != "chat":
                return a.name
        return agents[0].name if agents else "chat"

    async def _classify_with_llm(
        self, query: str, agents: list[AgentSpec]
    ) -> str:
        """Use an LLM to classify which agent should handle the query."""
        agent_list = "\n".join(
            f"  - {a.name}: {a.description[:200]}"
            for a in agents
        )
        prompt = (
            "You are a routing classifier. Given the user's query and the\n"
            "available agents, choose the SINGLE best agent to handle it.\n\n"
            f"Available agents:\n{agent_list}\n\n"
            f"User query: {query}\n\n"
            "Respond with a JSON object:\n"
            '  {{"agent": "<agent_name>", "reasoning": "<one-line reason>"}}\n\n'
            "Choose the agent whose description best matches the query intent."
        )

        try:
            from openai import OpenAI

            from app.config import get_settings

            settings = get_settings()
            if not settings.OPENAI_API_KEY:
                raise RuntimeError("No API key")

            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=200,
                response_format={"type": "json_object"},
            )
            import json

            content = response.choices[0].message.content or "{}"
            parsed = json.loads(content)
            agent_name = parsed.get("agent", "")

            # Verify the agent exists
            if any(a.name == agent_name for a in agents):
                logger.info(
                    "Router: LLM classified '%s' → agent '%s'",
                    query[:80],
                    agent_name,
                )
                return agent_name
        except Exception:
            logger.warning("Router: LLM classification error, falling back")

        raise RuntimeError("Classification failed")


# ── AgentChain ──────────────────────────────────────────────────────────


class AgentChain:
    """Execute a sequence of agents in order (pipeline).

    Each agent receives the previous agent's answer as context.
    The final agent's answer becomes the chain result.

    Args:
        agent_names: Ordered list of agent names to execute.
        description: Optional human-readable description of this chain.
    """

    def __init__(
        self,
        agent_names: list[str],
        description: str = "",
    ) -> None:
        self.agent_names = agent_names
        self.description = description or " → ".join(agent_names)

    async def run(
        self,
        query: str,
        user_id: Any = None,
    ) -> ChainResult:
        """Execute the chain sequentially.

        Args:
            query: Initial query for the first agent.
            user_id: Optional user ID for session tracking.

        Returns:
            ChainResult with all step results and the final answer.
        """
        from app.db.session import get_async_session
        from app.services.agent_service import AgentService

        steps: list[StepResult] = []
        current_context: dict[str, Any] = {}
        current_query = query

        for i, agent_name in enumerate(self.agent_names):
            logger.info(
                "Chain[%d/%d]: executing agent='%s'", i + 1, len(self.agent_names), agent_name
            )

            input_data: dict[str, Any] = {
                "query": current_query,
                "messages": [{"role": "user", "content": current_query}],
            }
            if current_context:
                input_data["context"] = dict(current_context)
                input_data["context"]["previous_step_result"] = steps[-1].answer if steps else ""

            try:
                async with get_async_session() as db:
                    service = AgentService()
                    result = await service.run_agent(
                        agent_name=agent_name,
                        input_data=input_data,
                        db=db,
                        user_id=user_id,
                    )

                step_result = StepResult(
                    agent_name=agent_name,
                    query=current_query,
                    answer=result.answer,
                    session_id=result.session_id,
                    iterations=result.iterations,
                    status=result.status,
                    cost=result.cost,
                )
                steps.append(step_result)

                # Pass the answer to the next agent
                current_query = result.answer
                current_context["previous_agent"] = agent_name

            except Exception as e:
                logger.exception("Chain[%d/%d]: agent '%s' failed", i + 1, len(self.agent_names), agent_name)
                error_result = StepResult(
                    agent_name=agent_name,
                    query=current_query,
                    answer="",
                    status="failed",
                    error=str(e),
                )
                steps.append(error_result)
                break

        total_iter = sum(s.iterations for s in steps)
        total_cost = {
            "total_tokens": sum(s.cost.get("total_tokens", 0) for s in steps),
            "steps": [{"agent": s.agent_name, "tokens": s.cost.get("total_tokens", 0)} for s in steps],
        }

        final = steps[-1].answer if steps else "Chain produced no output"
        return ChainResult(
            steps=steps,
            final_answer=final,
            total_iterations=total_iter,
            total_cost=total_cost,
        )


# ── ParallelAgentGroup ──────────────────────────────────────────────────


class ParallelAgentGroup:
    """Execute multiple agents in parallel and aggregate results.

    Args:
        agent_names: List of agent names to run concurrently.
        description: Optional description.
    """

    def __init__(
        self,
        agent_names: list[str],
        description: str = "",
    ) -> None:
        self.agent_names = agent_names
        self.description = description or f"parallel({', '.join(agent_names)})"

    async def run(
        self,
        query: str,
        user_id: Any = None,
    ) -> ChainResult:
        """Execute all agents concurrently.

        Each agent receives the same query but can process it independently.
        Results are aggregated into a single answer.

        Args:
            query: Query to send to all agents.
            user_id: Optional user ID for session tracking.

        Returns:
            ChainResult with all step results and an aggregated answer.
        """
        from app.db.session import get_async_session
        from app.services.agent_service import AgentService

        async def _run_single(agent_name: str) -> StepResult:
            input_data: dict[str, Any] = {
                "query": query,
                "messages": [{"role": "user", "content": query}],
            }
            try:
                async with get_async_session() as db:
                    service = AgentService()
                    result = await service.run_agent(
                        agent_name=agent_name,
                        input_data=input_data,
                        db=db,
                        user_id=user_id,
                    )
                return StepResult(
                    agent_name=agent_name,
                    query=query,
                    answer=result.answer,
                    session_id=result.session_id,
                    iterations=result.iterations,
                    status=result.status,
                    cost=result.cost,
                )
            except Exception as e:
                logger.exception("Parallel: agent '%s' failed", agent_name)
                return StepResult(
                    agent_name=agent_name,
                    query=query,
                    answer="",
                    status="failed",
                    error=str(e),
                )

        tasks = [_run_single(name) for name in self.agent_names]
        results = await asyncio.gather(*tasks)
        steps = list(results)

        total_iter = sum(s.iterations for s in steps)
        total_cost = {
            "total_tokens": sum(s.cost.get("total_tokens", 0) for s in steps),
            "steps": [{"agent": s.agent_name, "tokens": s.cost.get("total_tokens", 0)} for s in steps],
        }

        # Aggregate: combine all successful answers
        successful = [s for s in steps if s.status == "completed" and s.answer]
        if successful:
            parts = [f"## Results from {s.agent_name}\n\n{s.answer}" for s in successful]
            final = "\n\n---\n\n".join(parts)
        else:
            final = "All agents failed to produce a result."

        return ChainResult(
            steps=steps,
            final_answer=final,
            total_iterations=total_iter,
            total_cost=total_cost,
        )
