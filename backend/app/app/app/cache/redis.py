"""Async Redis cache client with JSON serialization and key prefix support."""

from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.config import Settings

logger = logging.getLogger(__name__)

DEFAULT_PREFIX = "docops"
DEFAULT_TTL = 3600


class RedisCache:
    """Async Redis cache wrapper with connection pooling, key prefix, and JSON serialization.

    Args:
        settings: Application settings containing REDIS_URL.
        prefix: Key prefix namespace (default ``"docops"``).
        default_ttl: Default TTL in seconds for cached entries.
    """

    def __init__(
        self,
        settings: Settings,
        prefix: str = DEFAULT_PREFIX,
        default_ttl: int = DEFAULT_TTL,
    ) -> None:
        self._prefix = prefix
        self._default_ttl = default_ttl
        self._pool: aioredis.ConnectionPool = aioredis.ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=20,
            decode_responses=True,
        )
        self._client: aioredis.Redis[str] = aioredis.Redis(connection_pool=self._pool)

    def _make_key(self, key: str) -> str:
        """Prefix a key with the configured namespace.

        Args:
            key: The raw cache key.

        Returns:
            Prefixed key string.
        """
        return f"{self._prefix}:{key}"

    async def get(self, key: str) -> Any | None:
        """Retrieve a JSON-deserialized value from cache.

        Args:
            key: Cache key (prefix is applied automatically).

        Returns:
            Deserialized value or ``None`` if the key does not exist.
        """
        raw = await self._client.get(self._make_key(key))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """Store a JSON-serialized value in cache.

        Args:
            key: Cache key (prefix is applied automatically).
            value: Any JSON-serializable Python object.
            ttl: Time-to-live in seconds. Uses default_ttl when ``None``.
        """
        serialized = json.dumps(value, default=str)
        effective_ttl = ttl if ttl is not None else self._default_ttl
        await self._client.set(self._make_key(key), serialized, ex=effective_ttl)

    async def delete(self, key: str) -> bool:
        """Delete a key from cache.

        Args:
            key: Cache key (prefix is applied automatically).

        Returns:
            ``True`` if the key existed and was deleted.
        """
        result = await self._client.delete(self._make_key(key))
        return result > 0

    async def exists(self, key: str) -> bool:
        """Check whether a key exists in cache.

        Args:
            key: Cache key (prefix is applied automatically).

        Returns:
            ``True`` if the key exists.
        """
        return bool(await self._client.exists(self._make_key(key)))

    async def expire(self, key: str, ttl: int) -> bool:
        """Set a new TTL on an existing key.

        Args:
            key: Cache key (prefix is applied automatically).
            ttl: New time-to-live in seconds.

        Returns:
            ``True`` if the timeout was set successfully.
        """
        return bool(await self._client.expire(self._make_key(key), ttl))

    async def health_check(self) -> bool:
        """Ping the Redis server to verify connectivity.

        Returns:
            ``True`` if the server responds with ``PONG``.
        """
        try:
            result = await self._client.ping()
            return bool(result)
        except Exception:
            logger.exception("Redis health check failed")
            return False

    async def close(self) -> None:
        """Close the underlying Redis connection pool."""
        await self._client.aclose()  # type: ignore[union-attr]
        await self._pool.disconnect()
