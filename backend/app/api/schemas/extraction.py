"""Pydantic schemas for extraction API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExtractRequest(BaseModel):
    """Request body for running field extraction."""

    model_config = ConfigDict(frozen=True)

    schema_name: str = Field(
        ..., min_length=1, max_length=255, description="Name of the extraction schema to use."
    )


class FieldUpdateRequest(BaseModel):
    """Request body for manually correcting an extracted field."""

    model_config = ConfigDict(frozen=True)

    field_value: dict[str, Any] | None = Field(
        None, description="New field value as a JSON object."
    )
    raw_text: str | None = Field(
        None, max_length=10000, description="Updated raw text snippet."
    )


class ValidationResultResponse(BaseModel):
    """Validation result embedded in extraction response."""

    model_config = ConfigDict(frozen=True)

    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ExtractedFieldResponse(BaseModel):
    """Response schema for a single extracted field."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: str
    field_name: str
    field_value: dict[str, Any] | None = None
    raw_text: str | None = None
    confidence: float | None = None
    page_number: int | None = None
    extraction_model: str | None = None
    is_verified: bool = False
    verified_by: str | None = None
    verified_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class ExtractionResultResponse(BaseModel):
    """Response schema for a completed extraction pipeline run."""

    model_config = ConfigDict(frozen=True)

    document_id: str
    document_type: str
    classification_confidence: float
    schema_name: str
    schema_version: int
    total_fields: int
    extracted_count: int
    valid_count: int
    validation: ValidationResultResponse
    fields: list[ExtractedFieldResponse]
    extracted_at: datetime = Field(default_factory=lambda: datetime.now())


class FieldUpdateResponse(BaseModel):
    """Response schema for a field update operation."""

    model_config = ConfigDict(frozen=True)

    id: str
    field_name: str
    old_value: dict[str, Any] | None = None
    new_value: dict[str, Any] | None = None
    is_verified: bool
    verified_by: str
    verified_at: str
