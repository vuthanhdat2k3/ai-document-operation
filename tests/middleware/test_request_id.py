"""Tests for X-Request-ID middleware."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


class TestRequestIDMiddleware:
    """Request-ID propagation through the middleware stack."""

    @pytest.mark.asyncio()
    async def test_generates_request_id_when_missing(self, app_client: AsyncClient) -> None:
        resp = await app_client.get("/api/v1/health")
        request_id = resp.headers.get("x-request-id")
        assert request_id is not None
        uuid.UUID(request_id)

    @pytest.mark.asyncio()
    async def test_preserves_client_request_id(self, app_client: AsyncClient) -> None:
        client_id = "my-custom-request-id-123"
        resp = await app_client.get("/api/v1/health", headers={"X-Request-ID": client_id})
        assert resp.headers["x-request-id"] == client_id

    @pytest.mark.asyncio()
    async def test_unique_ids_for_different_requests(self, app_client: AsyncClient) -> None:
        r1 = await app_client.get("/api/v1/health")
        r2 = await app_client.get("/api/v1/health")
        id1 = r1.headers["x-request-id"]
        id2 = r2.headers["x-request-id"]
        assert id1 != id2

    @pytest.mark.asyncio()
    async def test_request_id_present_on_error_responses(self, app_client: AsyncClient) -> None:
        resp = await app_client.get("/api/v1/nonexistent")
        assert "x-request-id" in resp.headers

    @pytest.mark.asyncio()
    async def test_request_id_in_error_body(self, app_client: AsyncClient) -> None:
        custom_id = "trace-abc-123"
        resp = await app_client.get(
            "/api/v1/nonexistent", headers={"X-Request-ID": custom_id}
        )
        body = resp.json()
        assert body["error"]["request_id"] == custom_id
