"""Tests for health and readiness endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


class TestHealthEndpoint:
    """GET /api/v1/health"""

    @pytest.mark.asyncio()
    async def test_returns_200(self, app_client: AsyncClient) -> None:
        resp = await app_client.get("/api/v1/health")
        assert resp.status_code == 200

    @pytest.mark.asyncio()
    async def test_body_contains_required_fields(self, app_client: AsyncClient) -> None:
        body = (await app_client.get("/api/v1/health")).json()
        assert body["status"] == "ok"
        assert body["version"] == "1.0.0"
        assert "timestamp" in body

    @pytest.mark.asyncio()
    async def test_timestamp_is_iso8601(self, app_client: AsyncClient) -> None:
        body = (await app_client.get("/api/v1/health")).json()
        ts = body["timestamp"]
        parsed = datetime.fromisoformat(ts)
        assert parsed.tzinfo is not None

    @pytest.mark.asyncio()
    async def test_has_request_id_header(self, app_client: AsyncClient) -> None:
        resp = await app_client.get("/api/v1/health")
        assert "x-request-id" in resp.headers


class TestReadinessEndpoint:
    """GET /api/v1/ready"""

    @pytest.mark.asyncio()
    async def test_returns_200_when_all_services_ok(self, app_client: AsyncClient) -> None:
        with (
            patch("app.api.v1.admin._check_postgres", new_callable=AsyncMock, return_value="ok"),
            patch("app.api.v1.admin._check_redis", new_callable=AsyncMock, return_value="ok"),
            patch("app.api.v1.admin._check_qdrant", new_callable=AsyncMock, return_value="ok"),
            patch("app.api.v1.admin._check_minio", new_callable=AsyncMock, return_value="ok"),
        ):
            resp = await app_client.get("/api/v1/ready")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ready"
        assert body["services"]["postgres"] == "ok"
        assert body["services"]["redis"] == "ok"
        assert body["services"]["qdrant"] == "ok"
        assert body["services"]["minio"] == "ok"

    @pytest.mark.asyncio()
    async def test_returns_degraded_when_one_service_fails(
        self, app_client: AsyncClient
    ) -> None:
        with (
            patch("app.api.v1.admin._check_postgres", new_callable=AsyncMock, return_value="ok"),
            patch(
                "app.api.v1.admin._check_redis",
                new_callable=AsyncMock,
                return_value="error: connection refused",
            ),
            patch("app.api.v1.admin._check_qdrant", new_callable=AsyncMock, return_value="ok"),
            patch("app.api.v1.admin._check_minio", new_callable=AsyncMock, return_value="ok"),
        ):
            resp = await app_client.get("/api/v1/ready")

        body = resp.json()
        assert body["status"] == "degraded"
        assert body["services"]["redis"].startswith("error:")

    @pytest.mark.asyncio()
    async def test_has_request_id_header(self, app_client: AsyncClient) -> None:
        resp = await app_client.get("/api/v1/ready")
        assert "x-request-id" in resp.headers

    @pytest.mark.asyncio()
    async def test_services_dict_has_all_keys(self, app_client: AsyncClient) -> None:
        resp = await app_client.get("/api/v1/ready")
        body = resp.json()
        assert set(body["services"].keys()) == {"postgres", "redis", "qdrant", "minio"}
