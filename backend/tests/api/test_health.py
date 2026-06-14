"""Tests for /health and /ready admin endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


class TestHealthEndpoint:
    """Tests for GET /api/v1/health."""

    async def test_returns_200(self, test_client: AsyncClient) -> None:
        resp = await test_client.get("/api/v1/health")
        assert resp.status_code == 200

    async def test_status_ok(self, test_client: AsyncClient) -> None:
        data = (await test_client.get("/api/v1/health")).json()
        assert data["status"] == "ok"

    async def test_version_present(self, test_client: AsyncClient) -> None:
        data = (await test_client.get("/api/v1/health")).json()
        assert data["version"] == "1.0.0"

    async def test_timestamp_present(self, test_client: AsyncClient) -> None:
        data = (await test_client.get("/api/v1/health")).json()
        assert "timestamp" in data
        assert isinstance(data["timestamp"], str)
        assert len(data["timestamp"]) > 0

    async def test_response_shape(self, test_client: AsyncClient) -> None:
        data = (await test_client.get("/api/v1/health")).json()
        assert set(data.keys()) == {"status", "version", "timestamp"}


class TestReadinessEndpoint:
    """Tests for GET /api/v1/ready."""

    async def test_returns_200_when_all_ok(self, test_client: AsyncClient) -> None:
        with patch(
            "app.api.v1.admin._check_postgres", new_callable=AsyncMock, return_value="ok"
        ), patch(
            "app.api.v1.admin._check_redis", new_callable=AsyncMock, return_value="ok"
        ), patch(
            "app.api.v1.admin._check_qdrant", new_callable=AsyncMock, return_value="ok"
        ), patch(
            "app.api.v1.admin._check_minio", new_callable=AsyncMock, return_value="ok"
        ):
            resp = await test_client.get("/api/v1/ready")
            assert resp.status_code == 200

    async def test_status_ready_when_all_ok(self, test_client: AsyncClient) -> None:
        with patch(
            "app.api.v1.admin._check_postgres", new_callable=AsyncMock, return_value="ok"
        ), patch(
            "app.api.v1.admin._check_redis", new_callable=AsyncMock, return_value="ok"
        ), patch(
            "app.api.v1.admin._check_qdrant", new_callable=AsyncMock, return_value="ok"
        ), patch(
            "app.api.v1.admin._check_minio", new_callable=AsyncMock, return_value="ok"
        ):
            data = (await test_client.get("/api/v1/ready")).json()
            assert data["status"] == "ready"

    async def test_status_degraded_when_service_down(self, test_client: AsyncClient) -> None:
        with patch(
            "app.api.v1.admin._check_postgres", new_callable=AsyncMock, return_value="ok"
        ), patch(
            "app.api.v1.admin._check_redis",
            new_callable=AsyncMock,
            return_value="error: connection refused",
        ), patch(
            "app.api.v1.admin._check_qdrant", new_callable=AsyncMock, return_value="ok"
        ), patch(
            "app.api.v1.admin._check_minio", new_callable=AsyncMock, return_value="ok"
        ):
            data = (await test_client.get("/api/v1/ready")).json()
            assert data["status"] == "degraded"

    async def test_services_in_response(self, test_client: AsyncClient) -> None:
        with patch(
            "app.api.v1.admin._check_postgres", new_callable=AsyncMock, return_value="ok"
        ), patch(
            "app.api.v1.admin._check_redis", new_callable=AsyncMock, return_value="ok"
        ), patch(
            "app.api.v1.admin._check_qdrant", new_callable=AsyncMock, return_value="ok"
        ), patch(
            "app.api.v1.admin._check_minio", new_callable=AsyncMock, return_value="ok"
        ):
            data = (await test_client.get("/api/v1/ready")).json()
            assert "services" in data
            assert "postgres" in data["services"]
            assert "redis" in data["services"]
            assert "qdrant" in data["services"]
            assert "minio" in data["services"]

    async def test_version_in_response(self, test_client: AsyncClient) -> None:
        with patch(
            "app.api.v1.admin._check_postgres", new_callable=AsyncMock, return_value="ok"
        ), patch(
            "app.api.v1.admin._check_redis", new_callable=AsyncMock, return_value="ok"
        ), patch(
            "app.api.v1.admin._check_qdrant", new_callable=AsyncMock, return_value="ok"
        ), patch(
            "app.api.v1.admin._check_minio", new_callable=AsyncMock, return_value="ok"
        ):
            data = (await test_client.get("/api/v1/ready")).json()
            assert data["version"] == "1.0.0"

    async def test_multiple_services_degraded(self, test_client: AsyncClient) -> None:
        with patch(
            "app.api.v1.admin._check_postgres",
            new_callable=AsyncMock,
            return_value="error: down",
        ), patch(
            "app.api.v1.admin._check_redis",
            new_callable=AsyncMock,
            return_value="error: timeout",
        ), patch(
            "app.api.v1.admin._check_qdrant", new_callable=AsyncMock, return_value="ok"
        ), patch(
            "app.api.v1.admin._check_minio", new_callable=AsyncMock, return_value="ok"
        ):
            data = (await test_client.get("/api/v1/ready")).json()
            assert data["status"] == "degraded"
            assert "error" in data["services"]["postgres"]
            assert "error" in data["services"]["redis"]
