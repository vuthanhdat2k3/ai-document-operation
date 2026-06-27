"""Document parsing API endpoints — enqueue, status polling, and content retrieval."""

from __future__ import annotations

import logging
import uuid

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.error_handler import NotFoundError, ValidationErrorDetail
from app.api.schemas.parsing import (
    ParsedContentResponse,
    ParseRequest,
    ParseStatusResponse,
)
from app.auth.dependencies import get_current_user_id
from app.db.session import get_db
from app.deps import get_redis
from app.services.parsing_service import (
    DocumentNotReadyError,
    ParsingService,
    ParsingServiceError,
    TaskNotFoundError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["parsing"])


async def _verify_document_ownership(
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Raise NotFoundError if the document does not belong to the user."""
    from sqlalchemy import select
    from app.db.models.document import Document

    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == user_id,
            Document.deleted_at.is_(None),
        )
    )
    if result.scalar_one_or_none() is None:
        raise NotFoundError(f"Document {document_id} not found")


async def _get_parsing_service(
    redis_client: aioredis.Redis = Depends(get_redis),  # noqa: B008
) -> ParsingService:
    """Dependency that provides a ``ParsingService`` instance."""
    return ParsingService(arq_redis=redis_client)


@router.post("/{document_id}/parse", response_model=ParseStatusResponse, status_code=202)
async def enqueue_parse(
    document_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
    body: ParseRequest | None = None,
    service: ParsingService = Depends(_get_parsing_service),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ParseStatusResponse:
    """Enqueue a document for background parsing (must own the document)."""
    await _verify_document_ownership(document_id, user_id, db)
    try:
        task_id = await service.enqueue_parse(document_id, db)
    except ParsingServiceError as exc:
        raise NotFoundError(str(exc)) from exc
    except DocumentNotReadyError as exc:
        raise ValidationErrorDetail(str(exc)) from exc

    return ParseStatusResponse(
        task_id=task_id,
        status="queued",
        progress=0.0,
    )


@router.get("/{document_id}/parse-status", response_model=ParseStatusResponse)
async def get_parse_status(
    document_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
    service: ParsingService = Depends(_get_parsing_service),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ParseStatusResponse:
    """Poll the parsing status for a document (must own the document)."""
    await _verify_document_ownership(document_id, user_id, db)
    task_id = f"parse:{document_id}"
    try:
        status_data = await service.get_parse_status(task_id)
    except TaskNotFoundError as exc:
        raise NotFoundError(str(exc)) from exc

    return ParseStatusResponse(
        task_id=status_data.get("task_id", task_id),
        status=status_data.get("status", "unknown"),
        progress=status_data.get("progress", 0.0),
        error=status_data.get("error"),
    )


@router.get("/{document_id}/parsed", response_model=ParsedContentResponse)
async def get_parsed_content(
    document_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
    service: ParsingService = Depends(_get_parsing_service),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ParsedContentResponse:
    """Retrieve the parsed content of a document (must own the document)."""
    await _verify_document_ownership(document_id, user_id, db)
    try:
        content = await service.get_parsed_content(document_id, db)
    except ParsingServiceError as exc:
        raise NotFoundError(str(exc)) from exc

    from app.api.schemas.parsing import PageContent, TableData

    pages = []
    for p in content.get("pages", []):
        pages.append(
            PageContent(
                page_number=p["page_number"],
                text=p.get("text", ""),
                confidence=p.get("confidence"),
            )
        )

    parsed_at = content.get("parsed_at")
    if isinstance(parsed_at, str):
        from datetime import datetime

        parsed_at = datetime.fromisoformat(parsed_at)

    return ParsedContentResponse(
        document_id=document_id,
        pages=pages,
        quality_score=content.get("quality_score"),
        parsed_at=parsed_at,
    )


@router.post("/{document_id}/index", status_code=200)
async def index_document(
    document_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict:
    """Index a parsed document: chunk text, generate embeddings, store in Qdrant (must own the document)."""
    await _verify_document_ownership(document_id, user_id, db)
    import hashlib
    from sqlalchemy import select, delete
    from app.db.models.document import Document
    from app.db.models.document_page import DocumentPage, DocumentChunk
    from app.rag.chunker import TextChunker
    from app.rag.embedder import EmbeddingPipeline
    from app.config import get_settings

    settings = get_settings()

    # 1. Load document
    stmt = select(Document).where(Document.id == document_id, Document.deleted_at.is_(None))
    result = await db.execute(stmt)
    document = result.scalar_one_or_none()
    if document is None:
        raise NotFoundError(f"Document {document_id} not found.")

    # 2. Load parsed pages
    stmt = select(DocumentPage).where(DocumentPage.document_id == document_id)
    result = await db.execute(stmt)
    pages = result.scalars().all()

    if not pages:
        raise ValidationErrorDetail("Document has no parsed content. Run parse first.")

    # 3. Chunk text
    chunker = TextChunker(chunk_size=512, chunk_overlap=64)
    all_chunks = []
    for page in pages:
        if not page.ocr_text:
            continue
        chunks = chunker.recursive_split(
            page.ocr_text,
            metadata={"page_number": page.page_number, "document_id": str(document_id)},
        )
        all_chunks.extend(chunks)

    if not all_chunks:
        raise ValidationErrorDetail("No text content found to index.")

    # 4. Delete old chunks for this document
    await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))

    # 5. Generate embeddings
    embedder = EmbeddingPipeline()
    chunk_texts = [c.text for c in all_chunks]
    embedding_result = embedder.embed_texts(chunk_texts)

    # 6. Save chunks to DB and prepare Qdrant points
    chunk_records = []
    qdrant_points = []
    for i, chunk in enumerate(all_chunks):
        chunk_id = str(uuid.uuid4())
        record = DocumentChunk(
            id=uuid.UUID(chunk_id) if len(chunk_id) == 36 else uuid.uuid4(),
            document_id=document_id,
            page_number=chunk.metadata.get("page_number", 1),
            chunk_index=i,
            chunk_text=chunk.text,
            token_count=len(chunk.text) // 4,
            embedding_model="bge-m3",
            embedding_dim=1024,
            chunk_metadata=chunk.metadata,
        )
        db.add(record)
        chunk_records.append(record)

        # Prepare Qdrant point
        dense_vector = embedding_result.dense[i] if i < len(embedding_result.dense) else [0.0] * 1024
        from qdrant_client.models import PointStruct
        qdrant_points.append(
            PointStruct(
                id=hashlib.md5(chunk_id.encode()).hexdigest()[:32],
                vector={"dense": dense_vector},
                payload={
                    "chunk_id": chunk_id,
                    "document_id": str(document_id),
                    "page": chunk.metadata.get("page_number", 1),
                    "chunk_index": i,
                    "text": chunk.text,
                },
            )
        )

    # 7. Store in Qdrant
    try:
        from qdrant_client import QdrantClient
        qdrant = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
        )

        # Create collection if not exists
        from qdrant_client.models import VectorParams, Distance
        collections = [c.name for c in qdrant.get_collections().collections]
        if "document_chunks" not in collections:
            qdrant.create_collection(
                collection_name="document_chunks",
                vectors_config={"dense": VectorParams(size=1024, distance=Distance.COSINE)},
            )

        # Upsert points
        qdrant.upsert(
            collection_name="document_chunks",
            points=qdrant_points,
        )
        qdrant.close()
    except Exception as exc:
        logger.warning("Qdrant indexing failed (chunks saved to DB): %s", exc)

    # 8. Update document status
    document.status = "completed"
    await db.flush()

    return {
        "document_id": str(document_id),
        "chunks_created": len(chunk_records),
        "pages_processed": len(pages),
        "qdrant_points": len(qdrant_points),
        "status": "indexed",
    }
