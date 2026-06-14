"""Pydantic schemas for report API endpoints."""

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ReportType(StrEnum):
    """Supported report types."""

    SUMMARY = "summary"
    DETAILED = "detailed"
    RISK_ASSESSMENT = "risk_assessment"


class ExportFormat(StrEnum):
    """Supported export formats."""

    MARKDOWN = "markdown"
    PDF = "pdf"


class ReportCreateRequest(BaseModel):
    """Request schema for generating a report."""

    model_config = ConfigDict(frozen=True)

    report_type: str = Field(
        default="summary",
        description="Type of report to generate: summary, detailed, or risk_assessment.",
    )


class ReportResponse(BaseModel):
    """Response schema for report metadata."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    document_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None
    report_type: str
    title: str
    content: dict
    format: str
    storage_path: str | None = None
    status: str
    generated_at: datetime
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ReportDownloadResponse(BaseModel):
    """Response schema for report download."""

    model_config = ConfigDict(frozen=True)

    report_id: uuid.UUID
    format: str
    filename: str
    download_url: str | None = None
    content: str | None = None
