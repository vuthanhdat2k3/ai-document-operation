"""Tests for the X-Request-ID ASGI middleware."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


class TestRequestIDMiddleware:
    """Tests for RequestIDMiddleware behavior."""

    async def test_response_has_request_id_header(self, test_client: AsyncClient) -> None:
        resp = await test_client.get("/api/v1/health")
        assert "x-request-id" in resp.headers

    async def test_request_id_is_uuid4(self, test_client: AsyncClient) -> None:
        resp = await test_client.get("/api/v1/health")
        request_id = resp.headers["x-request-id"]
        parsed = uuid.UUID(request_id, version=4)
        assert parsed.version == 4

    async def test_client_provided_request_id_preserved(self, test_client: AsyncClient) -> None:
        custom_id = "my-custom-request-id-12345"
        resp = await test_client.get("/api/v1/health", headers={"X-Request-ID": custom_id})
        assert resp.headers["x-request-id"] == custom_id

    async def test_different_requests_get_different_ids(self, test_client: AsyncClient) -> None:
        r1 = await test_client.get("/api/v1/health")
        r2 = await test_client.get("/api/v1/health")
        id1 = r1.headers["x-request-id"]
        id2 = r2.headers["x-request-id"]
        assert id1 != id2

    async def test_request_id_present_on_error_responses(self, test_client: AsyncClient) -> None:
        resp = await test_client.get("/api/v1/nonexistent")
        assert "x-request-id" in resp.headers
