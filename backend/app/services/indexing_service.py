"""Indexing service: chunk → embed → upsert to Qdrant."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document_page import DocumentChunk
from app.rag.chunker import TextChunker
from app.rag.embedder import EmbeddingPipeline
from app.vector.collections import (
    DEFAULT_COLLECTION,
    DENSE_VECTOR_NAME,
    SPARSE_VECTOR_NAME,
    ensure_document_collection,
)

logger = logging.getLogger(__name__)


class IndexingError(Exception):
    """Raised when document indexing fails."""


class IndexingService:
    """Orchestrates the full indexing pipeline for a document.

    1. Load parsed ``DocumentChunk`` rows from the database.
    2. Generate dense (and optionally sparse) embeddings.
    3. Upsert vectors into Qdrant.
    4. Update the DB rows with embedding metadata.

    Args:
        qdrant_client: A ``qdrant_client.QdrantClient`` instance.
        embedder: An ``EmbeddingPipeline`` instance.
        chunker: A ``TextChunker`` instance (used when raw text needs splitting).
        collection_name: Target Qdrant collection name.
    """

    def __init__(
        self,
        qdrant_client: Any,
        embedder: EmbeddingPipeline,
        chunker: TextChunker | None = None,
        collection_name: str = DEFAULT_COLLECTION,
    ) -> None:
        self._client = qdrant_client
        self._embedder = embedder
        self._chunker = chunker or TextChunker()
        self._collection = collection_name

    async def index_document(
        self,
        document_id: str | uuid.UUID,
        db: AsyncSession,
        user_id: str | None = None,
    ) -> None:
        """Run the full indexing pipeline for a single document.

        Args:
            document_id: UUID of the document to index.
            db: Active async database session.
            user_id: UUID of the document owner (for per-user isolation in Qdrant).

        Raises:
            IndexingError: If any stage of the pipeline fails.
        """
        doc_id = str(document_id)
        logger.info("Starting indexing for document %s", doc_id)

        await ensure_document_collection(self._client, self._collection)

        chunks = await self._load_chunks(document_id, db)
        if not chunks:
            logger.warning("No chunks found for document %s, skipping", doc_id)
            return

        texts = [c.chunk_text for c in chunks]
        logger.info("Generating embeddings for %d chunks", len(texts))
        embedding_result = self._embedder.embed_texts(texts)

        await self._upsert_to_qdrant(chunks, embedding_result, doc_id, user_id)

        await self._update_chunk_records(chunks, embedding_result, db)

        logger.info("Indexing complete for document %s (%d chunks)", doc_id, len(chunks))

    async def _load_chunks(
        self,
        document_id: str | uuid.UUID,
        db: AsyncSession,
    ) -> list[DocumentChunk]:
        """Load ``DocumentChunk`` rows ordered by chunk_index."""
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def _upsert_to_qdrant(
        self,
        chunks: list[DocumentChunk],
        embedding_result: Any,
        doc_id: str,
        user_id: str | None = None,
    ) -> None:
        """Upsert chunk vectors into the Qdrant collection."""
        from qdrant_client.models import PointStruct, SparseVector

        points: list[PointStruct] = []
        for i, chunk in enumerate(chunks):
            payload = {
                "document_id": doc_id,
                "page": chunk.page_number,
                "text": chunk.chunk_text,
                "chunk_index": chunk.chunk_index,
            }
            if user_id:
                payload["user_id"] = user_id
            if chunk.chunk_metadata:
                payload.update(chunk.chunk_metadata)

            vectors: dict[str, Any] = {
                DENSE_VECTOR_NAME: embedding_result.dense[i],
            }

            if embedding_result.sparse and i < len(embedding_result.sparse):
                sparse_data = embedding_result.sparse[i]
                if sparse_data.get("indices"):
                    vectors[SPARSE_VECTOR_NAME] = SparseVector(
                        indices=sparse_data["indices"],
                        values=sparse_data["values"],
                    )

            point_id = str(chunk.id)
            points.append(
                PointStruct(id=point_id, vector=vectors, payload=payload)
            )

        batch_size = 100
        for start in range(0, len(points), batch_size):
            batch = points[start : start + batch_size]
            self._client.upsert(
                collection_name=self._collection,
                points=batch,
            )
        logger.info("Upserted %d points to Qdrant collection '%s'", len(points), self._collection)

    async def _update_chunk_records(
        self,
        chunks: list[DocumentChunk],
        embedding_result: Any,
        db: AsyncSession,
    ) -> None:
        """Update ``DocumentChunk`` rows with embedding metadata."""
        model_name = self._embedder.model_name
        dim = len(embedding_result.dense[0]) if embedding_result.dense else None

        for i, chunk in enumerate(chunks):
            chunk.embedding_model = model_name
            chunk.embedding_dim = dim
            chunk.embedding_ref = f"{self._collection}:{chunk.id}"
            if embedding_result.dense and i < len(embedding_result.dense):
                chunk.token_count = len(chunk.chunk_text.split())

        await db.flush()
