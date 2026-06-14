"""Unit tests for RedisCache with mocked redis.asyncio."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.cache.redis import DEFAULT_PREFIX, DEFAULT_TTL, RedisCache


@pytest.fixture()
def mock_settings() -> MagicMock:
    settings = MagicMock()
    settings.REDIS_URL = "redis://localhost:6379/0"
    return settings


@pytest.fixture()
def redis_cache(mock_settings: MagicMock) -> RedisCache:
    with patch("app.cache.redis.aioredis.ConnectionPool") as mock_pool_cls, patch(
        "app.cache.redis.aioredis.Redis"
    ) as mock_redis_cls:
        mock_pool = MagicMock()
        mock_pool_cls.from_url.return_value = mock_pool

        mock_client = AsyncMock()
        mock_redis_cls.return_value = mock_client

        cache = RedisCache(settings=mock_settings)
        cache._client = mock_client
        return cache


class TestMakeKey:
    """Verify key prefixing logic."""

    def test_default_prefix(self, redis_cache: RedisCache) -> None:
        assert redis_cache._make_key("foo") == "docops:foo"

    def test_custom_prefix(self, mock_settings: MagicMock) -> None:
        with patch("app.cache.redis.aioredis.ConnectionPool"), patch(
            "app.cache.redis.aioredis.Redis"
        ):
            cache = RedisCache(settings=mock_settings, prefix="myprefix")
            cache._client = AsyncMock()
            assert cache._make_key("bar") == "myprefix:bar"

    def test_empty_key(self, redis_cache: RedisCache) -> None:
        assert redis_cache._make_key("") == "docops:"


class TestGet:
    """Tests for RedisCache.get."""

    async def test_get_existing_json(self, redis_cache: RedisCache) -> None:
        redis_cache._client.get = AsyncMock(return_value='{"key": "value"}')
        result = await redis_cache.get("test")
        assert result == {"key": "value"}

    async def test_get_nonexistent(self, redis_cache: RedisCache) -> None:
        redis_cache._client.get = AsyncMock(return_value=None)
        result = await redis_cache.get("missing")
        assert result is None

    async def test_get_raw_string(self, redis_cache: RedisCache) -> None:
        redis_cache._client.get = AsyncMock(return_value="not-json")
        result = await redis_cache.get("raw")
        assert result == "not-json"

    async def test_get_uses_prefixed_key(self, redis_cache: RedisCache) -> None:
        redis_cache._client.get = AsyncMock(return_value=None)
        await redis_cache.get("mykey")
        redis_cache._client.get.assert_called_once_with("docops:mykey")


class TestSet:
    """Tests for RedisCache.set."""

    async def test_set_json_value(self, redis_cache: RedisCache) -> None:
        redis_cache._client.set = AsyncMock()
        await redis_cache.set("key", {"a": 1})
        redis_cache._client.set.assert_called_once()
        call_args = redis_cache._client.set.call_args
        assert call_args[0][0] == "docops:key"
        assert json.loads(call_args[0][1]) == {"a": 1}

    async def test_set_with_custom_ttl(self, redis_cache: RedisCache) -> None:
        redis_cache._client.set = AsyncMock()
        await redis_cache.set("key", "val", ttl=60)
        call_args = redis_cache._client.set.call_args
        assert call_args[1]["ex"] == 60

    async def test_set_uses_default_ttl(self, redis_cache: RedisCache) -> None:
        redis_cache._client.set = AsyncMock()
        await redis_cache.set("key", "val")
        call_args = redis_cache._client.set.call_args
        assert call_args[1]["ex"] == DEFAULT_TTL

    async def test_set_list_value(self, redis_cache: RedisCache) -> None:
        redis_cache._client.set = AsyncMock()
        await redis_cache.set("key", [1, 2, 3])
        call_args = redis_cache._client.set.call_args
        assert json.loads(call_args[0][1]) == [1, 2, 3]


class TestDelete:
    """Tests for RedisCache.delete."""

    async def test_delete_existing(self, redis_cache: RedisCache) -> None:
        redis_cache._client.delete = AsyncMock(return_value=1)
        result = await redis_cache.delete("key")
        assert result is True

    async def test_delete_nonexistent(self, redis_cache: RedisCache) -> None:
        redis_cache._client.delete = AsyncMock(return_value=0)
        result = await redis_cache.delete("key")
        assert result is False

    async def test_delete_uses_prefixed_key(self, redis_cache: RedisCache) -> None:
        redis_cache._client.delete = AsyncMock(return_value=1)
        await redis_cache.delete("mykey")
        redis_cache._client.delete.assert_called_once_with("docops:mykey")


class TestExists:
    """Tests for RedisCache.exists."""

    async def test_exists_true(self, redis_cache: RedisCache) -> None:
        redis_cache._client.exists = AsyncMock(return_value=1)
        result = await redis_cache.exists("key")
        assert result is True

    async def test_exists_false(self, redis_cache: RedisCache) -> None:
        redis_cache._client.exists = AsyncMock(return_value=0)
        result = await redis_cache.exists("key")
        assert result is False


class TestExpire:
    """Tests for RedisCache.expire."""

    async def test_expire_success(self, redis_cache: RedisCache) -> None:
        redis_cache._client.expire = AsyncMock(return_value=True)
        result = await redis_cache.expire("key", 300)
        assert result is True

    async def test_expire_failure(self, redis_cache: RedisCache) -> None:
        redis_cache._client.expire = AsyncMock(return_value=False)
        result = await redis_cache.expire("key", 300)
        assert result is False


class TestHealthCheck:
    """Tests for RedisCache.health_check."""

    async def test_healthy(self, redis_cache: RedisCache) -> None:
        redis_cache._client.ping = AsyncMock(return_value=True)
        assert await redis_cache.health_check() is True

    async def test_unhealthy(self, redis_cache: RedisCache) -> None:
        redis_cache._client.ping = AsyncMock(side_effect=ConnectionError("refused"))
        assert await redis_cache.health_check() is False


class TestClose:
    """Tests for RedisCache.close."""

    async def test_close(self, redis_cache: RedisCache) -> None:
        redis_cache._client.aclose = AsyncMock()
        redis_cache._pool = AsyncMock()
        redis_cache._pool.disconnect = AsyncMock()
        await redis_cache.close()
        redis_cache._client.aclose.assert_called_once()
        redis_cache._pool.disconnect.assert_called_once()


class TestConstants:
    """Verify module-level constants."""

    def test_default_prefix(self) -> None:
        assert DEFAULT_PREFIX == "docops"

    def test_default_ttl(self) -> None:
        assert DEFAULT_TTL == 3600
