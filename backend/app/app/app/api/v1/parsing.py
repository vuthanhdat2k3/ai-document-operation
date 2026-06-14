"""Document parsing API endpoints — enqueue, status polling, and content retrieval."""

from __future__ import annotations

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
from app.db.session import get_db
from app.deps import get_redis
from app.services.parsing_service import (
    DocumentNotReadyError,
    ParsingService,
    ParsingServiceError,
    TaskNotFoundError,
)

router = APIRouter(prefix="/documents", tags=["parsing"])


async def _get_parsing_service(
    redis_client: aioredis.Redis = Depends(get_redis),  # noqa: B008
) -> ParsingService:
    """Dependency that provides a ``ParsingService`` instance."""
    return ParsingService(arq_redis=redis_client)


@router.post("/{document_id}/parse", response_model=ParseStatusResponse, status_code=202)
async def enqueue_parse(
    document_id: uuid.UUID,
    body: ParseRequest | None = None,
    service: ParsingService = Depends(_get_parsing_service),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ParseStatusResponse:
    """Enqueue a document for background parsing.

    Returns a task ID that can be used to poll for status via the
    ``GET /{document_id}/parse-status`` endpoint.

    Args:
        document_id: UUID of the document to parse.
        body: Optional parse request body (currently unused, reserved for
            future parser options).
        service: Injected ``ParsingService``.
        db: Injected async database session.

    Returns:
        Initial parse status with task ID and ``queued`` status.
    """
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
    service: ParsingService = Depends(_get_parsing_service),  # noqa: B008
) -> ParseStatusResponse:
    """Poll the parsing status for a document.

    The task ID is derived from the document ID using the convention
    ``parse:{document_id}`` which matches the job ID format used when
    enqueuing.

    Args:
        document_id: UUID of the document being parsed.
        service: Injected ``ParsingService``.

    Returns:
        Current parse status including progress and any error message.
    """
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
    service: ParsingService = Depends(_get_parsing_service),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ParsedContentResponse:
    """Retrieve the parsed content of a document.

    Returns the per-page text, confidence scores, and quality metadata
    produced by the parsing worker.

    Args:
        document_id: UUID of the document.
        service: Injected ``ParsingService``.
        db: Injected async database session.

    Returns:
        Full parsed content for the document.
    """
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
