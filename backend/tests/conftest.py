"""Shared test fixtures for the AI Document Operations Agent test suite."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
os.environ.setdefault("MINIO_ACCESS_KEY", "test")
os.environ.setdefault("MINIO_SECRET_KEY", "test")
os.environ.setdefault("DEBUG", "true")

from app.config import Settings


@pytest.fixture()
def test_settings() -> Settings:
    """Create a Settings instance with test-safe defaults."""
    return Settings(
        APP_NAME="test-app",
        DEBUG=True,
        LOG_LEVEL="DEBUG",
        DATABASE_URL="postgresql+asyncpg://test:test@localhost:5432/test",
        DB_POOL_SIZE=5,
        DB_MAX_OVERFLOW=2,
        DB_ECHO=False,
        REDIS_URL="redis://localhost:6379/0",
        QDRANT_URL="http://localhost:6333",
        QDRANT_API_KEY=None,
        MINIO_ENDPOINT="localhost:9000",
        MINIO_ACCESS_KEY="test",
        MINIO_SECRET_KEY="test",
        MINIO_BUCKET="test-bucket",
        MINIO_USE_SSL=False,
        OPENAI_API_KEY=None,
        CORS_ORIGINS="http://localhost:3000",
    )


@pytest.fixture()
def mock_db_session() -> AsyncMock:
    """Create a mock SQLAlchemy AsyncSession."""
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock())
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture()
async def test_client(test_settings: Settings) -> AsyncGenerator[AsyncClient, None]:
    """Create an httpx AsyncClient bound to the FastAPI app with mocked lifespan."""
    from app.main import create_app

    app = create_app(settings=test_settings)

    with patch("app.main._init_db", new_callable=AsyncMock), patch(
        "app.main._init_vector_store", new_callable=AsyncMock
    ), patch("app.main._warm_up_models", new_callable=AsyncMock), patch(
        "app.main._shutdown_db", new_callable=AsyncMock
    ), patch(
        "app.main._shutdown_vector_store", new_callable=AsyncMock
    ), patch(
        "app.main._flush_telemetry", new_callable=AsyncMock
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.fixture()
def mock_redis_client() -> AsyncMock:
    """Create a mock async Redis client."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    client.exists = AsyncMock(return_value=0)
    client.expire = AsyncMock(return_value=True)
    client.ping = AsyncMock(return_value=True)
    client.aclose = AsyncMock()
    return client


@pytest.fixture()
def mock_qdrant_httpx_client() -> AsyncMock:
    """Create a mock httpx.AsyncClient for Qdrant wrapper."""
    client = AsyncMock()
    client.is_closed = False
    response_ok = MagicMock()
    response_ok.status_code = 200
    response_ok.json.return_value = {"status": "ok", "result": {}}
    response_ok.raise_for_status = MagicMock()
    client.get = AsyncMock(return_value=response_ok)
    client.put = AsyncMock(return_value=response_ok)
    client.delete = AsyncMock(return_value=response_ok)
    client.aclose = AsyncMock()
    return client
