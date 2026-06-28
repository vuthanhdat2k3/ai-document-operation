"""Plan node — LLM generates a structured step-by-step plan before execution.

The plan node is invoked when the ``AgentSpec`` has a ``planner_prompt``
configured.  It asks the LLM to decompose the user query into a sequence of
tool calls or reasoning steps, then stores the plan in the agent state.

After planning, the agent executes each step sequentially via the reason →
tool_call → synthesize loop.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.harness.agent_spec import AgentSpec

logger = logging.getLogger(__name__)


def make_plan_node(spec: AgentSpec) -> Any:
    """Create a plan node for the given agent spec.

    Args:
        spec: AgentSpec with optional ``planner_prompt``.

    Returns:
        An async callable ``(state) -> partial_state_update``, or ``None``
        if the spec has no planner_prompt configured.
    """
    planner_prompt = spec.planner_prompt
    if not planner_prompt:
        return None

    async def plan_node(state: dict[str, Any]) -> dict[str, Any]:
        start = time.monotonic()
        messages = state.get("messages", [])

        # Find the user query
        user_query = ""
        for msg in reversed(messages):
            if isinstance(msg, dict) and msg.get("role") == "user":
                user_query = msg.get("content", "")
                break

        # Build tools description for the planner
        tools_desc = _build_tools_description(spec)
        filled_prompt = planner_prompt.format(tools=tools_desc)
        user_message = f"User query: {user_query}"

        llm_result = await _call_llm(filled_prompt, user_message, spec)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        plan = llm_result.get("plan", [])
        if not isinstance(plan, list):
            logger.warning("plan_node: LLM did not return a valid plan")
            plan = []

        # Log plan
        if plan:
            steps_desc = "; ".join(
                f"step {s.get('step', i+1)}: {s.get('tool', 'reason')}"
                for i, s in enumerate(plan)
            )
            logger.info("plan_node(%s): created plan — %s", spec.name, steps_desc)
        else:
            logger.info("plan_node(%s): empty plan — proceeding directly", spec.name)

        # Track plan cost
        cost_update: dict[str, Any] = {}
        prompt_tokens = llm_result.get("prompt_tokens", 0)
        completion_tokens = llm_result.get("completion_tokens", 0)
        if prompt_tokens or completion_tokens:
            existing_cost = state.get("metadata", {}).get("cost", {})
            cost_update = {
                "cost": {
                    "prompt_tokens": existing_cost.get("prompt_tokens", 0) + prompt_tokens,
                    "completion_tokens": existing_cost.get("completion_tokens", 0) + completion_tokens,
                    "total_tokens": existing_cost.get("total_tokens", 0)
                    + prompt_tokens
                    + completion_tokens,
                }
            }

        from app.agents.state import StepRecord

        steps = list(state.get("steps", []))
        steps.append(
            StepRecord(
                step_type="plan",
                iteration=0,
                input_summary=f"query={user_query[:100]}",
                output_summary=f"plan_steps={len(plan)}"
                + (f" [{steps_desc[:100]}]" if plan else ""),
                duration_ms=elapsed_ms,
                tokens_used=prompt_tokens + completion_tokens,
            )
        )

        metadata = {**state.get("metadata", {}), **cost_update}

        return {
            "current_step": "plan",
            "plan": plan,
            "plan_index": 0,
            "metadata": metadata,
            "steps": steps,
        }

    return plan_node


def _build_tools_description(spec: AgentSpec) -> str:
    """Build a description of available tools for the LLM."""
    if not spec.tools:
        return "(no tools available)"
    try:
        from app.agents.tools.registry import get_registry

        registry = get_registry()
        lines = []
        for tool_name in spec.tools:
            try:
                entry = registry.get(tool_name)
                schema_info = ""
                if entry.input_schema is not None:
                    schema = entry.input_schema.model_json_schema()
                    props = schema.get("properties", {})
                    required = schema.get("required", [])
                    params = []
                    for pname, pdef in props.items():
                        req = " (required)" if pname in required else " (optional)"
                        params.append(f"    - {pname}: {pdef.get('type', 'any')}{req}")
                    if params:
                        schema_info = "\n" + "\n".join(params)
                lines.append(f"- {entry.name}: {entry.description}{schema_info}")
            except Exception:
                lines.append(f"- {tool_name}: (unavailable)")
        return "\n".join(lines)
    except Exception as e:
        logger.error("Failed to build tools description: %s", e)
        return "(tool listing failed)"


async def _call_llm(system_prompt: str, user_message: str, spec: AgentSpec) -> dict[str, Any]:
    """Call the LLM and parse the JSON response."""
    try:
        from app.llm.base import Message
        from app.llm.factory import get_llm_provider, get_llm_provider_from_db

        try:
            provider = await get_llm_provider_from_db(agent_name=spec.name)
        except Exception:
            provider = get_llm_provider()
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_message),
        ]
        response = await provider.chat(
            messages=messages,
            model=None,
            max_tokens=2048,
            temperature=0.0,
        )
        content = response.content or "{}"
        parsed = json.loads(content)

        return {
            "plan": parsed.get("plan", []),
            "prompt_tokens": response.input_tokens or 0,
            "completion_tokens": response.output_tokens or 0,
        }
    except json.JSONDecodeError:
        logger.warning("plan_node: failed to parse LLM JSON response, using empty plan")
        return {"plan": []}
    except Exception as e:
        logger.error("plan_node LLM call failed: %s", e)
        return {"plan": []}
