from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ParseRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    options: dict | None = None


class ParseStatusResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_id: str
    status: str = Field(..., description="queued | processing | completed | failed")
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    error: str | None = None


class TableData(BaseModel):
    model_config = ConfigDict(frozen=True)

    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class PageContent(BaseModel):
    model_config = ConfigDict(frozen=True)

    page_number: int = Field(..., gt=0)
    text: str = ""
    tables: list[TableData] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class ParsedContentResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_id: uuid.UUID
    pages: list[PageContent] = Field(default_factory=list)
    quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    parsed_at: datetime | None = None
