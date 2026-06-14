"""Tests for LocalFileStorage — upload, download, delete, health check."""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

import pytest

from app.storage.local import LocalFileStorage


@pytest.fixture()
def storage(tmp_path: Path) -> LocalFileStorage:
    return LocalFileStorage(base_dir=tmp_path, url_prefix="/uploads")


@pytest.mark.asyncio()
class TestEnsureBucket:
    async def test_creates_directory(self, tmp_path: Path) -> None:
        target = tmp_path / "new_bucket"
        s = LocalFileStorage(base_dir=target)
        assert target.exists()


@pytest.mark.asyncio()
class TestUploadDownload:
    async def test_upload_and_download_bytes(self, storage: LocalFileStorage) -> None:
        name = await storage.upload_file("test.txt", b"hello")
        assert name == "test.txt"

        data = await storage.download_file("test.txt")
        assert data == b"hello"

    async def test_upload_stream(self, storage: LocalFileStorage) -> None:
        stream = io.BytesIO(b"stream data")
        await storage.upload_file("stream.bin", stream)
        data = await storage.download_file("stream.bin")
        assert data == b"stream data"

    async def test_nested_paths(self, storage: LocalFileStorage) -> None:
        await storage.upload_file("a/b/deep.txt", b"nested")
        data = await storage.download_file("a/b/deep.txt")
        assert data == b"nested"

    async def test_download_missing_raises(self, storage: LocalFileStorage) -> None:
        with pytest.raises(FileNotFoundError):
            await storage.download_file("nope.txt")

    async def test_delete(self, storage: LocalFileStorage) -> None:
        await storage.upload_file("to_delete.txt", b"bye")
        await storage.delete_file("to_delete.txt")
        with pytest.raises(FileNotFoundError):
            await storage.download_file("to_delete.txt")

    async def test_delete_missing_raises(self, storage: LocalFileStorage) -> None:
        with pytest.raises(FileNotFoundError):
            await storage.delete_file("ghost.txt")


@pytest.mark.asyncio()
class TestPathTraversal:
    async def test_rejects_traversal(self, storage: LocalFileStorage) -> None:
        with pytest.raises(ValueError, match="Path traversal"):
            storage._resolve("../../etc/passwd")


@pytest.mark.asyncio()
class TestPresignedUrl:
    async def test_returns_url(self, storage: LocalFileStorage) -> None:
        url = await storage.get_presigned_url("doc.pdf")
        assert url == "/uploads/doc.pdf"

    async def test_url_encoded(self, storage: LocalFileStorage) -> None:
        url = await storage.get_presigned_url("my file.pdf")
        assert "my%20file.pdf" in url


@pytest.mark.asyncio()
class TestHealthCheck:
    async def test_success(self, storage: LocalFileStorage) -> None:
        assert await storage.health_check() is True
