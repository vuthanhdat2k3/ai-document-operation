"""Retrieve node — performs hybrid search based on the user query."""

from __future__ import annotations

import logging
import time
from typing import Any

from app.agents.state import AgentState, StepRecord

logger = logging.getLogger(__name__)


def _extract_query(state: AgentState) -> str:
    """Extract the search query from the latest user message."""
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str) and content.strip():
                return content.strip()
    return ""


async def retrieve_node(state: AgentState) -> dict[str, Any]:
    """Retrieve relevant documents using hybrid search.

    Extracts the user query from messages, executes a search via the
    tool registry's ``search_documents`` tool, and updates state with
    the retrieved chunks.

    Args:
        state: Current agent state.

    Returns:
        Partial state update with ``documents``, ``current_step``,
        and an appended ``steps`` record.
    """
    start = time.monotonic()
    iteration = state.get("iteration", 0)
    query = _extract_query(state)

    if not query:
        logger.warning("retrieve_node: no user query found in messages")
        return {
            "documents": [],
            "current_step": "retrieve",
            "steps": state.get("steps", [])
            + [
                StepRecord(
                    step_type="retrieve",
                    iteration=iteration,
                    input_summary="no query found",
                    output_summary="0 documents",
                    duration_ms=0,
                )
            ],
        }

    documents: list[dict[str, Any]] = []
    try:
        from app.agents.tools.registry import get_registry

        registry = get_registry()
        if registry.has("search_documents"):
            entry = registry.get("search_documents")
            result = await entry.function(query=query, top_k=10)
            if isinstance(result, dict):
                documents = result.get("results", [])
            elif isinstance(result, list):
                documents = result
        else:
            logger.warning("retrieve_node: search_documents tool not registered")
    except Exception as e:
        logger.error("retrieve_node search failed: %s", e)

    elapsed_ms = int((time.monotonic() - start) * 1000)
    logger.info(
        "retrieve_node: query=%r docs=%d iteration=%d elapsed=%dms",
        query[:80],
        len(documents),
        iteration,
        elapsed_ms,
    )

    steps = list(state.get("steps", []))
    steps.append(
        StepRecord(
            step_type="retrieve",
            iteration=iteration,
            input_summary=query[:200],
            output_summary=f"{len(documents)} documents retrieved",
            duration_ms=elapsed_ms,
        )
    )

    return {
        "documents": documents,
        "current_step": "retrieve",
        "steps": steps,
    }
