"""Tests for RedisCache — CRUD operations and health check."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.cache.redis import RedisCache


@pytest.fixture()
def mock_settings() -> MagicMock:
    settings = MagicMock()
    settings.REDIS_URL = "redis://localhost:6379/0"
    return settings


@pytest.fixture()
def cache(mock_settings: MagicMock) -> RedisCache:
    return RedisCache(mock_settings, prefix="test", default_ttl=60)


class TestMakeKey:
    def test_prefix_applied(self, cache: RedisCache) -> None:
        assert cache._make_key("foo") == "test:foo"

    def test_nested_key(self, cache: RedisCache) -> None:
        assert cache._make_key("user:123") == "test:user:123"


@pytest.mark.asyncio()
class TestGetSetDelete:
    async def test_get_returns_none_for_missing(self, cache: RedisCache) -> None:
        cache._client = AsyncMock()
        cache._client.get = AsyncMock(return_value=None)
        result = await cache.get("missing")
        assert result is None

    async def test_get_deserializes_json(self, cache: RedisCache) -> None:
        cache._client = AsyncMock()
        cache._client.get = AsyncMock(return_value=json.dumps({"a": 1}))
        result = await cache.get("key")
        assert result == {"a": 1}

    async def test_get_returns_raw_for_non_json(self, cache: RedisCache) -> None:
        cache._client = AsyncMock()
        cache._client.get = AsyncMock(return_value="plain string")
        result = await cache.get("key")
        assert result == "plain string"

    async def test_set_serializes_json(self, cache: RedisCache) -> None:
        cache._client = AsyncMock()
        cache._client.set = AsyncMock()
        await cache.set("key", {"x": 42}, ttl=120)
        cache._client.set.assert_awaited_once_with(
            "test:key", json.dumps({"x": 42}, default=str), ex=120
        )

    async def test_set_uses_default_ttl(self, cache: RedisCache) -> None:
        cache._client = AsyncMock()
        cache._client.set = AsyncMock()
        await cache.set("key", "val")
        cache._client.set.assert_awaited_once_with("test:key", json.dumps("val", default=str), ex=60)

    async def test_delete_returns_true_when_existed(self, cache: RedisCache) -> None:
        cache._client = AsyncMock()
        cache._client.delete = AsyncMock(return_value=1)
        assert await cache.delete("key") is True

    async def test_delete_returns_false_when_missing(self, cache: RedisCache) -> None:
        cache._client = AsyncMock()
        cache._client.delete = AsyncMock(return_value=0)
        assert await cache.delete("key") is False


@pytest.mark.asyncio()
class TestExistsExpire:
    async def test_exists_true(self, cache: RedisCache) -> None:
        cache._client = AsyncMock()
        cache._client.exists = AsyncMock(return_value=1)
        assert await cache.exists("key") is True

    async def test_exists_false(self, cache: RedisCache) -> None:
        cache._client = AsyncMock()
        cache._client.exists = AsyncMock(return_value=0)
        assert await cache.exists("key") is False

    async def test_expire(self, cache: RedisCache) -> None:
        cache._client = AsyncMock()
        cache._client.expire = AsyncMock(return_value=True)
        assert await cache.expire("key", 300) is True


@pytest.mark.asyncio()
class TestHealthCheck:
    async def test_success(self, cache: RedisCache) -> None:
        cache._client = AsyncMock()
        cache._client.ping = AsyncMock(return_value=True)
        assert await cache.health_check() is True

    async def test_failure(self, cache: RedisCache) -> None:
        cache._client = AsyncMock()
        cache._client.ping = AsyncMock(side_effect=ConnectionError("down"))
        assert await cache.health_check() is False
