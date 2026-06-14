"""Pydantic schemas for evaluation API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvalRunRequest(BaseModel):
    """Request body for triggering an evaluation run."""

    model_config = ConfigDict(frozen=True)

    dataset_path: str | None = Field(
        default=None,
        description="Path to the JSONL gold dataset file.",
    )
    pipeline_name: str = Field(
        default="qa",
        description="Name of the pipeline to evaluate (e.g. 'qa', 'extract').",
    )
    options: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional evaluation options.",
    )


class MetricResultResponse(BaseModel):
    """A single metric name-value pair."""

    model_config = ConfigDict(frozen=True)

    name: str
    value: float


class PerSampleResultResponse(BaseModel):
    """Result for a single evaluation sample."""

    model_config = ConfigDict(frozen=True)

    sample_id: str
    question: str
    predicted_answer: str
    expected_answer: str
    metrics: dict[str, float] = Field(default_factory=dict)
    latency_ms: float = 0.0
    error: str | None = None


class EvalResultResponse(BaseModel):
    """Response body for evaluation results."""

    model_config = ConfigDict(frozen=True)

    dataset_name: str
    total_samples: int
    successful_samples: int
    failed_samples: int
    aggregate_metrics: dict[str, float] = Field(default_factory=dict)
    per_sample_results: list[PerSampleResultResponse] = Field(default_factory=list)
    total_latency_ms: float = 0.0
    summary: str = ""
    run_id: str = ""
    created_at: datetime | None = None


class EvalRunTriggeredResponse(BaseModel):
    """Response returned immediately when an eval run is triggered."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    status: str = "running"
    message: str = "Evaluation run started."


class EvalResultsListResponse(BaseModel):
    """Response listing available evaluation results."""

    model_config = ConfigDict(frozen=True)

    results: list[EvalResultResponse] = Field(default_factory=list)
    total: int = 0
