"""Common Pydantic response models for API endpoints."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Individual validation error detail."""

    model_config = ConfigDict(frozen=True)

    field: str | None = None
    issue: str
    value: Any | None = None


class ErrorBody(BaseModel):
    """Nested error object inside ErrorResponse."""

    model_config = ConfigDict(frozen=True)

    code: str
    message: str
    request_id: str
    details: list[ErrorDetail] | None = None
    timestamp: str = Field(default="")


class ErrorResponse(BaseModel):
    """Structured error response returned by exception handlers.

    Follows the API spec error envelope::

        {
            "error": {
                "code": "NOT_FOUND",
                "message": "Resource not found.",
                "request_id": "req_abc123",
                "timestamp": "2025-01-15T10:30:00Z"
            }
        }
    """

    model_config = ConfigDict(frozen=True)

    error: ErrorBody


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""

    model_config = ConfigDict(frozen=True)

    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


# Rebuild to resolve forward references in Generic models
PaginatedResponse.model_rebuild()


class HealthResponse(BaseModel):
    """Response model for the health check endpoint."""

    model_config = ConfigDict(frozen=True)

    status: str
    version: str
    timestamp: str


class ServiceStatus:
    """Constants for service check results."""

    OK = "ok"


class ReadinessResponse(BaseModel):
    """Response model for the readiness check endpoint."""

    model_config = ConfigDict(frozen=True)

    status: str
    version: str
    services: dict[str, str]
