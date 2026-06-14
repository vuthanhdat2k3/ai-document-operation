"""Pydantic schemas for Q&A API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class QARequest(BaseModel):
    """Request body for asking a question about a document."""

    model_config = ConfigDict(frozen=True)

    query: str = Field(..., min_length=1, max_length=2000, description="The question to ask.")
    document_id: str | None = Field(
        None,
        description="Target document UUID. If None, searches across all accessible documents.",
    )
    session_id: str | None = Field(
        None,
        description="Existing session UUID for conversation continuity.",
    )


class CitationResponse(BaseModel):
    """A citation referencing a specific chunk in a source document."""

    model_config = ConfigDict(frozen=True)

    chunk_id: str
    document_id: str
    page: int = 0
    text: str = Field("", description="Excerpt from the source chunk.")
    score: float = Field(0.0, description="Relevance score.")


class QAResponse(BaseModel):
    """Response body for a Q&A answer."""

    model_config = ConfigDict(frozen=True)

    answer: str
    citations: list[CitationResponse] = Field(default_factory=list)
    groundedness_score: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="How well the answer is supported by the sources (0.0–1.0).",
    )
    session_id: str
    confidence: float = Field(0.0, ge=0.0, le=1.0)


class QAHISTORYEntry(BaseModel):
    """A single Q&A exchange in a session."""

    model_config = ConfigDict(frozen=True)

    query: str
    answer: str
    citations: list[CitationResponse] = Field(default_factory=list)
    groundedness_score: float = 0.0
    timestamp: datetime | None = None


class QASessionResponse(BaseModel):
    """Response body for Q&A session history."""

    model_config = ConfigDict(frozen=True)

    session_id: str
    history: list[QAHISTORYEntry] = Field(default_factory=list)
    total: int = 0
