"""Synthesize node factory — generate the final answer.

Parameterized by the ``AgentSpec`` so each agent gets its own system prompt.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.harness.agent_spec import AgentSpec

logger = logging.getLogger(__name__)


def make_synthesize_node(spec: AgentSpec) -> Any:
    """Create a synthesize node for the given agent spec.

    Uses the agent's system prompt as the synthesis base.  Builds a
    context-aware user message from the state.

    Args:
        spec: AgentSpec containing the system prompt.

    Returns:
        An async callable ``(state) -> partial_state_update``.
    """
    base_prompt = spec.system_prompt

    synthesis_instruction = (
        "\n\nGenerate a clear, accurate final answer based on the "
        "context and tool results provided. Base your answer only "
        "on the available information. Do not hallucinate."
    )

    async def synthesize_node(state: dict[str, Any]) -> dict[str, Any]:
        from app.agents.state import StepRecord
        from app.llm.base import Message
        from app.llm.factory import get_llm_provider

        start = time.monotonic()
        iteration = state.get("iteration", 0)

        system_content = base_prompt + synthesis_instruction
        user_message = _build_synthesis_prompt(state)

        llm = get_llm_provider()
        llm_messages = [
            Message(role="system", content=system_content),
            Message(role="user", content=user_message),
        ]

        try:
            response = await llm.chat(
                messages=llm_messages,
                model=spec.model.model_name,
                max_tokens=spec.model.max_tokens,
                temperature=spec.model.temperature,
            )
            final_answer = response.content
            prompt_tokens = response.input_tokens
            completion_tokens = response.output_tokens
        except Exception as e:
            logger.error("synthesize_node LLM call failed: %s", e)
            final_answer = f"I encountered an error while generating the answer: {e}"
            prompt_tokens = 0
            completion_tokens = 0

        elapsed_ms = int((time.monotonic() - start) * 1000)

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
                step_type="synthesize",
                iteration=iteration,
                input_summary=f"context docs count",
                output_summary=final_answer[:200],
                duration_ms=elapsed_ms,
                tokens_used=prompt_tokens + completion_tokens,
            )
        )

        logger.info(
            "synthesize_node(%s): generated answer (%d chars) iteration=%d",
            spec.name,
            len(final_answer),
            iteration,
        )

        return {
            "final_answer": final_answer,
            "current_step": "synthesize",
            "metadata": {**state.get("metadata", {}), **cost_update},
            "steps": steps,
        }

    return synthesize_node


def _build_synthesis_prompt(state: dict[str, Any]) -> str:
    """Build the user message for synthesis from state context."""
    parts = []

    user_query = ""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, dict) and msg.get("role") == "user":
            user_query = msg.get("content", "")
            break
    parts.append(f"User Query: {user_query}")

    # Check both context.documents and legacy documents field
    context = state.get("context", {})
    docs = context.get("documents", []) or state.get("documents", [])
    if docs:
        parts.append("\n--- Retrieved Context ---")
        for i, doc in enumerate(docs[:10], 1):
            text = doc.get("text", "")[:500]
            doc_id = doc.get("document_id", "unknown")
            page = doc.get("page", "?")
            parts.append(f"[Chunk {i}] (doc={doc_id}, page={page}): {text}")

    tool_results = state.get("tool_results", [])
    if tool_results:
        parts.append("\n--- Tool Results ---")
        for tr in tool_results:
            tool_name = tr["tool_name"]
            args = tr["arguments"]
            output = tr["output"]
            error = tr.get("error")
            if error:
                parts.append(f"Tool '{tool_name}'({args}): ERROR - {error}")
            else:
                parts.append(f"Tool '{tool_name}'({args}): {str(output)[:500]}")

    return "\n".join(parts)
