"""Tests for QdrantClientWrapper — connection and collection management."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.vector.client import QdrantClientWrapper


@pytest.fixture()
def mock_settings() -> MagicMock:
    settings = MagicMock()
    settings.QDRANT_URL = "http://localhost:6333"
    settings.QDRANT_API_KEY = None
    return settings


@pytest.fixture()
def wrapper(mock_settings: MagicMock) -> QdrantClientWrapper:
    return QdrantClientWrapper(mock_settings)


class TestHeaders:
    def test_no_api_key(self, wrapper: QdrantClientWrapper) -> None:
        headers = wrapper._headers()
        assert "api-key" not in headers
        assert headers["Content-Type"] == "application/json"

    def test_with_api_key(self, mock_settings: MagicMock) -> None:
        mock_settings.QDRANT_API_KEY = "secret"
        w = QdrantClientWrapper(mock_settings)
        headers = w._headers()
        assert headers["api-key"] == "secret"


@pytest.mark.asyncio()
class TestHealthCheck:
    async def test_success(self, wrapper: QdrantClientWrapper) -> None:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        wrapper._client = mock_client

        assert await wrapper.health_check() is True

    async def test_failure(self, wrapper: QdrantClientWrapper) -> None:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=ConnectionError("refused"))
        mock_client.is_closed = False
        wrapper._client = mock_client

        assert await wrapper.health_check() is False


@pytest.mark.asyncio()
class TestCreateCollection:
    async def test_create_dense_only(self, wrapper: QdrantClientWrapper) -> None:
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": True}
        mock_client.put = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        wrapper._client = mock_client

        result = await wrapper.create_collection(
            "test_col", vectors_config={"dense": {"size": 1024, "distance": "Cosine"}}
        )
        assert result == {"result": True}

    async def test_create_with_sparse(self, wrapper: QdrantClientWrapper) -> None:
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": True}
        mock_client.put = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        wrapper._client = mock_client

        result = await wrapper.create_collection(
            "test_col",
            vectors_config={"dense": {"size": 1024, "distance": "Cosine"}},
            sparse_vectors_config={"sparse": {"index": {"on_disk": False}}},
        )
        assert result == {"result": True}


@pytest.mark.asyncio()
class TestDeleteCollection:
    async def test_delete(self, wrapper: QdrantClientWrapper) -> None:
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": True}
        mock_client.delete = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        wrapper._client = mock_client

        result = await wrapper.delete_collection("test_col")
        assert result == {"result": True}


@pytest.mark.asyncio()
class TestListCollections:
    async def test_list(self, wrapper: QdrantClientWrapper) -> None:
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {"collections": [{"name": "col_a"}, {"name": "col_b"}]}
        }
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        wrapper._client = mock_client

        names = await wrapper.list_collections()
        assert names == ["col_a", "col_b"]


@pytest.mark.asyncio()
class TestCollectionExists:
    async def test_exists(self, wrapper: QdrantClientWrapper) -> None:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        wrapper._client = mock_client

        assert await wrapper.collection_exists("test_col") is True

    async def test_not_exists(self, wrapper: QdrantClientWrapper) -> None:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        wrapper._client = mock_client

        assert await wrapper.collection_exists("test_col") is False


@pytest.mark.asyncio()
class TestClose:
    async def test_close(self, wrapper: QdrantClientWrapper) -> None:
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.aclose = AsyncMock()
        wrapper._client = mock_client

        await wrapper.close()
        mock_client.aclose.assert_awaited_once()
        assert wrapper._client is None
