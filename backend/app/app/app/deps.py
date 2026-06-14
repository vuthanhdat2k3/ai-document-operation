"""Dependency injection providers for FastAPI."""

from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.session import get_db
from app.llm.base import LLMProvider


async def get_llm(
    settings: Settings = Depends(get_settings),
) -> LLMProvider:
    """Return an LLM provider based on settings.

    Args:
        settings: Application settings with LLM configuration.

    Returns:
        Configured LLMProvider instance.
    """
    from app.llm.factory import get_llm_provider
    return get_llm_provider(settings)


async def get_redis(
    settings: Settings = Depends(get_settings),
) -> AsyncGenerator[aioredis.Redis, None]:
    """Yield an async Redis client for dependency injection.

    Args:
        settings: Application settings containing the Redis URL.

    Yields:
        An async Redis client instance.
    """
    client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


async def get_qdrant(
    settings: Settings = Depends(get_settings),
) -> AsyncGenerator["QdrantClient", None]:
    """Yield a Qdrant client for dependency injection.

    Args:
        settings: Application settings containing Qdrant connection info.

    Yields:
        A QdrantClient instance.
    """
    from qdrant_client import QdrantClient

    client = QdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
    )
    try:
        yield client
    finally:
        client.close()


async def get_minio(
    settings: Settings = Depends(get_settings),
) -> AsyncGenerator["Minio", None]:
    """Yield a MinIO client for dependency injection.

    Args:
        settings: Application settings containing MinIO connection info.

    Yields:
        A Minio client instance.
    """
    from minio import Minio

    client = Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_USE_SSL,
    )
    yield client
