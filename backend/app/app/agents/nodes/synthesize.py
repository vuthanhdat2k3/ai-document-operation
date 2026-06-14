"""Synthesize node — generate the final answer from accumulated context."""

from __future__ import annotations

import logging
import time
from typing import Any

from app.agents.state import AgentState, StepRecord

logger = logging.getLogger(__name__)

SYNTHESIZE_SYSTEM_PROMPT = """You are an AI document operations assistant. Generate a clear, accurate answer based on the provided context and tool results.

Rules:
- Base your answer only on the provided context. Do not hallucinate.
- If the context is insufficient, state what information is missing.
- Cite specific documents or chunks when possible.
- Keep the answer concise and directly addressing the user's query.
"""


def _build_synthesis_prompt(state: AgentState) -> str:
    """Build the user message for synthesis from state context."""
    parts = []

    user_query = ""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, dict) and msg.get("role") == "user":
            user_query = msg.get("content", "")
            break
    parts.append(f"User Query: {user_query}")

    docs = state.get("documents", [])
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


def _call_llm_synthesize(system_prompt: str, user_message: str) -> dict[str, Any]:
    """Call the LLM to generate the final synthesized answer."""
    try:
        from openai import OpenAI

        from app.config import get_settings

        settings = get_settings()
        if not settings.OPENAI_API_KEY:
            logger.warning("synthesize_node: OPENAI_API_KEY not set")
            return {
                "answer": "Unable to generate answer: LLM service unavailable.",
                "prompt_tokens": 0,
                "completion_tokens": 0,
            }

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=settings.DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.0,
            max_tokens=2048,
        )
        content = response.choices[0].message.content or ""
        usage = response.usage
        return {
            "answer": content.strip(),
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "completion_tokens": usage.completion_tokens if usage else 0,
        }
    except ImportError:
        logger.warning("synthesize_node: openai package not installed")
        return _fallback_synthesis(user_message)
    except Exception as e:
        logger.error("synthesize_node LLM call failed: %s", e)
        return _fallback_synthesis(user_message)


def _fallback_synthesis(user_message: str) -> dict[str, Any]:
    """Generate a simple extractive answer when the LLM is unavailable.

    Returns the top retrieved chunks as a naive answer.
    """
    lines = user_message.split("\n")
    context_lines = []
    in_context = False
    for line in lines:
        if "--- Retrieved Context ---" in line:
            in_context = True
            continue
        if "--- Tool Results ---" in line:
            in_context = False
            continue
        if in_context and line.strip():
            context_lines.append(line.strip())

    if context_lines:
        answer = "Based on the retrieved documents:\n\n" + "\n".join(context_lines[:5])
    else:
        answer = "I was unable to find relevant information to answer your query."

    return {"answer": answer, "prompt_tokens": 0, "completion_tokens": 0}


async def synthesize_node(state: AgentState) -> dict[str, Any]:
    """Generate the final answer from accumulated context and tool results.

    If an LLM is available, uses it to produce a coherent answer.
    Otherwise falls back to extractive synthesis from retrieved chunks.

    Args:
        state: Current agent state with documents and tool results.

    Returns:
        Partial state update with ``final_answer``, ``current_step``,
        updated ``metadata``, and appended ``steps``.
    """
    start = time.monotonic()
    iteration = state.get("iteration", 0)

    user_message = _build_synthesis_prompt(state)
    result = _call_llm_synthesize(SYNTHESIZE_SYSTEM_PROMPT, user_message)

    final_answer = result["answer"]
    elapsed_ms = int((time.monotonic() - start) * 1000)

    prompt_tokens = result.get("prompt_tokens", 0)
    completion_tokens = result.get("completion_tokens", 0)

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
            input_summary=f"context={len(state.get('documents', []))} docs, {len(state.get('tool_results', []))} tool results",
            output_summary=final_answer[:200],
            duration_ms=elapsed_ms,
            tokens_used=prompt_tokens + completion_tokens,
        )
    )

    logger.info("synthesize_node: generated answer (%d chars) iteration=%d", len(final_answer), iteration)

    return {
        "final_answer": final_answer,
        "current_step": "synthesize",
        "metadata": {**state.get("metadata", {}), **cost_update},
        "steps": steps,
    }
