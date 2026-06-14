"""Tests for collection management helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.vector.collections import (
    DEFAULT_COLLECTION,
    DENSE_VECTOR_NAME,
    DENSE_VECTOR_SIZE,
    SPARSE_VECTOR_NAME,
    create_document_collection,
    ensure_document_collection,
)


@pytest.fixture()
def mock_client() -> AsyncMock:
    client = AsyncMock()
    client.create_collection = AsyncMock(return_value={"result": True})
    client.collection_exists = AsyncMock(return_value=False)
    return client


@pytest.mark.asyncio()
class TestCreateDocumentCollection:
    async def test_creates_with_correct_config(self, mock_client: AsyncMock) -> None:
        result = await create_document_collection(mock_client)
        assert result == {"result": True}

        call_kwargs = mock_client.create_collection.call_args
        assert call_kwargs.kwargs["name"] == DEFAULT_COLLECTION
        vectors = call_kwargs.kwargs["vectors_config"]
        assert DENSE_VECTOR_NAME in vectors
        assert vectors[DENSE_VECTOR_NAME]["size"] == DENSE_VECTOR_SIZE
        assert vectors[DENSE_VECTOR_NAME]["distance"] == "Cosine"

        sparse = call_kwargs.kwargs["sparse_vectors_config"]
        assert SPARSE_VECTOR_NAME in sparse

    async def test_custom_name_and_size(self, mock_client: AsyncMock) -> None:
        await create_document_collection(
            mock_client, collection_name="custom", dense_vector_size=768
        )
        call_kwargs = mock_client.create_collection.call_args
        assert call_kwargs.kwargs["name"] == "custom"
        assert call_kwargs.kwargs["vectors_config"][DENSE_VECTOR_NAME]["size"] == 768


@pytest.mark.asyncio()
class TestEnsureDocumentCollection:
    async def test_creates_when_missing(self, mock_client: AsyncMock) -> None:
        mock_client.collection_exists = AsyncMock(return_value=False)
        await ensure_document_collection(mock_client)
        mock_client.create_collection.assert_awaited_once()

    async def test_skips_when_exists(self, mock_client: AsyncMock) -> None:
        mock_client.collection_exists = AsyncMock(return_value=True)
        await ensure_document_collection(mock_client)
        mock_client.create_collection.assert_not_awaited()
