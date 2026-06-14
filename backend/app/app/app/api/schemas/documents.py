"""Pydantic schemas for document API endpoints."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
import uuid

from pydantic import AliasPath, BaseModel, ConfigDict, Field

from app.api.schemas.common import PaginatedResponse
from app.services.validation import ALLOWED_MIME_TYPES as _VALIDATION_MIME_MAP

ALLOWED_MIME_TYPES: set[str] = set(_VALIDATION_MIME_MAP.keys())


class DocumentStatus(StrEnum):
    """Valid document processing statuses."""

    UPLOADED = "uploaded"
    QUEUED = "queued"
    PROCESSING = "processing"
    OCR_COMPLETE = "ocr_complete"
    EXTRACTION_COMPLETE = "extraction_complete"
    REVIEWED = "reviewed"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class DocumentCreate(BaseModel):
    """Request schema for creating a document (used internally, not via API)."""

    filename: str = Field(..., min_length=1, max_length=500)
    mime_type: str
    file_size_bytes: int = Field(..., gt=0)


class DocumentUpdate(BaseModel):
    """Request schema for updating document metadata."""

    filename: str | None = Field(None, min_length=1, max_length=500)
    document_type: str | None = Field(None, max_length=100)
    metadata_: dict | None = Field(None, alias="metadata")


class DocumentResponse(BaseModel):
    """Response schema for a single document."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    user_id: uuid.UUID
    filename: str
    original_filename: str
    mime_type: str
    file_size_bytes: int
    storage_backend: str
    storage_path: str
    page_count: int | None = None
    status: str
    document_type: str | None = None
    classification: dict | None = None
    metadata: dict = Field(default_factory=dict, validation_alias=AliasPath("metadata_"))
    checksum_sha256: str
    uploaded_at: datetime
    processed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class DocumentDetailResponse(DocumentResponse):
    """Extended document response with pages and chunks summary."""

    pages: list[dict] = Field(default_factory=list)
    chunks: list[dict] = Field(default_factory=list)


DocumentListResponse = PaginatedResponse[DocumentResponse]


class DownloadResponse(BaseModel):
    """Response schema for presigned download URL."""

    model_config = ConfigDict(frozen=True)

    url: str
    expires_in: int = 3600
