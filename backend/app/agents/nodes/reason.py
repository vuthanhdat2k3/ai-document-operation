"""Reason node — LLM decides whether to call a tool or synthesize."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.agents.state import AgentState, StepRecord

logger = logging.getLogger(__name__)


REASON_SYSTEM_PROMPT = """You are an AI document operations agent. Given the user query and retrieved context, decide the next action.

Available tools:
{tools}

You must respond with a JSON object in one of two formats:

1. To call a tool:
{{"action": "tool_call", "tool_name": "<name>", "arguments": {{...}}}}

2. To generate the final answer:
{{"action": "synthesize", "reasoning": "<why no more tools are needed>"}}

Rules:
- Only use tools that are listed above.
- If you have enough information to answer, choose "synthesize".
- Do not call the same tool with the same arguments more than once.
- Keep tool arguments minimal and focused.
"""


def _build_tools_description(state: AgentState) -> str:
    """Build a description of available tools for the LLM prompt."""
    try:
        from app.agents.tools.registry import get_registry

        registry = get_registry()
        tools = registry.list_tools()
        if not tools:
            return "(no tools available)"
        lines = []
        for t in tools:
            schema_info = ""
            if t.input_schema is not None:
                schema = t.input_schema.model_json_schema()
                props = schema.get("properties", {})
                required = schema.get("required", [])
                params = []
                for pname, pdef in props.items():
                    req = " (required)" if pname in required else " (optional)"
                    params.append(f"    - {pname}: {pdef.get('type', 'any')}{req}")
                if params:
                    schema_info = "\n" + "\n".join(params)
            lines.append(f"- {t.name}: {t.description}{schema_info}")
        return "\n".join(lines)
    except Exception as e:
        logger.error("Failed to build tools description: %s", e)
        return "(tool listing failed)"


def _build_context_summary(state: AgentState) -> str:
    """Build a summary of retrieved documents and past tool results."""
    parts = []

    docs = state.get("documents", [])
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


def _call_llm(system_prompt: str, user_message: str) -> dict[str, Any]:
    """Call the LLM and parse the JSON response.

    Falls back to synthesize if the LLM is unavailable or returns
    unparseable output.
    """
    try:
        from openai import OpenAI

        from app.config import get_settings

        settings = get_settings()
        if not settings.OPENAI_API_KEY:
            logger.warning("reason_node: OPENAI_API_KEY not set, defaulting to synthesize")
            return {"action": "synthesize", "reasoning": "LLM unavailable (no API key)"}

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=settings.DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.0,
            max_tokens=1024,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)

        usage = response.usage
        return {
            "action": parsed.get("action", "synthesize"),
            "tool_name": parsed.get("tool_name"),
            "arguments": parsed.get("arguments", {}),
            "reasoning": parsed.get("reasoning", ""),
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "completion_tokens": usage.completion_tokens if usage else 0,
        }
    except ImportError:
        logger.warning("reason_node: openai package not installed, defaulting to synthesize")
        return {"action": "synthesize", "reasoning": "LLM unavailable (openai not installed)"}
    except Exception as e:
        logger.error("reason_node LLM call failed: %s", e)
        return {"action": "synthesize", "reasoning": f"LLM error: {e}"}


async def reason_node(state: AgentState) -> dict[str, Any]:
    """Reason about the next action based on retrieved context.

    Uses the LLM to decide whether to call a tool or proceed to synthesis.
    If no LLM is available, defaults to synthesis.

    Args:
        state: Current agent state.

    Returns:
        Partial state update with ``current_step``, ``pending_tool``,
        ``metadata``, and an appended ``steps`` record.
    """
    start = time.monotonic()
    iteration = state.get("iteration", 0)
    messages = state.get("messages", [])

    tools_desc = _build_tools_description(state)
    system_prompt = REASON_SYSTEM_PROMPT.format(tools=tools_desc)

    context = _build_context_summary(state)
    user_query = ""
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "user":
            user_query = msg.get("content", "")
            break

    user_message = f"Query: {user_query}\n\n{context}"

    llm_result = _call_llm(system_prompt, user_message)
    elapsed_ms = int((time.monotonic() - start) * 1000)

    action = llm_result.get("action", "synthesize")
    pending_tool = None

    if action == "tool_call" and llm_result.get("tool_name"):
        pending_tool = {
            "name": llm_result["tool_name"],
            "arguments": llm_result.get("arguments", {}),
        }
        logger.info(
            "reason_node: decided to call tool=%s iteration=%d",
            llm_result["tool_name"],
            iteration,
        )
    else:
        logger.info("reason_node: decided to synthesize iteration=%d", iteration)

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
