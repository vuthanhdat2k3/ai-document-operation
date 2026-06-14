"""Tests for DocumentStorageService — upload, download, presigned URL, delete, checksum."""

from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.services.storage import DocumentStorageService, StorageResult


def _test_settings() -> Settings:
    return Settings(
        DEBUG=True,
        LOG_LEVEL="DEBUG",
        DATABASE_URL="postgresql+asyncpg://test:test@localhost:5432/test",
        REDIS_URL="redis://localhost:6379/0",
        QDRANT_URL="http://localhost:6333",
        MINIO_ENDPOINT="localhost:9000",
        MINIO_ACCESS_KEY="test",
        MINIO_SECRET_KEY="test",
        CORS_ORIGINS="http://localhost:3000",
    )


@pytest.fixture()
def mock_minio_storage() -> MagicMock:
    storage = MagicMock()
    storage.upload_file = AsyncMock(return_value="user123/doc456/report.pdf")
    storage.download_file = AsyncMock(return_value=b"file content bytes")
    storage.get_presigned_url = AsyncMock(
        return_value="http://minio:9000/bucket/user123/doc456/report.pdf?X-Amz-Signature=abc"
    )
    storage.delete_file = AsyncMock()
    return storage


@pytest.fixture()
def storage_service(mock_minio_storage: MagicMock) -> DocumentStorageService:
    settings = _test_settings()
    with patch("app.services.storage.get_settings", return_value=settings):
        service = DocumentStorageService(storage=mock_minio_storage)
    return service


class TestUploadDocument:
    """upload_document delegates to MinioStorage and returns StorageResult."""

    @pytest.mark.asyncio()
    async def test_returns_storage_result(
        self, storage_service: DocumentStorageService
    ) -> None:
        file_bytes = b"%PDF-1.4 test content"
        result = await storage_service.upload_document(
            file_bytes=file_bytes,
            filename="report.pdf",
            document_id="doc456",
            user_id="user123",
            content_type="application/pdf",
        )
        assert isinstance(result, StorageResult)
        assert result.storage_path == "user123/doc456/report.pdf"
        assert result.size == len(file_bytes)

    @pytest.mark.asyncio()
    async def test_checksum_is_sha256(
        self, storage_service: DocumentStorageService
    ) -> None:
        file_bytes = b"hello world"
        result = await storage_service.upload_document(
            file_bytes=file_bytes,
            filename="test.txt",
            document_id="doc1",
            user_id="user1",
            content_type="text/plain",
        )
        expected = hashlib.sha256(file_bytes).hexdigest()
        assert result.checksum == expected
        assert len(result.checksum) == 64

    @pytest.mark.asyncio()
    async def test_delegates_to_minio_upload(
        self,
        storage_service: DocumentStorageService,
        mock_minio_storage: MagicMock,
    ) -> None:
        file_bytes = b"data"
        await storage_service.upload_document(
            file_bytes=file_bytes,
            filename="file.pdf",
            document_id="d1",
            user_id="u1",
            content_type="application/pdf",
        )
        mock_minio_storage.upload_file.assert_awaited_once_with(
            object_name="u1/d1/file.pdf",
            data=file_bytes,
            length=4,
            content_type="application/pdf",
        )

    @pytest.mark.asyncio()
    async def test_builds_correct_storage_path(
        self, storage_service: DocumentStorageService
    ) -> None:
        result = await storage_service.upload_document(
            file_bytes=b"x",
            filename="doc.pdf",
            document_id="abc-def",
            user_id="user-999",
        )
        assert result.storage_path == "user-999/abc-def/doc.pdf"

    @pytest.mark.asyncio()
    async def test_default_content_type(
        self,
        storage_service: DocumentStorageService,
        mock_minio_storage: MagicMock,
    ) -> None:
        await storage_service.upload_document(
            file_bytes=b"x",
            filename="f.bin",
            document_id="d",
            user_id="u",
        )
        call_kwargs = mock_minio_storage.upload_file.call_args[1]
        assert call_kwargs["content_type"] == "application/octet-stream"

    @pytest.mark.asyncio()
    async def test_empty_file_still_works(
        self, storage_service: DocumentStorageService
    ) -> None:
        result = await storage_service.upload_document(
            file_bytes=b"",
            filename="empty.pdf",
            document_id="d1",
            user_id="u1",
        )
        assert result.size == 0
        assert result.checksum == hashlib.sha256(b"").hexdigest()


class TestDownloadDocument:
    """download_document returns raw bytes from MinIO."""

    @pytest.mark.asyncio()
    async def test_returns_bytes(
        self, storage_service: DocumentStorageService
    ) -> None:
        data = await storage_service.download_document("user123/doc456/report.pdf")
        assert data == b"file content bytes"

    @pytest.mark.asyncio()
    async def test_passes_storage_path(
        self,
        storage_service: DocumentStorageService,
        mock_minio_storage: MagicMock,
    ) -> None:
        await storage_service.download_document("some/path.pdf")
        mock_minio_storage.download_file.assert_awaited_once_with(
            object_name="some/path.pdf"
        )


class TestGetPresignedUrl:
    """get_presigned_url delegates to MinioStorage."""

    @pytest.mark.asyncio()
    async def test_returns_url(self, storage_service: DocumentStorageService) -> None:
        url = await storage_service.get_presigned_url("user123/doc456/report.pdf")
        assert url.startswith("http://")

    @pytest.mark.asyncio()
    async def test_custom_expiry(
        self,
        storage_service: DocumentStorageService,
        mock_minio_storage: MagicMock,
    ) -> None:
        await storage_service.get_presigned_url("path.pdf", expiry_seconds=7200)
        mock_minio_storage.get_presigned_url.assert_awaited_once_with(
            object_name="path.pdf", expires=7200
        )

    @pytest.mark.asyncio()
    async def test_default_expiry(
        self,
        storage_service: DocumentStorageService,
        mock_minio_storage: MagicMock,
    ) -> None:
        await storage_service.get_presigned_url("path.pdf")
        mock_minio_storage.get_presigned_url.assert_awaited_once_with(
            object_name="path.pdf", expires=3600
        )


class TestDeleteDocument:
    """delete_document delegates to MinioStorage."""

    @pytest.mark.asyncio()
    async def test_calls_delete(
        self,
        storage_service: DocumentStorageService,
        mock_minio_storage: MagicMock,
    ) -> None:
        await storage_service.delete_document("user123/doc456/report.pdf")
        mock_minio_storage.delete_file.assert_awaited_once_with(
            object_name="user123/doc456/report.pdf"
        )

    @pytest.mark.asyncio()
    async def test_returns_none(
        self, storage_service: DocumentStorageService
    ) -> None:
        result = await storage_service.delete_document("path.pdf")
        assert result is None


class TestChecksumComputation:
    """_compute_checksum should produce correct SHA-256 digests."""

    def test_known_hash(self) -> None:
        data = b"hello world"
        expected = hashlib.sha256(data).hexdigest()
        assert DocumentStorageService._compute_checksum(data) == expected

    def test_empty_data(self) -> None:
        expected = hashlib.sha256(b"").hexdigest()
        assert DocumentStorageService._compute_checksum(b"") == expected

    def test_deterministic(self) -> None:
        data = b"test data for hashing"
        h1 = DocumentStorageService._compute_checksum(data)
        h2 = DocumentStorageService._compute_checksum(data)
        assert h1 == h2

    def test_different_data_different_hash(self) -> None:
        h1 = DocumentStorageService._compute_checksum(b"data1")
        h2 = DocumentStorageService._compute_checksum(b"data2")
        assert h1 != h2


class TestBuildStoragePath:
    """_build_storage_path should construct correct object keys."""

    def test_standard_path(self) -> None:
        path = DocumentStorageService._build_storage_path(
            "user1", "doc1", "file.pdf"
        )
        assert path == "user1/doc1/file.pdf"

    def test_uuid_ids(self) -> None:
        path = DocumentStorageService._build_storage_path(
            "550e8400-e29b-41d4-a716-446655440000",
            "660e8400-e29b-41d4-a716-446655440001",
            "report.pdf",
        )
        assert path == "550e8400-e29b-41d4-a716-446655440000/660e8400-e29b-41d4-a716-446655440001/report.pdf"

    def test_filename_with_spaces(self) -> None:
        path = DocumentStorageService._build_storage_path(
            "u1", "d1", "my report.pdf"
        )
        assert path == "u1/d1/my report.pdf"


class TestStorageResult:
    """StorageResult dataclass behavior."""

    def test_frozen(self) -> None:
        r = StorageResult(storage_path="p", checksum="c", size=10)
        with pytest.raises(AttributeError):
            r.storage_path = "other"  # type: ignore[misc]

    def test_fields(self) -> None:
        r = StorageResult(
            storage_path="user/doc/file.pdf",
            checksum="abc123" * 10 + "ab",
            size=4096,
        )
        assert r.storage_path == "user/doc/file.pdf"
        assert r.size == 4096
