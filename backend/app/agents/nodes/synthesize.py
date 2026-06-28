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
- Luôn trả lời bằng tiếng Việt.
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

    Uses ``get_llm_provider_from_db`` to respect the user's model selection,
    falling back to env vars or extractive synthesis if unavailable.

    Refuses to answer when no documents or tool results are available, to
    prevent hallucination.

    Args:
        state: Current agent state with documents and tool results.

    Returns:
        Partial state update with ``final_answer``, ``current_step``,
        updated ``metadata``, and appended ``steps``.
    """
    from app.llm.base import Message
    from app.llm.factory import get_llm_provider_from_db

    start = time.monotonic()
    iteration = state.get("iteration", 0)
    agent_name = state.get("metadata", {}).get("agent_name", "doc-qa")

    docs = state.get("documents", [])
    tool_results = state.get("tool_results", [])
    plan = state.get("plan", [])

    # Guard: refuse to hallucinate when the planner expected document context
    # but nothing was found.  If the plan is empty, the LLM classified the
    # query as general chat / greeting — respond naturally without guard.
    if plan and not docs and not tool_results:
        final_answer = (
            "Xin lỗi, tôi không tìm thấy tài liệu nào phù hợp với câu hỏi của bạn. "
            "Vui lòng tải lên tài liệu trước hoặc thử lại với câu hỏi khác."
        )
        prompt_tokens = 0
        completion_tokens = 0
        logger.info("synthesize_node: plan existed but no context — refused to hallucinate")
    elif not plan and not docs and not tool_results:
        # Empty plan = general chat/greeting — use LLM to respond naturally,
        # fallback to a friendly message if LLM unavailable.
        prompt_tokens = 0
        completion_tokens = 0
        try:
            llm = await get_llm_provider_from_db(agent_name=agent_name)
        except Exception:
            llm = None
        if llm is not None:
            try:
                response = await llm.chat(
                    messages=[
                        Message(role="system", content="You are a helpful assistant. Answer the user's question naturally and concisely in Vietnamese."),
                        Message(role="user", content=state.get("messages", [{}])[-1].get("content", "") if isinstance(state.get("messages", [{}])[-1], dict) else ""),
                    ],
                    temperature=0.0,
                    max_tokens=512,
                )
                final_answer = response.content
                prompt_tokens = response.input_tokens
                completion_tokens = response.output_tokens
            except Exception as e:
                logger.error("synthesize_node greeting LLM failed: %s", e)
                final_answer = "Xin chào! Tôi có thể giúp gì cho bạn?"
        else:
            logger.warning("synthesize_node: no LLM provider, using generic greeting")
            final_answer = "Xin chào! Tôi có thể giúp gì cho bạn?"
    else:
        user_message = _build_synthesis_prompt(state)

        prompt_tokens = 0
        completion_tokens = 0

        try:
            llm = await get_llm_provider_from_db(agent_name=agent_name)
        except Exception:
            llm = None

        if llm is not None:
            try:
                response = await llm.chat(
                    messages=[
                        Message(role="system", content=SYNTHESIZE_SYSTEM_PROMPT),
                        Message(role="user", content=user_message),
                    ],
                    temperature=0.0,
                    max_tokens=2048,
                )
                final_answer = response.content
                prompt_tokens = response.input_tokens
                completion_tokens = response.output_tokens
            except Exception as e:
                logger.error("synthesize_node LLM call failed: %s", e)
                result = _fallback_synthesis(user_message)
                final_answer = result["answer"]
                prompt_tokens = result.get("prompt_tokens", 0)
                completion_tokens = result.get("completion_tokens", 0)
        else:
            logger.warning("synthesize_node: no LLM provider, using fallback synthesis")
            result = _fallback_synthesis(user_message)
            final_answer = result["answer"]

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
