"""Unit tests for QdrantClientWrapper with mocked httpx."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.vector.client import QdrantClientWrapper


@pytest.fixture()
def mock_settings() -> MagicMock:
    settings = MagicMock()
    settings.QDRANT_URL = "http://localhost:6333"
    settings.QDRANT_API_KEY = None
    return settings


@pytest.fixture()
def mock_settings_with_key() -> MagicMock:
    settings = MagicMock()
    settings.QDRANT_URL = "http://localhost:6333"
    settings.QDRANT_API_KEY = "test-api-key"
    return settings


@pytest.fixture()
def wrapper(mock_settings: MagicMock) -> QdrantClientWrapper:
    return QdrantClientWrapper(settings=mock_settings)


@pytest.fixture()
def wrapper_with_key(mock_settings_with_key: MagicMock) -> QdrantClientWrapper:
    return QdrantClientWrapper(settings=mock_settings_with_key)


def _mock_response(status_code: int = 200, json_data: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    return resp


def _make_mock_client(**overrides: object) -> AsyncMock:
    client = AsyncMock()
    client.is_closed = False
    for k, v in overrides.items():
        setattr(client, k, v)
    return client


class TestHeaders:
    """Verify header construction."""

    def test_headers_without_api_key(self, wrapper: QdrantClientWrapper) -> None:
        headers = wrapper._headers()
        assert headers["Content-Type"] == "application/json"
        assert "api-key" not in headers

    def test_headers_with_api_key(self, wrapper_with_key: QdrantClientWrapper) -> None:
        headers = wrapper_with_key._headers()
        assert headers["api-key"] == "test-api-key"


class TestHealthCheck:
    """Tests for QdrantClientWrapper.health_check."""

    async def test_healthy(self, wrapper: QdrantClientWrapper) -> None:
        mock_client = _make_mock_client(get=AsyncMock(return_value=_mock_response(200)))
        wrapper._client = mock_client
        assert await wrapper.health_check() is True
        mock_client.get.assert_called_once_with("/healthz")

    async def test_unhealthy(self, wrapper: QdrantClientWrapper) -> None:
        mock_client = _make_mock_client(get=AsyncMock(return_value=_mock_response(503)))
        wrapper._client = mock_client
        assert await wrapper.health_check() is False

    async def test_exception_returns_false(self, wrapper: QdrantClientWrapper) -> None:
        mock_client = _make_mock_client(get=AsyncMock(side_effect=ConnectionError("refused")))
        wrapper._client = mock_client
        assert await wrapper.health_check() is False


class TestCreateCollection:
    """Tests for QdrantClientWrapper.create_collection."""

    async def test_create_basic(self, wrapper: QdrantClientWrapper) -> None:
        resp = _mock_response(200, {"status": "ok"})
        mock_client = _make_mock_client(put=AsyncMock(return_value=resp))
        wrapper._client = mock_client

        result = await wrapper.create_collection(
            "test_col", {"size": 384, "distance": "Cosine"}
        )
        mock_client.put.assert_called_once()
        call_args = mock_client.put.call_args
        assert call_args[0][0] == "/collections/test_col"
        assert result == {"status": "ok"}

    async def test_create_with_sparse(self, wrapper: QdrantClientWrapper) -> None:
        resp = _mock_response(200, {"status": "ok"})
        mock_client = _make_mock_client(put=AsyncMock(return_value=resp))
        wrapper._client = mock_client

        await wrapper.create_collection(
            "test_col",
            {"size": 384, "distance": "Cosine"},
            sparse_vectors_config={"text": {"index": {"on_disk": True}}},
        )
        call_args = mock_client.put.call_args
        payload = call_args[1]["json"]
        assert "sparse_vectors" in payload


class TestDeleteCollection:
    """Tests for QdrantClientWrapper.delete_collection."""

    async def test_delete(self, wrapper: QdrantClientWrapper) -> None:
        resp = _mock_response(200, {"status": "ok"})
        mock_client = _make_mock_client(delete=AsyncMock(return_value=resp))
        wrapper._client = mock_client

        result = await wrapper.delete_collection("test_col")
        mock_client.delete.assert_called_once_with("/collections/test_col")
        assert result == {"status": "ok"}


class TestListCollections:
    """Tests for QdrantClientWrapper.list_collections."""

    async def test_list(self, wrapper: QdrantClientWrapper) -> None:
        resp = _mock_response(
            200,
            {"result": {"collections": [{"name": "col1"}, {"name": "col2"}]}},
        )
        mock_client = _make_mock_client(get=AsyncMock(return_value=resp))
        wrapper._client = mock_client

        result = await wrapper.list_collections()
        assert result == ["col1", "col2"]

    async def test_empty_list(self, wrapper: QdrantClientWrapper) -> None:
        resp = _mock_response(200, {"result": {"collections": []}})
        mock_client = _make_mock_client(get=AsyncMock(return_value=resp))
        wrapper._client = mock_client

        result = await wrapper.list_collections()
        assert result == []


class TestCollectionExists:
    """Tests for QdrantClientWrapper.collection_exists."""

    async def test_exists(self, wrapper: QdrantClientWrapper) -> None:
        mock_client = _make_mock_client(get=AsyncMock(return_value=_mock_response(200)))
        wrapper._client = mock_client
        assert await wrapper.collection_exists("col") is True

    async def test_not_exists(self, wrapper: QdrantClientWrapper) -> None:
        mock_client = _make_mock_client(get=AsyncMock(return_value=_mock_response(404)))
        wrapper._client = mock_client
        assert await wrapper.collection_exists("col") is False


class TestGetCollectionInfo:
    """Tests for QdrantClientWrapper.get_collection_info."""

    async def test_get_info(self, wrapper: QdrantClientWrapper) -> None:
        info = {"result": {"vectors_count": 100}}
        mock_client = _make_mock_client(get=AsyncMock(return_value=_mock_response(200, info)))
        wrapper._client = mock_client

        result = await wrapper.get_collection_info("col")
        assert result == info


class TestClose:
    """Tests for QdrantClientWrapper.close."""

    async def test_close_open_client(self, wrapper: QdrantClientWrapper) -> None:
        mock_client = _make_mock_client(aclose=AsyncMock())
        wrapper._client = mock_client
        await wrapper.close()
        mock_client.aclose.assert_called_once()
        assert wrapper._client is None

    async def test_close_already_closed(self, wrapper: QdrantClientWrapper) -> None:
        mock_client = AsyncMock()
        mock_client.is_closed = True
        mock_client.aclose = AsyncMock()
        wrapper._client = mock_client
        await wrapper.close()
        mock_client.aclose.assert_not_called()

    async def test_close_no_client(self, wrapper: QdrantClientWrapper) -> None:
        wrapper._client = None
        await wrapper.close()


class TestGetClient:
    """Tests for lazy client creation."""

    async def test_creates_client_when_none(self, wrapper: QdrantClientWrapper) -> None:
        with patch("app.vector.client.httpx.AsyncClient") as mock_cls:
            mock_instance = AsyncMock()
            mock_instance.is_closed = False
            mock_cls.return_value = mock_instance
            wrapper._client = None
            client = await wrapper._get_client()
            assert client is mock_instance

    async def test_reuses_open_client(self, wrapper: QdrantClientWrapper) -> None:
        mock_client = _make_mock_client()
        wrapper._client = mock_client
        client = await wrapper._get_client()
        assert client is mock_client

    async def test_recreates_closed_client(self, wrapper: QdrantClientWrapper) -> None:
        old_client = AsyncMock()
        old_client.is_closed = True
        wrapper._client = old_client

        with patch("app.vector.client.httpx.AsyncClient") as mock_cls:
            new_client = AsyncMock()
            new_client.is_closed = False
            mock_cls.return_value = new_client
            client = await wrapper._get_client()
            assert client is new_client
