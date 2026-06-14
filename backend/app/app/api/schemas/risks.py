"""Pydantic schemas for risk analysis API endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RiskItemResponse(BaseModel):
    """Response schema for a single risk item."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: uuid.UUID
    category: str
    severity: str
    title: str
    description: str | None = None
    evidence: dict | None = None
    page_number: int | None = None
    status: str = "open"
    resolution: str | None = None
    detected_by: str | None = None
    created_at: datetime | None = None


class ChecklistItemResponse(BaseModel):
    """Response schema for a single checklist item."""

    model_config = ConfigDict(frozen=True)

    description: str
    severity: str
    category: str
    suggested_action: str
    due_days: int


class MissingClauseResponse(BaseModel):
    """Response schema for a missing clause."""

    model_config = ConfigDict(frozen=True)

    clause_name: str
    description: str
    severity: str
    suggestion: str


class AnomalyResponse(BaseModel):
    """Response schema for a detected anomaly."""

    model_config = ConfigDict(frozen=True)

    field_name: str
    value: object = None
    expected_range: str
    deviation: float
    severity: str


class AnalysisResultResponse(BaseModel):
    """Full response from the risk analysis pipeline."""

    model_config = ConfigDict(frozen=True)

    document_id: str
    risk_count: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    risks: list[RiskItemResponse]
    missing_clauses: list[MissingClauseResponse]
    anomalies: list[AnomalyResponse]
    checklist: list[ChecklistItemResponse]
