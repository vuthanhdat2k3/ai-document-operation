"""Unit tests for Pydantic response schemas in app.api.schemas.common."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.schemas.common import (
    ErrorBody,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    PaginatedResponse,
    ReadinessResponse,
    ServiceStatus,
)


class TestErrorDetail:
    """Tests for ErrorDetail schema."""

    def test_valid_detail(self) -> None:
        d = ErrorDetail(field="name", issue="required", value=None)
        assert d.field == "name"
        assert d.issue == "required"
        assert d.value is None

    def test_field_optional(self) -> None:
        d = ErrorDetail(issue="invalid")
        assert d.field is None

    def test_with_value(self) -> None:
        d = ErrorDetail(field="age", issue="invalid type", value="abc")
        assert d.value == "abc"

    def test_frozen(self) -> None:
        d = ErrorDetail(issue="test")
        with pytest.raises(ValidationError):
            d.issue = "changed"  # type: ignore[misc]


class TestErrorBody:
    """Tests for ErrorBody schema."""

    def test_valid_body(self) -> None:
        body = ErrorBody(
            code="NOT_FOUND",
            message="Resource not found.",
            request_id="abc-123",
        )
        assert body.code == "NOT_FOUND"
        assert body.message == "Resource not found."
        assert body.request_id == "abc-123"
        assert body.details is None

    def test_with_details(self) -> None:
        details = [ErrorDetail(field="email", issue="invalid")]
        body = ErrorBody(
            code="UNPROCESSABLE_ENTITY",
            message="Validation failed.",
            request_id="req-1",
            details=details,
        )
        assert body.details is not None
        assert len(body.details) == 1

    def test_frozen(self) -> None:
        body = ErrorBody(code="ERR", message="msg", request_id="r1")
        with pytest.raises(ValidationError):
            body.code = "OTHER"  # type: ignore[misc]


class TestErrorResponse:
    """Tests for ErrorResponse schema."""

    def test_valid_error_response(self) -> None:
        resp = ErrorResponse(
            error=ErrorBody(
                code="INTERNAL_ERROR",
                message="Something went wrong.",
                request_id="req-42",
            )
        )
        assert resp.error.code == "INTERNAL_ERROR"
        assert resp.error.request_id == "req-42"

    def test_serialization(self) -> None:
        resp = ErrorResponse(
            error=ErrorBody(code="NOT_FOUND", message="Not found.", request_id="r1")
        )
        data = resp.model_dump()
        assert "error" in data
        assert data["error"]["code"] == "NOT_FOUND"


class TestPaginatedResponse:
    """Tests for PaginatedResponse schema."""

    def test_valid_paginated(self) -> None:
        resp = PaginatedResponse[str](items=["a", "b"], total=2, page=1, page_size=10, pages=1)
        assert resp.items == ["a", "b"]
        assert resp.total == 2
        assert resp.page == 1
        assert resp.page_size == 10
        assert resp.pages == 1

    def test_empty_items(self) -> None:
        resp = PaginatedResponse[int](items=[], total=0, page=1, page_size=10, pages=0)
        assert resp.items == []
        assert resp.total == 0

    def test_generic_dict(self) -> None:
        resp = PaginatedResponse[dict[str, str]](
            items=[{"key": "value"}],
            total=1,
            page=1,
            page_size=10,
            pages=1,
        )
        assert resp.items[0]["key"] == "value"


class TestHealthResponse:
    """Tests for HealthResponse schema."""

    def test_valid_health(self) -> None:
        resp = HealthResponse(status="ok", version="1.0.0", timestamp="2024-01-01T00:00:00Z")
        assert resp.status == "ok"
        assert resp.version == "1.0.0"
        assert resp.timestamp == "2024-01-01T00:00:00Z"

    def test_frozen(self) -> None:
        resp = HealthResponse(status="ok", version="1.0.0", timestamp="t")
        with pytest.raises(ValidationError):
            resp.status = "fail"  # type: ignore[misc]


class TestReadinessResponse:
    """Tests for ReadinessResponse schema."""

    def test_valid_readiness(self) -> None:
        services = {"postgres": "ok", "redis": "ok", "qdrant": "ok", "minio": "ok"}
        resp = ReadinessResponse(status="ready", version="1.0.0", services=services)
        assert resp.status == "ready"
        assert all(v == "ok" for v in resp.services.values())

    def test_degraded_status(self) -> None:
        services = {"postgres": "ok", "redis": "error: timeout", "qdrant": "ok", "minio": "ok"}
        resp = ReadinessResponse(status="degraded", version="1.0.0", services=services)
        assert resp.status == "degraded"
        assert "error" in resp.services["redis"]

    def test_frozen(self) -> None:
        resp = ReadinessResponse(status="ready", version="1.0.0", services={})
        with pytest.raises(ValidationError):
            resp.status = "down"  # type: ignore[misc]


class TestServiceStatus:
    """Tests for ServiceStatus constants."""

    def test_ok_constant(self) -> None:
        assert ServiceStatus.OK == "ok"
