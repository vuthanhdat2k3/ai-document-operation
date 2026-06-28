"""Reason node factory — LLM decides whether to call a tool or synthesize.

Parameterized by the ``AgentSpec`` so each agent gets its own system prompt
and tool list.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.harness.agent_spec import AgentSpec

logger = logging.getLogger(__name__)


def make_reason_node(spec: AgentSpec) -> Any:
    """Create a reason node for the given agent spec.

    The node calls the LLM with the agent's system prompt (including
    available tools) and decides whether to invoke a tool or synthesise.

    Args:
        spec: AgentSpec containing system prompt and tool list.

    Returns:
        An async callable ``(state) -> partial_state_update``.
    """
    system_prompt = spec.system_prompt

    async def reason_node(state: dict[str, Any]) -> dict[str, Any]:
        start = time.monotonic()
        iteration = state.get("iteration", 0)
        messages = state.get("messages", [])

        # Build tools description
        tools_desc = _build_tools_description(spec)
        filled_prompt = system_prompt.format(tools=tools_desc)

        # Build context from state
        context = _build_context_summary(state)
        user_query = ""
        for msg in reversed(messages):
            if isinstance(msg, dict) and msg.get("role") == "user":
                user_query = msg.get("content", "")
                break

        user_message = f"Query: {user_query}\n\n{context}"

        llm_result = await _call_llm(filled_prompt, user_message, spec)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        action = llm_result.get("action", "synthesize")
        pending_tool = None

        if action == "tool_call" and llm_result.get("tool_name"):
            pending_tool = {
                "name": llm_result["tool_name"],
                "arguments": llm_result.get("arguments", {}),
            }
            logger.info(
                "reason_node(%s): decided to call tool=%s iteration=%d",
                spec.name,
                llm_result["tool_name"],
                iteration,
            )
        else:
            logger.info("reason_node(%s): decided to synthesize iteration=%d", spec.name, iteration)

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
                step_type="reason",
                iteration=iteration,
                input_summary=f"query={user_query[:100]}",
                output_summary=f"action={action}"
                + (f" tool={llm_result.get('tool_name', '')}" if action == "tool_call" else ""),
                duration_ms=elapsed_ms,
                tokens_used=prompt_tokens + completion_tokens,
            )
        )

        metadata = {**state.get("metadata", {}), **cost_update}

        return {
            "current_step": "reason",
            "pending_tool": pending_tool,
            "metadata": metadata,
            "steps": steps,
        }

    return reason_node


def _build_tools_description(spec: AgentSpec) -> str:
    """Build a description of available tools for the LLM prompt."""
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


def _build_context_summary(state: dict[str, Any]) -> str:
    """Build a summary of retrieved documents and past tool results."""
    parts = []

    # Check both context.documents and legacy documents field
    context = state.get("context", {})
    docs = context.get("documents", []) or state.get("documents", [])
    if docs:
        parts.append("Retrieved context:")
        for i, doc in enumerate(docs[:5], 1):
            text = doc.get("text", "")[:300]
            score = doc.get("score", 0)
            parts.append(f"  [{i}] (score={score:.3f}) {text}")
        if len(docs) > 5:
            parts.append(f"  ... and {len(docs) - 5} more chunks")

    tool_results = state.get("tool_results", [])
    if tool_results:
        parts.append("\nPrevious tool results:")
        for tr in tool_results:
            parts.append(f"  - {tr['tool_name']}({tr['arguments']}): {str(tr['output'])[:200]}")

    return "\n".join(parts) if parts else "(no context available)"


async def _call_llm(system_prompt: str, user_message: str, spec: AgentSpec) -> dict[str, Any]:
    """Call the LLM via the provider abstraction and parse the JSON response.

    Uses ``get_llm_provider()`` so the agent can work with OpenAI, Anthropic,
    Xiaomi, or local models — whatever ``LLM_PROVIDER`` is configured to.

    Falls back to synthesize if the LLM is unavailable or returns
    unparseable output.
    """
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
            max_tokens=1024,
            temperature=0.0,
        )

        content = response.content or "{}"
        parsed = json.loads(content)

        return {
            "action": parsed.get("action", "synthesize"),
            "tool_name": parsed.get("tool_name"),
            "arguments": parsed.get("arguments", {}),
            "reasoning": parsed.get("reasoning", ""),
            "prompt_tokens": response.input_tokens or 0,
            "completion_tokens": response.output_tokens or 0,
        }
    except json.JSONDecodeError:
        logger.warning("reason_node: failed to parse LLM JSON response, defaulting to synthesize")
        return {"action": "synthesize", "reasoning": "LLM response parse error"}
    except Exception as e:
        logger.error("reason_node LLM call failed: %s", e)
        return {"action": "synthesize", "reasoning": f"LLM error: {e}"}
