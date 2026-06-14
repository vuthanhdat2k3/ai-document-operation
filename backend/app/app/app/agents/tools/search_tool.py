"""Search documents tool for the agent registry."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from app.agents.tools.registry import get_registry

logger = logging.getLogger(__name__)

registry = get_registry()


class SearchDocumentsInput(BaseModel):
    """Input schema for the search_documents tool."""

    query: str = Field(..., description="Natural language search query", min_length=1)
    top_k: int = Field(10, description="Maximum number of results to return", ge=1, le=100)


class SearchDocumentsOutput(BaseModel):
    """Output schema for the search_documents tool."""

    results: list[dict[str, Any]]
    total: int


def _search_documents_sync(query: str, top_k: int = 10) -> dict[str, Any]:
    """Synchronous search fallback used when no async context is available.

    In production, the agent service passes a pre-bound async search function
    via the tool's closure. This standalone version returns an empty result
    to prevent crashes when the tool is invoked without a retriever.
    """
    logger.warning("search_documents called without a bound retriever; returning empty results")
    return {"results": [], "total": 0}


@registry.register(
    name="search_documents",
    description=(
        "Search the document corpus using hybrid (dense + sparse) retrieval. "
        "Returns relevant text chunks with metadata including document_id, "
        "page number, and relevance score."
    ),
    input_schema=SearchDocumentsInput,
    output_example={
        "results": [
            {
                "chunk_id": "abc123",
                "document_id": "doc-uuid",
                "text": "Relevant text chunk...",
                "score": 0.87,
                "page": 3,
            }
        ],
        "total": 1,
    },
)
def search_documents(query: str, top_k: int = 10) -> dict[str, Any]:
    """Search documents by query string.

    This is the default (sync) entry point. The agent service replaces
    this with an async-aware version at runtime by calling
    ``create_bound_search_tool``.

    Args:
        query: Natural language search query.
        top_k: Maximum number of results.

    Returns:
        Dict with ``results`` list and ``total`` count.
    """
    return _search_documents_sync(query, top_k)


def create_bound_search_tool(retriever: Any) -> callable:
    """Create an async search function bound to a specific retriever instance.

    The agent service calls this to produce a tool function that uses the
    live HybridRetriever rather than the stub above.

    Args:
        retriever: A ``HybridRetriever`` instance.

    Returns:
        An async callable with the same signature as ``search_documents``.
    """

    async def bound_search(query: str, top_k: int = 10) -> dict[str, Any]:
        try:
            results = await retriever.search(query=query, top_k=top_k)
            return {
                "results": [
                    {
                        "chunk_id": r.chunk_id,
                        "document_id": r.document_id,
                        "text": r.text,
                        "score": r.score,
                        "page": r.page,
                        "metadata": r.metadata,
                    }
                    for r in results
                ],
                "total": len(results),
            }
        except Exception as e:
            logger.error("search_documents failed: %s", e)
            return {"results": [], "total": 0, "error": str(e)}

    return bound_search
