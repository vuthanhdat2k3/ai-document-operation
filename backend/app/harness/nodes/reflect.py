"""Reflect node — self-healing retry when a tool call fails.

When a tool call returns an error, the reflect node asks the LLM to analyse
the failure and decide how to recover:

1. **Fix arguments** — retry the same tool with corrected arguments.
2. **Try another tool** — use a different tool to achieve the same goal.
3. **Skip / synthesise** — proceed to answer with what is already known.

The reflect node updates ``pending_tool`` so the graph loop retries with
corrected values, or sets ``current_step = "synthesize"`` to bail out.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.harness.agent_spec import AgentSpec

logger = logging.getLogger(__name__)

REFLECT_SYSTEM_PROMPT = """A tool call just failed. Analyse the error and decide how to recover.

Available tools:
{tools}

The failed tool call was:
  Tool: {tool_name}
  Arguments: {arguments}
  Error: {error}

Respond with a JSON object in one of these formats:

1. Retry with corrected arguments:
  {{"action": "retry", "tool_name": "{tool_name}", "arguments": {{...}}, "reasoning": "..."}}

2. Try a different tool:
  {{"action": "retry", "tool_name": "<other_tool>", "arguments": {{...}}, "reasoning": "..."}}

3. Give up and synthesise with what is available:
  {{"action": "synthesize", "reasoning": "..."}}

Rules:
- If the error is a bad argument, fix it and retry (option 1).
- If the tool is fundamentally wrong for this task, try another (option 2).
- If you already have enough information, synthesise (option 3).
- Maximum retries per tool: 2.
"""


def make_reflect_node(spec: AgentSpec) -> Any:
    """Create a reflect node for the given agent spec.

    Args:
        spec: AgentSpec containing system prompt and tool list.

    Returns:
        An async callable ``(state) -> partial_state_update``.
    """

    async def reflect_node(state: dict[str, Any]) -> dict[str, Any]:
        start = time.monotonic()

        # Get the failed tool call info from state
        pending_tool = state.get("pending_tool") or {}
        tool_error = state.get("tool_error", "")
        tool_name = pending_tool.get("name", "")
        arguments = pending_tool.get("arguments", {})
        retry_count = state.get("retry_count", 0)

        # Build tools description
        tools_desc = _build_tools_description(spec)
        prompt = REFLECT_SYSTEM_PROMPT.format(
            tools=tools_desc,
            tool_name=tool_name,
            arguments=json.dumps(arguments, indent=2),
            error=tool_error,
        )

        # Add max retry context
        max_retries = spec.guardrails.max_tool_repeats or 2
        if retry_count >= max_retries:
            logger.warning(
                "reflect_node(%s): max retries (%d) reached for tool %s, synthesizing",
                spec.name, max_retries, tool_name,
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)

            from app.agents.state import StepRecord

            steps = list(state.get("steps", []))
            steps.append(
                StepRecord(
                    step_type="reflect",
                    iteration=state.get("iteration", 0),
                    input_summary=f"tool={tool_name} error={tool_error[:100]}",
                    output_summary="max_retries_reached -> synthesize",
                    duration_ms=elapsed_ms,
                )
            )

            return {
                "current_step": "synthesize",
                "pending_tool": None,
                "retry_count": retry_count + 1,
                "tool_error": "",
                "steps": steps,
            }

        user_message = (
            f"Tool call failed after {retry_count} retries.\n"
            "Analyse and decide how to recover."
        )

        llm_result = await _call_llm(prompt, user_message, spec)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        action = llm_result.get("action", "synthesize")
        new_pending_tool = None
        should_synthesize = False

        if action == "retry" and llm_result.get("tool_name"):
            new_pending_tool = {
                "name": llm_result["tool_name"],
                "arguments": llm_result.get("arguments", {}),
            }
            logger.info(
                "reflect_node(%s): retrying tool=%s (retry %d)",
                spec.name, llm_result["tool_name"], retry_count + 1,
            )
        else:
            should_synthesize = True
            logger.info(
                "reflect_node(%s): giving up on tool=%s, synthesizing",
                spec.name, tool_name,
            )

        # Cost tracking
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
                step_type="reflect",
                iteration=state.get("iteration", 0),
                input_summary=f"tool={tool_name} error={tool_error[:100]}",
                output_summary=f"action={action}"
                + (f" retry={llm_result.get('tool_name', '')}" if action == "retry" else ""),
                duration_ms=elapsed_ms,
                tokens_used=prompt_tokens + completion_tokens,
            )
        )

        metadata = {**state.get("metadata", {}), **cost_update}

        update: dict[str, Any] = {
            "metadata": metadata,
            "steps": steps,
            "retry_count": retry_count + 1,
            "tool_error": "",
        }

        if should_synthesize:
            update["current_step"] = "synthesize"
            update["pending_tool"] = None
        else:
            update["pending_tool"] = new_pending_tool
            update["current_step"] = "tool_call"

        return update

    return reflect_node


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
        from app.llm.factory import get_llm_provider

        provider = get_llm_provider()
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_message),
        ]
        response = await provider.chat(
            messages=messages,
            model=spec.model.model_name,
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
        logger.warning("reflect_node: failed to parse LLM JSON, defaulting to synthesize")
        return {"action": "synthesize", "reasoning": "LLM parse error"}
    except Exception as e:
        logger.error("reflect_node LLM call failed: %s", e)
        return {"action": "synthesize", "reasoning": f"LLM error: {e}"}
