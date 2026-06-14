"""Tests for global exception handlers (error_handler middleware)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.middleware.error_handler import (
    AppError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    UnauthorizedError,
    ValidationErrorDetail,
    _build_error_response,
    _get_request_id,
    register_exception_handlers,
)


class TestErrorClasses:
    """Verify custom error class attributes."""

    def test_app_error_defaults(self) -> None:
        e = AppError()
        assert e.status_code == 500
        assert e.code == "INTERNAL_ERROR"
        assert "unexpected error" in e.message.lower()

    def test_app_error_custom_message(self) -> None:
        e = AppError(message="custom error")
        assert e.message == "custom error"

    def test_not_found_error(self) -> None:
        e = NotFoundError()
        assert e.status_code == 404
        assert e.code == "NOT_FOUND"

    def test_not_found_custom_message(self) -> None:
        e = NotFoundError(message="Document not found")
        assert e.message == "Document not found"

    def test_validation_error_detail(self) -> None:
        e = ValidationErrorDetail()
        assert e.status_code == 422
        assert e.code == "UNPROCESSABLE_ENTITY"

    def test_rate_limit_error(self) -> None:
        e = RateLimitError()
        assert e.status_code == 429
        assert e.code == "RATE_LIMIT_EXCEEDED"

    def test_unauthorized_error(self) -> None:
        e = UnauthorizedError()
        assert e.status_code == 401
        assert e.code == "UNAUTHORIZED"

    def test_forbidden_error(self) -> None:
        e = ForbiddenError()
        assert e.status_code == 403
        assert e.code == "FORBIDDEN"

    def test_errors_are_exceptions(self) -> None:
        for cls in (
            AppError, NotFoundError, ValidationErrorDetail,
            RateLimitError, UnauthorizedError, ForbiddenError,
        ):
            assert issubclass(cls, Exception)

    def test_inheritance_chain(self) -> None:
        assert issubclass(NotFoundError, AppError)
        assert issubclass(RateLimitError, AppError)
        assert issubclass(UnauthorizedError, AppError)
        assert issubclass(ForbiddenError, AppError)
        assert issubclass(ValidationErrorDetail, AppError)


class TestBuildErrorResponse:
    """Verify _build_error_response helper."""

    def test_basic_structure(self) -> None:
        resp = _build_error_response(
            code="NOT_FOUND",
            message="Not found.",
            request_id="req-1",
            status_code=404,
        )
        assert "error" in resp
        assert resp["error"]["code"] == "NOT_FOUND"
        assert resp["error"]["message"] == "Not found."
        assert resp["error"]["request_id"] == "req-1"
        assert "timestamp" in resp["error"]

    def test_with_details(self) -> None:
        details = [{"field": "email", "issue": "invalid"}]
        resp = _build_error_response(
            code="UNPROCESSABLE_ENTITY",
            message="Validation failed.",
            request_id="req-2",
            status_code=422,
            details=details,
        )
        assert resp["error"]["details"] == details  # type: ignore[index]

    def test_without_details(self) -> None:
        resp = _build_error_response(
            code="ERR", message="msg", request_id="r1", status_code=500
        )
        assert "details" not in resp["error"]

    def test_none_details_omitted(self) -> None:
        resp = _build_error_response(
            code="ERR", message="msg", request_id="r1", status_code=500, details=None
        )
        assert "details" not in resp["error"]


class TestGetRequestId:
    """Verify _get_request_id helper."""

    def test_with_state(self) -> None:
        request = MagicMock()
        request.state.request_id = "test-id"
        assert _get_request_id(request) == "test-id"

    def test_without_request_id_attr(self) -> None:
        request = MagicMock(spec=[])
        request.state = MagicMock(spec=[])
        assert _get_request_id(request) == "unknown"


class TestErrorHandlersIntegration:
    """Integration tests for exception handlers via HTTP."""

    async def test_app_error_returns_structured_response(self) -> None:
        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/not-found")
        async def trigger_not_found() -> None:
            raise NotFoundError("Item missing")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/not-found")
        assert resp.status_code == 404
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == "NOT_FOUND"
        assert data["error"]["message"] == "Item missing"
        assert "request_id" in data["error"]
        assert "timestamp" in data["error"]

    async def test_rate_limit_error(self) -> None:
        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/rate-limited")
        async def trigger_rate_limit() -> None:
            raise RateLimitError()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/rate-limited")
        assert resp.status_code == 429
        data = resp.json()
        assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"

    async def test_unhandled_exception_returns_500(self) -> None:
        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/crash")
        async def trigger_crash() -> None:
            raise AppError("unexpected failure")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/crash")
        assert resp.status_code == 500
        data = resp.json()
        assert data["error"]["code"] == "INTERNAL_ERROR"

    async def test_app_error_with_request_id_header(self) -> None:
        from app.api.middleware.request_id import RequestIDMiddleware

        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)
        register_exception_handlers(app)

        @app.get("/err")
        async def trigger_err() -> None:
            raise AppError("test error")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/err", headers={"X-Request-ID": "my-id"})
        data = resp.json()
        assert data["error"]["request_id"] == "my-id"

    async def test_error_without_request_id_defaults_unknown(self) -> None:
        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/err")
        async def trigger_err() -> None:
            raise AppError("test error")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/err")
        data = resp.json()
        assert data["error"]["request_id"] == "unknown"

    async def test_raw_404_has_detail(self, test_client: AsyncClient) -> None:
        resp = await test_client.get("/api/v1/nonexistent")
        assert resp.status_code == 404
