"""Hybrid search API endpoint backed by Qdrant."""

import logging
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.search import (
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)
from app.auth.dependencies import get_current_user_id
from app.config import get_settings
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/", response_model=SearchResponse)
async def hybrid_search(
    body: SearchRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> SearchResponse:
    """Execute a hybrid search across the current user's indexed documents."""
    from sqlalchemy import select
    from app.db.models.document import Document

    # Only search documents owned by the current user
    doc_result = await db.execute(
        select(Document.id).where(
            Document.user_id == user_id,
            Document.deleted_at.is_(None),
            Document.status == "completed",
        )
    )
    user_doc_ids = [str(row[0]) for row in doc_result.all()]
    if not user_doc_ids:
        return SearchResponse(results=[], total=0, query=body.query, cached=False)

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

        # Scope by user's documents (intersect with explicit document_ids if given)
        if body.document_ids:
            doc_ids = [d for d in body.document_ids if d in user_doc_ids]
        else:
            doc_ids = user_doc_ids
        filters = {"document_id": doc_ids[0] if len(doc_ids) == 1 else doc_ids} if doc_ids else None

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
