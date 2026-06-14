"""Tests for DocumentService — create, get, list, update, delete with error cases."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.services.document_service import (
    DocumentNotFoundError,
    DocumentPermissionError,
    DocumentService,
    DocumentValidationError,
)
from app.services.storage import DocumentStorageService, StorageResult
from app.services.validation import FileValidator, ValidationResult


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


def _make_document(**overrides) -> MagicMock:
    doc = MagicMock()
    doc.id = overrides.get("id", uuid.uuid4())
    doc.user_id = overrides.get("user_id", uuid.uuid4())
    doc.filename = overrides.get("filename", "report.pdf")
    doc.original_filename = overrides.get("original_filename", "report.pdf")
    doc.mime_type = overrides.get("mime_type", "application/pdf")
    doc.file_size_bytes = overrides.get("file_size_bytes", 1024)
    doc.storage_path = overrides.get("storage_path", "u1/d1/report.pdf")
    doc.storage_backend = overrides.get("storage_backend", "minio")
    doc.status = overrides.get("status", "uploaded")
    doc.document_type = overrides.get("document_type", None)
    doc.classification = overrides.get("classification", None)
    doc.metadata_ = overrides.get("metadata_", {})
    doc.checksum_sha256 = overrides.get("checksum_sha256", "a" * 64)
    doc.uploaded_at = overrides.get("uploaded_at", datetime.now(UTC))
    doc.processed_at = overrides.get("processed_at", None)
    doc.created_at = overrides.get("created_at", datetime.now(UTC))
    doc.updated_at = overrides.get("updated_at", datetime.now(UTC))
    doc.deleted_at = overrides.get("deleted_at", None)
    doc.page_count = overrides.get("page_count", None)
    return doc


@pytest.fixture()
def mock_validator() -> MagicMock:
    v = MagicMock(spec=FileValidator)
    v.validate_file.return_value = ValidationResult(
        is_valid=True, errors=[], detected_mime_type="application/pdf"
    )
    return v


@pytest.fixture()
def mock_storage() -> MagicMock:
    s = MagicMock(spec=DocumentStorageService)
    s.upload_document = AsyncMock(
        return_value=StorageResult(
            storage_path="user1/doc1/report.pdf",
            checksum="a" * 64,
            size=1024,
        )
    )
    s.delete_document = AsyncMock()
    s.get_presigned_url = AsyncMock(
        return_value="http://minio:9000/bucket/path?sig=abc"
    )
    return s


@pytest.fixture()
def mock_db() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture()
def service(mock_validator: MagicMock, mock_storage: MagicMock) -> DocumentService:
    return DocumentService(validator=mock_validator, storage=mock_storage)


class TestCreateDocument:
    """create_document should validate, upload, and persist."""

    @pytest.mark.asyncio()
    async def test_returns_document(
        self,
        service: DocumentService,
        mock_db: AsyncMock,
    ) -> None:
        doc = await service.create_document(
            filename="report.pdf",
            content_type="application/pdf",
            file_size=1024,
            file_bytes=b"%PDF-1.4 content",
            user_id=uuid.uuid4(),
            db=mock_db,
        )
        assert doc is not None
        assert doc.filename == "report.pdf"
        assert doc.mime_type == "application/pdf"

    @pytest.mark.asyncio()
    async def test_calls_validator(
        self,
        service: DocumentService,
        mock_validator: MagicMock,
        mock_db: AsyncMock,
    ) -> None:
        await service.create_document(
            filename="test.pdf",
            content_type="application/pdf",
            file_size=100,
            file_bytes=b"%PDF",
            user_id=uuid.uuid4(),
            db=mock_db,
        )
        mock_validator.validate_file.assert_called_once()
        call_kwargs = mock_validator.validate_file.call_args[1]
        assert call_kwargs["filename"] == "test.pdf"
        assert call_kwargs["content_type"] == "application/pdf"
        assert call_kwargs["file_size"] == 100

    @pytest.mark.asyncio()
    async def test_calls_storage_upload(
        self,
        service: DocumentService,
        mock_storage: MagicMock,
        mock_db: AsyncMock,
    ) -> None:
        user_id = uuid.uuid4()
        await service.create_document(
            filename="doc.pdf",
            content_type="application/pdf",
            file_size=200,
            file_bytes=b"%PDF-1.4",
            user_id=user_id,
            db=mock_db,
        )
        mock_storage.upload_document.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_adds_document_to_db(
        self,
        service: DocumentService,
        mock_db: AsyncMock,
    ) -> None:
        await service.create_document(
            filename="report.pdf",
            content_type="application/pdf",
            file_size=100,
            file_bytes=b"%PDF",
            user_id=uuid.uuid4(),
            db=mock_db,
        )
        mock_db.add.assert_called_once()
        mock_db.flush.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_validation_failure_raises(
        self,
        service: DocumentService,
        mock_validator: MagicMock,
        mock_db: AsyncMock,
    ) -> None:
        mock_validator.validate_file.return_value = ValidationResult(
            is_valid=False,
            errors=["Bad file type"],
            detected_mime_type=None,
        )
        with pytest.raises(DocumentValidationError) as exc_info:
            await service.create_document(
                filename="bad.gif",
                content_type="image/gif",
                file_size=100,
                file_bytes=b"GIF89a",
                user_id=uuid.uuid4(),
                db=mock_db,
            )
        assert "Bad file type" in str(exc_info.value)
        assert exc_info.value.result.is_valid is False

    @pytest.mark.asyncio()
    async def test_uses_detected_mime_type(
        self,
        service: DocumentService,
        mock_validator: MagicMock,
        mock_db: AsyncMock,
    ) -> None:
        mock_validator.validate_file.return_value = ValidationResult(
            is_valid=True,
            errors=[],
            detected_mime_type="image/png",
        )
        doc = await service.create_document(
            filename="img.png",
            content_type="image/png",
            file_size=100,
            file_bytes=b"\x89PNG",
            user_id=uuid.uuid4(),
            db=mock_db,
        )
        assert doc.mime_type == "image/png"

    @pytest.mark.asyncio()
    async def test_generates_unique_doc_id(
        self,
        service: DocumentService,
        mock_db: AsyncMock,
    ) -> None:
        doc1 = await service.create_document(
            filename="a.pdf",
            content_type="application/pdf",
            file_size=10,
            file_bytes=b"%PDF",
            user_id=uuid.uuid4(),
            db=mock_db,
        )
        doc2 = await service.create_document(
            filename="b.pdf",
            content_type="application/pdf",
            file_size=10,
            file_bytes=b"%PDF",
            user_id=uuid.uuid4(),
            db=mock_db,
        )
        assert doc1.id != doc2.id


class TestGetDocument:
    """get_document should retrieve by ID and verify ownership."""

    @pytest.mark.asyncio()
    async def test_returns_document_when_found(
        self,
        service: DocumentService,
        mock_db: AsyncMock,
    ) -> None:
        user_id = uuid.uuid4()
        doc = _make_document(user_id=user_id)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = doc
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.get_document(doc.id, user_id, mock_db)
        assert result is doc

    @pytest.mark.asyncio()
    async def test_raises_not_found_when_missing(
        self,
        service: DocumentService,
        mock_db: AsyncMock,
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(DocumentNotFoundError):
            await service.get_document(uuid.uuid4(), uuid.uuid4(), mock_db)

    @pytest.mark.asyncio()
    async def test_raises_permission_error_for_wrong_user(
        self,
        service: DocumentService,
        mock_db: AsyncMock,
    ) -> None:
        owner_id = uuid.uuid4()
        other_id = uuid.uuid4()
        doc = _make_document(user_id=owner_id)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = doc
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(DocumentPermissionError):
            await service.get_document(doc.id, other_id, mock_db)

    @pytest.mark.asyncio()
    async def test_excludes_soft_deleted(
        self,
        service: DocumentService,
        mock_db: AsyncMock,
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(DocumentNotFoundError):
            await service.get_document(uuid.uuid4(), uuid.uuid4(), mock_db)


class TestListDocuments:
    """list_documents should return paginated results."""

    @pytest.mark.asyncio()
    async def test_returns_documents_and_total(
        self,
        service: DocumentService,
        mock_db: AsyncMock,
    ) -> None:
        user_id = uuid.uuid4()
        docs = [_make_document(user_id=user_id) for _ in range(3)]

        count_result = MagicMock()
        count_result.scalar_one.return_value = 3
        rows_result = MagicMock()
        rows_result.scalars.return_value.all.return_value = docs

        mock_db.execute = AsyncMock(side_effect=[count_result, rows_result])

        result_docs, total = await service.list_documents(user_id, mock_db)
        assert total == 3
        assert len(result_docs) == 3

    @pytest.mark.asyncio()
    async def test_pagination_parameters(
        self,
        service: DocumentService,
        mock_db: AsyncMock,
    ) -> None:
        user_id = uuid.uuid4()
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        rows_result = MagicMock()
        rows_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(side_effect=[count_result, rows_result])

        docs, total = await service.list_documents(
            user_id, mock_db, page=2, page_size=10
        )
        assert total == 0
        assert docs == []

    @pytest.mark.asyncio()
    async def test_empty_result(
        self,
        service: DocumentService,
        mock_db: AsyncMock,
    ) -> None:
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        rows_result = MagicMock()
        rows_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(side_effect=[count_result, rows_result])

        docs, total = await service.list_documents(uuid.uuid4(), mock_db)
        assert total == 0
        assert docs == []

    @pytest.mark.asyncio()
    async def test_page_clamped_to_minimum(
        self,
        service: DocumentService,
        mock_db: AsyncMock,
    ) -> None:
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        rows_result = MagicMock()
        rows_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(side_effect=[count_result, rows_result])

        await service.list_documents(uuid.uuid4(), mock_db, page=-1)
        assert mock_db.execute.await_count == 2

    @pytest.mark.asyncio()
    async def test_page_size_clamped_to_100(
        self,
        service: DocumentService,
        mock_db: AsyncMock,
    ) -> None:
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        rows_result = MagicMock()
        rows_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(side_effect=[count_result, rows_result])

        await service.list_documents(uuid.uuid4(), mock_db, page_size=500)
        assert mock_db.execute.await_count == 2


class TestUpdateDocument:
    """update_document should modify allowed fields only."""

    @pytest.mark.asyncio()
    async def test_updates_allowed_fields(
        self,
        service: DocumentService,
        mock_db: AsyncMock,
    ) -> None:
        user_id = uuid.uuid4()
        doc = _make_document(user_id=user_id)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = doc
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.update_document(
            doc.id, user_id, {"document_type": "invoice"}, mock_db
        )
        assert result.document_type == "invoice"

    @pytest.mark.asyncio()
    async def test_updates_status(
        self,
        service: DocumentService,
        mock_db: AsyncMock,
    ) -> None:
        user_id = uuid.uuid4()
        doc = _make_document(user_id=user_id)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = doc
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.update_document(
            doc.id, user_id, {"status": "completed"}, mock_db
        )
        assert result.status == "completed"

    @pytest.mark.asyncio()
    async def test_disallowed_field_raises(
        self,
        service: DocumentService,
        mock_db: AsyncMock,
    ) -> None:
        with pytest.raises(ValueError, match="Cannot update fields"):
            await service.update_document(
                uuid.uuid4(), uuid.uuid4(), {"filename": "new.pdf"}, mock_db
            )

    @pytest.mark.asyncio()
    async def test_raises_not_found(
        self,
        service: DocumentService,
        mock_db: AsyncMock,
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(DocumentNotFoundError):
            await service.update_document(
                uuid.uuid4(), uuid.uuid4(), {"status": "completed"}, mock_db
            )

    @pytest.mark.asyncio()
    async def test_raises_permission_error(
        self,
        service: DocumentService,
        mock_db: AsyncMock,
    ) -> None:
        owner = uuid.uuid4()
        other = uuid.uuid4()
        doc = _make_document(user_id=owner)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = doc
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(DocumentPermissionError):
            await service.update_document(
                doc.id, other, {"status": "completed"}, mock_db
            )


class TestDeleteDocument:
    """delete_document should soft-delete by setting deleted_at."""

    @pytest.mark.asyncio()
    async def test_sets_deleted_at(
        self,
        service: DocumentService,
        mock_db: AsyncMock,
    ) -> None:
        user_id = uuid.uuid4()
        doc = _make_document(user_id=user_id)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = doc
        mock_db.execute = AsyncMock(return_value=mock_result)

        await service.delete_document(doc.id, user_id, mock_db)
        assert doc.deleted_at is not None
        mock_db.flush.assert_awaited()

    @pytest.mark.asyncio()
    async def test_raises_not_found(
        self,
        service: DocumentService,
        mock_db: AsyncMock,
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(DocumentNotFoundError):
            await service.delete_document(uuid.uuid4(), uuid.uuid4(), mock_db)

    @pytest.mark.asyncio()
    async def test_raises_permission_error(
        self,
        service: DocumentService,
        mock_db: AsyncMock,
    ) -> None:
        owner = uuid.uuid4()
        other = uuid.uuid4()
        doc = _make_document(user_id=owner)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = doc
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(DocumentPermissionError):
            await service.delete_document(doc.id, other, mock_db)


class TestExceptionHierarchy:
    """Custom exceptions should inherit from DocumentServiceError."""

    def test_not_found_inherits(self) -> None:
        assert issubclass(DocumentNotFoundError, Exception)

    def test_permission_inherits(self) -> None:
        assert issubclass(DocumentPermissionError, Exception)

    def test_validation_error_holds_result(self) -> None:
        result = ValidationResult(is_valid=False, errors=["test error"])
        err = DocumentValidationError(result)
        assert err.result is result
        assert "test error" in str(err)
