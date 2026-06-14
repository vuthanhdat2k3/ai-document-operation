"""Tests for global exception handlers and error response format."""

from __future__ import annotations

from unittest.mock import patch

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
    register_exception_handlers,
)
from app.api.middleware.request_id import RequestIDMiddleware


def _build_error_app() -> FastAPI:
    """Create a minimal FastAPI app with error handlers and test routes."""
    app = FastAPI()
    register_exception_handlers(app)
    app.add_middleware(RequestIDMiddleware)

    @app.get("/err/app")
    async def raise_app() -> None:
        raise AppError("Something broke")

    @app.get("/err/not-found")
    async def raise_not_found() -> None:
        raise NotFoundError("Document doc_123 not found")

    @app.get("/err/validation")
    async def raise_validation() -> None:
        raise ValidationErrorDetail("Field 'title' is required")

    @app.get("/err/rate-limit")
    async def raise_rate_limit() -> None:
        raise RateLimitError("Rate limit exceeded")

    @app.get("/err/unauthorized")
    async def raise_unauthorized() -> None:
        raise UnauthorizedError("Token expired")

    @app.get("/err/forbidden")
    async def raise_forbidden() -> None:
        raise ForbiddenError("Admin role required")

    @app.get("/err/unhandled")
    async def raise_unhandled() -> None:
        raise RuntimeError("unexpected boom")

    return app


@pytest.fixture()
async def err_client() -> AsyncClient:
    app = _build_error_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestErrorResponseFormat:
    """Verify the structured error envelope matches the API spec."""

    @pytest.mark.asyncio()
    async def test_error_envelope_has_nested_error_object(
        self, err_client: AsyncClient
    ) -> None:
        body = (await err_client.get("/err/not-found")).json()
        assert "error" in body
        err = body["error"]
        assert "code" in err
        assert "message" in err
        assert "request_id" in err
        assert "timestamp" in err

    @pytest.mark.asyncio()
    async def test_timestamp_is_iso8601(self, err_client: AsyncClient) -> None:
        from datetime import datetime

        body = (await err_client.get("/err/app")).json()
        ts = body["error"]["timestamp"]
        parsed = datetime.fromisoformat(ts)
        assert parsed.tzinfo is not None


class TestNotFoundError:
    @pytest.mark.asyncio()
    async def test_status_404(self, err_client: AsyncClient) -> None:
        assert (await err_client.get("/err/not-found")).status_code == 404

    @pytest.mark.asyncio()
    async def test_code_not_found(self, err_client: AsyncClient) -> None:
        body = (await err_client.get("/err/not-found")).json()
        assert body["error"]["code"] == "NOT_FOUND"


class TestUnauthorizedError:
    @pytest.mark.asyncio()
    async def test_status_401(self, err_client: AsyncClient) -> None:
        assert (await err_client.get("/err/unauthorized")).status_code == 401

    @pytest.mark.asyncio()
    async def test_code_unauthorized(self, err_client: AsyncClient) -> None:
        body = (await err_client.get("/err/unauthorized")).json()
        assert body["error"]["code"] == "UNAUTHORIZED"


class TestForbiddenError:
    @pytest.mark.asyncio()
    async def test_status_403(self, err_client: AsyncClient) -> None:
        assert (await err_client.get("/err/forbidden")).status_code == 403

    @pytest.mark.asyncio()
    async def test_code_forbidden(self, err_client: AsyncClient) -> None:
        body = (await err_client.get("/err/forbidden")).json()
        assert body["error"]["code"] == "FORBIDDEN"


class TestValidationError:
    @pytest.mark.asyncio()
    async def test_status_422(self, err_client: AsyncClient) -> None:
        assert (await err_client.get("/err/validation")).status_code == 422

    @pytest.mark.asyncio()
    async def test_code_unprocessable_entity(self, err_client: AsyncClient) -> None:
        body = (await err_client.get("/err/validation")).json()
        assert body["error"]["code"] == "UNPROCESSABLE_ENTITY"


class TestRateLimitError:
    @pytest.mark.asyncio()
    async def test_status_429(self, err_client: AsyncClient) -> None:
        assert (await err_client.get("/err/rate-limit")).status_code == 429

    @pytest.mark.asyncio()
    async def test_code_rate_limit_exceeded(self, err_client: AsyncClient) -> None:
        body = (await err_client.get("/err/rate-limit")).json()
        assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"


class TestUnhandledException:
    @pytest.mark.asyncio()
    async def test_status_500(self, err_client: AsyncClient) -> None:
        assert (await err_client.get("/err/unhandled")).status_code == 500

    @pytest.mark.asyncio()
    async def test_code_internal_error(self, err_client: AsyncClient) -> None:
        body = (await err_client.get("/err/unhandled")).json()
        assert body["error"]["code"] == "INTERNAL_ERROR"

    @pytest.mark.asyncio()
    async def test_does_not_leak_details(self, err_client: AsyncClient) -> None:
        body = (await err_client.get("/err/unhandled")).json()
        assert "boom" not in body["error"]["message"]


class TestRequestIDInErrors:
    @pytest.mark.asyncio()
    async def test_custom_request_id_propagated(self, err_client: AsyncClient) -> None:
        resp = await err_client.get(
            "/err/not-found", headers={"X-Request-ID": "trace-999"}
        )
        assert resp.headers["x-request-id"] == "trace-999"
        assert resp.json()["error"]["request_id"] == "trace-999"

    @pytest.mark.asyncio()
    async def test_generated_request_id_propagated(
        self, err_client: AsyncClient
    ) -> None:
        resp = await err_client.get("/err/not-found")
        rid = resp.headers.get("x-request-id")
        assert rid is not None
        assert resp.json()["error"]["request_id"] == rid
