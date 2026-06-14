"""Hybrid retriever combining dense and sparse search via Qdrant."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.rag.embedder import EmbeddingPipeline
from app.vector.collections import (
    DEFAULT_COLLECTION,
    DENSE_VECTOR_NAME,
    SPARSE_VECTOR_NAME,
)

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single retrieval result.

    Attributes:
        chunk_id: Unique identifier for the chunk (Qdrant point ID).
        document_id: Parent document UUID.
        text: The chunk text.
        score: Relevance score (higher is better).
        page: Page number the chunk originated from.
        metadata: Additional payload metadata.
    """

    chunk_id: str
    document_id: str
    text: str
    score: float
    page: int = 0
    metadata: dict = field(default_factory=dict)


class HybridRetriever:
    """Execute hybrid (dense + sparse) search against a Qdrant collection.

    Uses the ``qdrant_client`` Python SDK for query execution.

    Args:
        qdrant_client: An initialised ``qdrant_client.QdrantClient``.
        embedder: An ``EmbeddingPipeline`` instance for vectorising queries.
        collection_name: Target Qdrant collection.
    """

    def __init__(
        self,
        qdrant_client: Any,
        embedder: EmbeddingPipeline,
        collection_name: str = DEFAULT_COLLECTION,
    ) -> None:
        self._client = qdrant_client
        self._embedder = embedder
        self._collection = collection_name

    async def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[SearchResult]:
        """Run hybrid retrieval and return fused, ranked results.

        1. Embed the query (dense + sparse).
        2. Execute dense vector search.
        3. Execute sparse vector search (if sparse vectors are available).
        4. Apply RRF fusion if both paths returned results.

        Args:
            query: Natural language query string.
            top_k: Maximum number of results to return.
            filters: Optional metadata filters (Qdrant ``Filter``-compatible dict).

        Returns:
            List of ``SearchResult`` sorted by relevance score descending.
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue, QueryResponse

        query_dense = self._embedder.embed_query(query)
        query_result = self._embedder.embed_texts([query])
        query_sparse = query_result.sparse[0] if query_result.sparse else None

        qdrant_filter = self._build_filter(filters) if filters else None

        dense_results = await self._dense_search(query_dense, top_k * 2, qdrant_filter)

        sparse_results: list[SearchResult] = []
        if query_sparse and query_sparse.get("indices"):
            sparse_results = await self._sparse_search(query_sparse, top_k * 2, qdrant_filter)

        if sparse_results:
            from app.rag.fusion import rrf_fusion

            fused = rrf_fusion([dense_results, sparse_results])
            return fused[:top_k]

        return dense_results[:top_k]

    async def _dense_search(
        self,
        query_vector: list[float],
        limit: int,
        qdrant_filter: Any | None,
    ) -> list[SearchResult]:
        """Execute cosine similarity search on dense vectors."""
        from qdrant_client.models import NamedVector

        try:
            results = self._client.query_points(
                collection_name=self._collection,
                query=query_vector,
                using=DENSE_VECTOR_NAME,
                query_filter=qdrant_filter,
                limit=limit,
                with_payload=True,
            )
            return self._parse_points(results)
        except Exception:
            logger.warning("Dense search failed", exc_info=True)
            return []

    async def _sparse_search(
        self,
        sparse_vector: dict,
        limit: int,
        qdrant_filter: Any | None,
    ) -> list[SearchResult]:
        """Execute sparse vector search."""
        from qdrant_client.models import NamedSparseVector, SparseVector

        try:
            sparse = NamedSparseVector(
                name=SPARSE_VECTOR_NAME,
                vector=SparseVector(
                    indices=sparse_vector["indices"],
                    values=sparse_vector["values"],
                ),
            )
            results = self._client.query_points(
                collection_name=self._collection,
                query=sparse,
                using=SPARSE_VECTOR_NAME,
                query_filter=qdrant_filter,
                limit=limit,
                with_payload=True,
            )
            return self._parse_points(results)
        except Exception:
            logger.debug("Sparse search not available or failed", exc_info=True)
            return []

    @staticmethod
    def _parse_points(response: Any) -> list[SearchResult]:
        """Convert Qdrant query response to ``SearchResult`` list."""
        results: list[SearchResult] = []
        points = getattr(response, "points", None) or response
        if isinstance(points, list):
            for pt in points:
                payload = getattr(pt, "payload", None) or {}
                score = getattr(pt, "score", 0.0)
                results.append(
                    SearchResult(
                        chunk_id=str(getattr(pt, "id", "")),
                        document_id=payload.get("document_id", ""),
                        text=payload.get("text", ""),
                        score=score,
                        page=payload.get("page", 0),
                        metadata={
                            k: v
                            for k, v in payload.items()
                            if k not in ("text", "document_id", "page")
                        },
                    )
                )
        return results

    @staticmethod
    def _build_filter(filters: dict) -> Any:
        """Build a Qdrant ``Filter`` from a simple key-value dict.

        Supports exact-match filters. Keys map to payload field names.
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        conditions = []
        for key, value in filters.items():
            if isinstance(value, list):
                from qdrant_client.models import MatchAny

                conditions.append(
                    FieldCondition(key=key, match=MatchAny(any=value))
                )
            else:
                conditions.append(
                    FieldCondition(key=key, match=MatchValue(value=value))
                )
        return Filter(must=conditions)
