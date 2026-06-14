"""Hybrid search API endpoint backed by Qdrant."""

import logging

from fastapi import APIRouter

from app.api.schemas.search import (
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/", response_model=SearchResponse)
async def hybrid_search(body: SearchRequest) -> SearchResponse:
    """Execute a hybrid search across indexed documents in Qdrant."""
    settings = get_settings()

    try:
        from qdrant_client import QdrantClient
        from app.rag.embedder import EmbeddingPipeline
        from app.rag.retriever import HybridRetriever
        from app.vector.collections import DEFAULT_COLLECTION

        qdrant = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
        embedder = EmbeddingPipeline()
        retriever = HybridRetriever(
            qdrant_client=qdrant,
            embedder=embedder,
            collection_name=DEFAULT_COLLECTION,
        )

        filters = None
        if body.document_ids:
            filters = {"document_id": body.document_ids[0] if len(body.document_ids) == 1 else body.document_ids}

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
        qdrant.close()

    except Exception:
        logger.warning("Hybrid search failed, returning empty results", exc_info=True)
        result_items = []

    return SearchResponse(
        results=result_items,
        total=len(result_items),
        query=body.query,
        cached=False,
    )
