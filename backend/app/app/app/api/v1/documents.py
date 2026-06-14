"""Document CRUD API endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.error_handler import NotFoundError, ValidationErrorDetail
from app.api.schemas.documents import (
    ALLOWED_MIME_TYPES,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentUpdate,
    DownloadResponse,
)
from app.config import Settings, get_settings
from app.db.session import get_db
from app.services.document_service import (
    DocumentNotFoundError,
    DocumentPermissionError,
    DocumentService,
    DocumentValidationError,
)
from app.services.storage import DocumentStorageService
from app.services.validation import FileValidator

router = APIRouter(prefix="/documents", tags=["documents"])

CURRENT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def _get_document_service(
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> DocumentService:
    """Dependency that provides a DocumentService instance."""
    return DocumentService(
        validator=FileValidator(),
        storage=DocumentStorageService(),
    )


async def _get_current_user_id() -> uuid.UUID:
    """Placeholder dependency for the current authenticated user.

    Will be replaced with actual JWT auth dependency.
    """
    return CURRENT_USER_ID


@router.post("/", response_model=DocumentResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),  # noqa: B008
    service: DocumentService = Depends(_get_document_service),  # noqa: B008
    user_id: uuid.UUID = Depends(_get_current_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> DocumentResponse:
    """Upload a document file."""
    content = await file.read()
    original_filename = file.filename or "unknown"

    try:
        document = await service.create_document(
            filename=original_filename,
            content_type=file.content_type or "application/octet-stream",
            file_size=len(content),
            file_bytes=content,
            user_id=user_id,
            db=db,
        )
        await db.commit()
    except DocumentValidationError as exc:
        raise ValidationErrorDetail(str(exc)) from exc

    return DocumentResponse.model_validate(document)


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status: str | None = None,
    document_type: str | None = None,
    service: DocumentService = Depends(_get_document_service),  # noqa: B008
    user_id: uuid.UUID = Depends(_get_current_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> DocumentListResponse:
    """List documents with pagination and optional filters."""
    documents, total = await service.list_documents(
        user_id=user_id,
        db=db,
        page=page,
        page_size=page_size,
        status=status,
        document_type=document_type,
    )
    pages = (total + page_size - 1) // page_size
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(d) for d in documents],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: uuid.UUID,
    service: DocumentService = Depends(_get_document_service),  # noqa: B008
    user_id: uuid.UUID = Depends(_get_current_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> DocumentDetailResponse:
    """Get a document by ID with pages and chunks summary."""
    try:
        document = await service.get_document(document_id, user_id, db)
    except DocumentNotFoundError as exc:
        raise NotFoundError(str(exc)) from exc
    except DocumentPermissionError as exc:
        raise NotFoundError(str(exc)) from exc

    return DocumentDetailResponse.model_validate(document)


@router.patch("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: uuid.UUID,
    body: DocumentUpdate,
    service: DocumentService = Depends(_get_document_service),  # noqa: B008
    user_id: uuid.UUID = Depends(_get_current_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> DocumentResponse:
    """Update document metadata."""
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise ValidationErrorDetail("No fields provided for update.")

    try:
        document = await service.update_document(
            document_id=document_id,
            user_id=user_id,
            updates=update_data,
            db=db,
        )
        await db.commit()
    except DocumentNotFoundError as exc:
        raise NotFoundError(str(exc)) from exc
    except DocumentPermissionError as exc:
        raise NotFoundError(str(exc)) from exc
    except ValueError as exc:
        raise ValidationErrorDetail(str(exc)) from exc

    return DocumentResponse.model_validate(document)


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    service: DocumentService = Depends(_get_document_service),  # noqa: B008
    user_id: uuid.UUID = Depends(_get_current_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> None:
    """Soft delete a document."""
    try:
        await service.delete_document(document_id, user_id, db)
        await db.commit()
    except DocumentNotFoundError as exc:
        raise NotFoundError(str(exc)) from exc
    except DocumentPermissionError as exc:
        raise NotFoundError(str(exc)) from exc


@router.get("/{document_id}/download", response_model=DownloadResponse)
async def download_document(
    document_id: uuid.UUID,
    service: DocumentService = Depends(_get_document_service),  # noqa: B008
    user_id: uuid.UUID = Depends(_get_current_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> DownloadResponse:
    """Get a presigned download URL for a document."""
    try:
        document = await service.get_document(document_id, user_id, db)
    except DocumentNotFoundError as exc:
        raise NotFoundError(str(exc)) from exc
    except DocumentPermissionError as exc:
        raise NotFoundError(str(exc)) from exc

    if not document.storage_path:
        raise NotFoundError("Document has no associated file in storage.")

    try:
        storage_service = DocumentStorageService()
        url = await storage_service.get_presigned_url(document.storage_path)
    except Exception as exc:
        raise NotFoundError(
            f"Could not generate download link: {exc}"
        ) from exc

    return DownloadResponse(url=url, expires_in=3600)
