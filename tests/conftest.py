"""Shared test fixtures for the backend test suite."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings


@pytest.fixture()
def test_settings() -> Settings:
    """Return deterministic test settings."""
    return Settings(
        DEBUG=True,
        LOG_LEVEL="DEBUG",
        DATABASE_URL="postgresql+asyncpg://test:test@localhost:5432/test",
        REDIS_URL="redis://localhost:6379/0",
        QDRANT_URL="http://localhost:6333",
        MINIO_ENDPOINT="localhost:9000",
        MINIO_ACCESS_KEY="test",
        MINIO_SECRET_KEY="test",
        CORS_ORIGINS="http://localhost:3000",
    )


@pytest.fixture()
def mock_db_session() -> AsyncMock:
    """Return a mocked async database session."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=MagicMock())
    return session


@pytest.fixture()
async def app_client(test_settings: Settings) -> AsyncGenerator[AsyncClient, None]:
    """Return an async HTTP client wired to a fresh test app instance."""
    from app.main import create_app

    with patch("app.config.get_settings", return_value=test_settings):
        application = create_app(test_settings)
        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
