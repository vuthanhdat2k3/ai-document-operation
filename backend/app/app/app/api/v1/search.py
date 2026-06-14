"""Hybrid search API endpoint backed by Qdrant with Redis caching."""

import hashlib
import json
import logging

from fastapi import APIRouter, Depends

from app.api.schemas.search import (
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)
from app.auth.dependencies import get_current_user
from app.cache.query_cache import QueryCache
from app.cache.redis import RedisCache
from app.config import get_settings
from app.db.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


def _build_query_hash(query: str, document_ids: list[str] | None, top_k: int) -> str:
    """Build a deterministic cache key hash for a search query."""
    raw = json.dumps({"q": query, "doc_ids": document_ids, "top_k": top_k}, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _get_query_cache() -> QueryCache:
    """Dependency that provides a QueryCache instance."""
    settings = get_settings()
    redis_cache = RedisCache(settings, prefix="docops")
    return QueryCache(redis_cache)


@router.post("/", response_model=SearchResponse)
async def hybrid_search(
    body: SearchRequest,
    current_user: User = Depends(get_current_user),  # noqa: B008
    cache: QueryCache = Depends(_get_query_cache),  # noqa: B008
) -> SearchResponse:
    """Execute a hybrid (dense + sparse) search across indexed documents.

    Results are cached in Redis for 5 minutes per unique query+filters
    combination.

    Args:
        body: Search request with query string, optional document ID filter,
            and top_k limit.
        current_user: Authenticated user.
        cache: Query cache instance.

    Returns:
        Ranked search results with chunk text, scores, and page references.
    """
    query_hash = _build_query_hash(body.query, body.document_ids, body.top_k)

    cached = await cache.get_cached_search(query_hash)
    if cached is not None:
        return SearchResponse(
            results=[SearchResultItem(**r) for r in cached],
            total=len(cached),
            query=body.query,
            cached=True,
        )

    settings = get_settings()

    try:
        from qdrant_client import QdrantClient

        from app.rag.embedder import EmbeddingPipeline
        from app.rag.retriever import HybridRetriever
        from app.vector.collections import DEFAULT_COLLECTION

        qdrant = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
        embedder = EmbeddingPipeline(settings)
        retriever = HybridRetriever(
            qdrant_client=qdrant,
            embedder=embedder,
            collection_name=DEFAULT_COLLECTION,
        )

        filters = None
        if body.document_ids:
            filters = {"document_id": body.document_ids}

        search_results = await retriever.search(
            query=body.query,
            top_k=body.top_k,
            filters=filters,
        )

        result_items = [
            SearchResultItem(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                text=r.text,
                score=r.score,
                page=r.page,
            )
            for r in search_results
        ]

    except Exception:
        logger.warning("Hybrid search failed, returning empty results", exc_info=True)
        result_items = []

    result_dicts = [r.model_dump() for r in result_items]
    await cache.cache_search_result(query_hash, result_dicts, ttl=300)

    return SearchResponse(
        results=result_items,
        total=len(result_items),
        query=body.query,
        cached=False,
    )
