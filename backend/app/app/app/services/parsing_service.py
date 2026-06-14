"""Parsing service — orchestrates document parsing via ARQ background workers."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import Document
from app.db.models.document_page import DocumentPage

logger = logging.getLogger(__name__)

_TASK_KEY_PREFIX = "docops:parse_task:"


class ParsingServiceError(Exception):
    """Base exception for parsing service operations."""


class DocumentNotReadyError(ParsingServiceError):
    """Raised when a document is not in a parseable state."""


class TaskNotFoundError(ParsingServiceError):
    """Raised when a task cannot be found in Redis."""


class ParsingService:
    """Manages document parsing lifecycle: enqueue, status polling, and content retrieval.

    This service is designed to be instantiated per-request or injected via
    FastAPI dependency injection.

    Args:
        arq_redis: Async Redis client used to communicate with the ARQ
            job queue.  This should be a connection to the same Redis
            instance that the ARQ worker is consuming from.
    """

    def __init__(self, arq_redis: aioredis.Redis[str]) -> None:
        self._redis = arq_redis

    async def enqueue_parse(
        self,
        document_id: uuid.UUID,
        db: AsyncSession,
    ) -> str:
        """Enqueue a document for background parsing.

        Validates that the document exists and is in a parseable state,
        then enqueues an ARQ job.

        Args:
            document_id: UUID of the document to parse.
            db: Active async database session.

        Returns:
            The ARQ job/task ID.

        Raises:
            DocumentNotFoundError: If the document does not exist.
            DocumentNotReadyError: If the document is not in a parseable state.
        """
        result = await db.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()

        if document is None:
            raise ParsingServiceError(f"Document {document_id} not found")

        if document.status not in ("uploaded", "queued", "failed"):
            raise DocumentNotReadyError(
                f"Document {document_id} has status '{document.status}'. "
                "Only documents with status 'uploaded', 'queued', or 'failed' can be parsed."
            )

        document.status = "queued"
        await db.commit()

        from arq import create_pool
        from app.workers.task_queue import WorkerSettings

        arq_pool = await create_pool(WorkerSettings.redis_settings)
        try:
            job = await arq_pool.enqueue_job(
                "process_document_task",
                str(document_id),
                _job_id=f"parse:{document_id}",
            )
            task_id = job.job_id if job is not None else f"parse:{document_id}"
        finally:
            await arq_pool.aclose()

        initial_progress = {
            "task_id": task_id,
            "status": "queued",
            "progress": 0.0,
            "error": None,
        }
        await self._redis.set(
            f"{_TASK_KEY_PREFIX}{task_id}",
            json.dumps(initial_progress, default=str),
            ex=86400,
        )

        logger.info(
            "Parse job enqueued: document_id=%s task_id=%s",
            document_id,
            task_id,
        )
        return task_id

    async def get_parse_status(self, task_id: str) -> dict[str, Any]:
        """Retrieve the current status of a parse task from Redis.

        Args:
            task_id: The ARQ job/task ID returned by ``enqueue_parse``.

        Returns:
            Dictionary with keys ``task_id``, ``status``, ``progress``,
            and ``error``.

        Raises:
            TaskNotFoundError: If the task key is not in Redis.
        """
        raw = await self._redis.get(f"{_TASK_KEY_PREFIX}{task_id}")
        if raw is None:
            raise TaskNotFoundError(f"Task {task_id} not found or expired")

        data: dict[str, Any] = json.loads(raw)
        return data

    async def get_parsed_content(
        self,
        document_id: uuid.UUID,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Retrieve the parsed content (pages) for a document.

        Args:
            document_id: UUID of the document.
            db: Active async database session.

        Returns:
            Dictionary with ``document_id``, ``pages`` (list of page dicts),
            ``quality_score``, and ``parsed_at``.

        Raises:
            ParsingServiceError: If the document does not exist.
        """
        result = await db.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()

        if document is None:
            raise ParsingServiceError(f"Document {document_id} not found")

        pages_result = await db.execute(
            select(DocumentPage)
            .where(DocumentPage.document_id == document_id)
            .order_by(DocumentPage.page_number)
        )
        pages = list(pages_result.scalars().all())

        quality_score: float | None = None
        if document.metadata_ and "parse_metadata" in document.metadata_:
            quality_score = document.metadata_["parse_metadata"].get("quality_score")

        page_list: list[dict[str, Any]] = []
        for page in pages:
            page_list.append({
                "page_number": page.page_number,
                "text": page.ocr_text or "",
                "confidence": page.ocr_confidence,
                "language": page.language,
                "ocr_engine": page.ocr_engine,
            })

        return {
            "document_id": str(document_id),
            "status": document.status,
            "pages": page_list,
            "page_count": len(page_list),
            "quality_score": quality_score,
            "parsed_at": document.processed_at.isoformat() if document.processed_at else None,
        }
