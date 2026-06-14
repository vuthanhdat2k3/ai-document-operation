"""Unit tests for LocalFileStorage using a temporary directory."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from app.storage.local import LocalFileStorage


@pytest.fixture()
def storage(tmp_path: Path) -> LocalFileStorage:
    return LocalFileStorage(base_dir=tmp_path / "uploads", url_prefix="/uploads")


class TestInit:
    """Tests for LocalFileStorage initialization."""

    def test_creates_base_dir(self, tmp_path: Path) -> None:
        base = tmp_path / "new_uploads"
        LocalFileStorage(base_dir=base)
        assert base.exists()

    def test_url_prefix_stripped(self, tmp_path: Path) -> None:
        s = LocalFileStorage(base_dir=tmp_path / "up", url_prefix="/uploads/")
        assert s._url_prefix == "/uploads"


class TestResolve:
    """Tests for path resolution and traversal prevention."""

    def test_normal_path(self, storage: LocalFileStorage) -> None:
        resolved = storage._resolve("test.txt")
        assert str(resolved).startswith(str(storage._base))

    def test_path_traversal_blocked(self, storage: LocalFileStorage) -> None:
        with pytest.raises(ValueError, match="Path traversal"):
            storage._resolve("../../etc/passwd")

    def test_dot_dot_blocked(self, storage: LocalFileStorage) -> None:
        with pytest.raises(ValueError, match="Path traversal"):
            storage._resolve("../secret.txt")

    def test_absolute_path_blocked(self, storage: LocalFileStorage) -> None:
        with pytest.raises(ValueError, match="Path traversal"):
            storage._resolve("/etc/passwd")


class TestUploadFile:
    """Tests for LocalFileStorage.upload_file."""

    async def test_upload_bytes(self, storage: LocalFileStorage) -> None:
        result = await storage.upload_file("test.txt", b"hello world")
        assert result == "test.txt"
        content = (storage._base / "test.txt").read_bytes()
        assert content == b"hello world"

    async def test_upload_stream(self, storage: LocalFileStorage) -> None:
        stream = io.BytesIO(b"stream data")
        result = await storage.upload_file("stream.txt", stream)
        assert result == "stream.txt"
        content = (storage._base / "stream.txt").read_bytes()
        assert content == b"stream data"

    async def test_upload_creates_subdirs(self, storage: LocalFileStorage) -> None:
        await storage.upload_file("sub/dir/file.txt", b"data")
        assert (storage._base / "sub" / "dir" / "file.txt").exists()

    async def test_upload_binary_data(self, storage: LocalFileStorage) -> None:
        data = bytes(range(256))
        await storage.upload_file("binary.bin", data)
        content = (storage._base / "binary.bin").read_bytes()
        assert content == data


class TestDownloadFile:
    """Tests for LocalFileStorage.download_file."""

    async def test_download_existing(self, storage: LocalFileStorage) -> None:
        await storage.upload_file("test.txt", b"content")
        result = await storage.download_file("test.txt")
        assert result == b"content"

    async def test_download_nonexistent(self, storage: LocalFileStorage) -> None:
        with pytest.raises(FileNotFoundError):
            await storage.download_file("missing.txt")

    async def test_roundtrip(self, storage: LocalFileStorage) -> None:
        original = b"roundtrip test data \x00\x01\x02"
        await storage.upload_file("data.bin", original)
        downloaded = await storage.download_file("data.bin")
        assert downloaded == original


class TestDeleteFile:
    """Tests for LocalFileStorage.delete_file."""

    async def test_delete_existing(self, storage: LocalFileStorage) -> None:
        await storage.upload_file("to_delete.txt", b"data")
        await storage.delete_file("to_delete.txt")
        assert not (storage._base / "to_delete.txt").exists()

    async def test_delete_nonexistent(self, storage: LocalFileStorage) -> None:
        with pytest.raises(FileNotFoundError):
            await storage.delete_file("ghost.txt")


class TestGetPresignedUrl:
    """Tests for LocalFileStorage.get_presigned_url."""

    async def test_returns_url(self, storage: LocalFileStorage) -> None:
        url = await storage.get_presigned_url("file.txt")
        assert url == "/uploads/file.txt"

    async def test_url_with_subdir(self, storage: LocalFileStorage) -> None:
        url = await storage.get_presigned_url("sub/file.txt")
        assert url == "/uploads/sub/file.txt"

    async def test_url_with_special_chars(self, storage: LocalFileStorage) -> None:
        url = await storage.get_presigned_url("my file.pdf")
        assert url.startswith("/uploads/")
        assert " " not in url


class TestHealthCheck:
    """Tests for LocalFileStorage.health_check."""

    async def test_healthy(self, storage: LocalFileStorage) -> None:
        assert await storage.health_check() is True

    async def test_creates_dir_if_missing(self, tmp_path: Path) -> None:
        base = tmp_path / "missing" / "deep"
        s = LocalFileStorage(base_dir=base)
        assert await s.health_check() is True
        assert base.exists()


class TestEnsureBucket:
    """Tests for LocalFileStorage.ensure_bucket (no-op for local)."""

    async def test_ensure_bucket_noop(self, storage: LocalFileStorage) -> None:
        await storage.ensure_bucket()
        assert storage._base.exists()

    async def test_ensure_bucket_creates_dir(self, tmp_path: Path) -> None:
        base = tmp_path / "new"
        s = LocalFileStorage(base_dir=base)
        await s.ensure_bucket()
        assert s._base.exists()
