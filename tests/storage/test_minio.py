"""Tests for MinioStorage — upload, download, health check."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest

from app.storage.minio import MinioStorage


@pytest.fixture()
def mock_settings() -> MagicMock:
    settings = MagicMock()
    settings.MINIO_ENDPOINT = "localhost:9000"
    settings.MINIO_ACCESS_KEY = "minioadmin"
    settings.MINIO_SECRET_KEY = "minioadmin"
    settings.MINIO_BUCKET = "test-bucket"
    settings.MINIO_USE_SSL = False
    return settings


@pytest.fixture()
def storage(mock_settings: MagicMock) -> MinioStorage:
    with patch("app.storage.minio.Minio"):
        return MinioStorage(mock_settings)


@pytest.mark.asyncio()
class TestEnsureBucket:
    async def test_creates_bucket_when_missing(self, storage: MinioStorage) -> None:
        storage._client.bucket_exists = MagicMock(return_value=False)
        storage._client.make_bucket = MagicMock()

        await storage.ensure_bucket()
        storage._client.bucket_exists.assert_called_once_with("test-bucket")
        storage._client.make_bucket.assert_called_once_with("test-bucket")

    async def test_skips_when_exists(self, storage: MinioStorage) -> None:
        storage._client.bucket_exists = MagicMock(return_value=True)
        storage._client.make_bucket = MagicMock()

        await storage.ensure_bucket()
        storage._client.make_bucket.assert_not_called()


@pytest.mark.asyncio()
class TestUploadDownload:
    async def test_upload_bytes(self, storage: MinioStorage) -> None:
        storage._client.put_object = MagicMock()
        result = await storage.upload_file("doc.txt", b"hello world", content_type="text/plain")
        assert result == "doc.txt"
        storage._client.put_object.assert_called_once()

    async def test_upload_stream(self, storage: MinioStorage) -> None:
        storage._client.put_object = MagicMock()
        stream = io.BytesIO(b"data")
        result = await storage.upload_file("doc.bin", stream, length=4)
        assert result == "doc.bin"

    async def test_download(self, storage: MinioStorage) -> None:
        mock_response = MagicMock()
        mock_response.read.return_value = b"file content"
        storage._client.get_object = MagicMock(return_value=mock_response)

        data = await storage.download_file("doc.txt")
        assert data == b"file content"

    async def test_delete(self, storage: MinioStorage) -> None:
        storage._client.remove_object = MagicMock()
        await storage.delete_file("doc.txt")
        storage._client.remove_object.assert_called_once_with(
            bucket_name="test-bucket", object_name="doc.txt"
        )

    async def test_presigned_url(self, storage: MinioStorage) -> None:
        storage._client.presigned_get_object = MagicMock(
            return_value="http://minio:9000/test-bucket/doc.txt?sig=abc"
        )
        url = await storage.get_presigned_url("doc.txt", expires=7200)
        assert url.startswith("http://")


@pytest.mark.asyncio()
class TestHealthCheck:
    async def test_success(self, storage: MinioStorage) -> None:
        storage._client.list_buckets = MagicMock(return_value=[])
        assert await storage.health_check() is True

    async def test_failure(self, storage: MinioStorage) -> None:
        storage._client.list_buckets = MagicMock(side_effect=ConnectionError("down"))
        assert await storage.health_check() is False
