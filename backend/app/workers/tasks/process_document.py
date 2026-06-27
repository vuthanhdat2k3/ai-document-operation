"""Background task for processing/parsing uploaded documents."""

from __future__ import annotations

import asyncio
import json
import logging
import tempfile
import traceback
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models.document import Document
from app.db.models.document_page import DocumentPage
from app.db.session import get_session_factory
from app.processing.parsers import get_parser
from app.processing.parsers.base import ParseResult
from app.services.storage import DocumentStorageService

logger = logging.getLogger(__name__)

_PROGRESS_TTL = 86400  # 24 hours


async def _update_progress(
    redis: aioredis.Redis[str],
    task_id: str,
    status: str,
    progress: float,
    error: str | None = None,
) -> None:
    """Store task progress in Redis.

    Args:
        redis: Async Redis client.
        task_id: Unique task identifier.
        status: Current task status string.
        progress: Progress ratio (0.0 to 1.0).
        error: Optional error message if the task failed.
    """
    payload: dict[str, Any] = {
        "task_id": task_id,
        "status": status,
        "progress": round(progress, 4),
        "error": error,
    }
    await redis.set(
        f"docops:parse_task:{task_id}",
        json.dumps(payload, default=str),
        ex=_PROGRESS_TTL,
    )


def _run_parser_sync(mime_type: str, file_path: Path) -> ParseResult:
    """Run the appropriate parser synchronously.

    This function is intended to be executed in a thread executor because
    parsers are CPU-bound and synchronous.

    Args:
        mime_type: MIME type of the document.
        file_path: Path to the temporary file on disk.

    Returns:
        ParseResult from the parser.

    Raises:
        ValueError: If no parser is available for the MIME type.
    """
    parser = get_parser(mime_type)
    if parser is None:
        raise ValueError(f"No parser available for MIME type: {mime_type}")
    return parser.parse(file_path)


async def process_document_task(ctx: dict[str, Any], document_id: str) -> dict[str, Any]:
    """ARQ worker task that parses an uploaded document.

    Downloads the document from storage, runs the appropriate parser in a
    thread executor, saves per-page results to the database, and updates
    the document status.

    Args:
        ctx: ARQ worker context (contains ``redis`` client).
        document_id: UUID string of the document to process.

    Returns:
        Dictionary with ``document_id``, ``status``, ``page_count``, and
        ``quality_score``.
    """
    redis: aioredis.Redis[str] = ctx["redis"]
    doc_uuid = uuid.UUID(document_id)
    task_id = ctx.get("job_id", document_id)
    storage = DocumentStorageService()

    session_factory = get_session_factory()

    async with session_factory() as db:
        try:
            await _update_progress(redis, task_id, "processing", 0.0)

            result = await db.execute(
                select(Document)
                .options(selectinload(Document.pages))
                .where(Document.id == doc_uuid)
            )
            document = result.scalar_one_or_none()
            if document is None:
                raise ValueError(f"Document {document_id} not found")

            if document.status not in ("uploaded", "queued"):
                raise ValueError(
                    f"Document {document_id} has status '{document.status}', "
                    "expected 'uploaded' or 'queued'"
                )

            document.status = "processing"
            document.processed_at = None
            await db.commit()

            await _update_progress(redis, task_id, "processing", 0.1)

            file_bytes = await storage.download_document(document.storage_path)

            with tempfile.NamedTemporaryFile(
                suffix=_mime_to_suffix(document.mime_type),
                delete=False,
            ) as tmp:
                tmp.write(file_bytes)
                tmp_path = Path(tmp.name)

            await _update_progress(redis, task_id, "processing", 0.3)

            try:
                loop = asyncio.get_running_loop()
                parse_result: ParseResult = await loop.run_in_executor(
                    None,
                    _run_parser_sync,
                    document.mime_type,
                    tmp_path,
                )
            finally:
                tmp_path.unlink(missing_ok=True)

            await _update_progress(redis, task_id, "processing", 0.6)

            for page in document.pages:
                await db.delete(page)
            await db.flush()

            page_records: list[DocumentPage] = []
            for page_result in parse_result.pages:
                page_record = DocumentPage(
                    id=uuid.uuid4(),
                    document_id=doc_uuid,
                    page_number=page_result.page_number,
                    ocr_text=page_result.text,
                    ocr_confidence=page_result.confidence,
                    ocr_engine=type(
                        get_parser(document.mime_type)
                    ).__name__.lower()
                    if get_parser(document.mime_type)
                    else None,
                )
                db.add(page_record)
                page_records.append(page_record)

            await db.flush()

            await _update_progress(redis, task_id, "processing", 0.8)

            document.status = "completed"
            document.page_count = len(page_records)
            document.processed_at = datetime.now(UTC)

            if parse_result.metadata:
                existing_meta = dict(document.metadata_ or {})
                existing_meta["parse_metadata"] = parse_result.metadata
                document.metadata_ = existing_meta

            await db.commit()

            await _update_progress(redis, task_id, "completed", 1.0)

            logger.info(
                "Document parsed successfully: id=%s pages=%d quality=%.2f",
                document_id,
                len(page_records),
                parse_result.quality_score,
            )

            return {
                "document_id": document_id,
                "status": "completed",
                "page_count": len(page_records),
                "quality_score": parse_result.quality_score,
            }

        except Exception as exc:
            logger.error(
                "Document parsing failed: id=%s error=%s",
                document_id,
                str(exc),
                exc_info=True,
            )

            try:
                result = await db.execute(
                    select(Document).where(Document.id == doc_uuid)
                )
                document = result.scalar_one_or_none()
                if document is not None:
                    document.status = "failed"
                    document.processed_at = datetime.now(UTC)
                    existing_meta = dict(document.metadata_ or {})
                    existing_meta["parse_error"] = str(exc)
                    existing_meta["parse_traceback"] = traceback.format_exc()
                    document.metadata_ = existing_meta
                    await db.commit()
            except Exception:
                logger.exception(
                    "Failed to update document status to 'failed': id=%s",
                    document_id,
                )

            await _update_progress(
                redis,
                task_id,
                "failed",
                0.0,
                error=str(exc),
            )

            return {
                "document_id": document_id,
                "status": "failed",
                "error": str(exc),
            }


def _mime_to_suffix(mime_type: str) -> str:
    """Map a MIME type to a file suffix for temporary file creation.

    Args:
        mime_type: The document MIME type.

    Returns:
        A file extension string including the leading dot.
    """
    mapping = {
        "application/pdf": ".pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        "text/plain": ".txt",
        "text/html": ".html",
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/tiff": ".tiff",
    }
    return mapping.get(mime_type, ".bin")
