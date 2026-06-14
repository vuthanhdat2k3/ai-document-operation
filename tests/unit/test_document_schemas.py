"""Tests for document Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.api.schemas.documents import (
    DocumentDetailResponse,
    DocumentResponse,
    DocumentStatus,
    DocumentUpdate,
    DownloadResponse,
)


class TestDocumentStatus:
    def test_all_statuses(self) -> None:
        assert DocumentStatus.UPLOADED == "uploaded"
        assert DocumentStatus.FAILED == "failed"
        assert DocumentStatus.COMPLETED == "completed"

    def test_from_string(self) -> None:
        assert DocumentStatus("uploaded") == DocumentStatus.UPLOADED


class TestDocumentResponse:
    def test_from_dict(self) -> None:
        data = {
            "id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            "filename": "test.pdf",
            "original_filename": "test.pdf",
            "mime_type": "application/pdf",
            "file_size_bytes": 1024,
            "storage_backend": "minio",
            "storage_path": "user/doc/test.pdf",
            "status": "uploaded",
            "checksum_sha256": "a" * 64,
            "uploaded_at": datetime.now(UTC),
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
        resp = DocumentResponse(**data)
        assert resp.filename == "test.pdf"
        assert resp.status == "uploaded"

    def test_optional_fields_none(self) -> None:
        data = {
            "id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            "filename": "test.pdf",
            "original_filename": "test.pdf",
            "mime_type": "application/pdf",
            "file_size_bytes": 1024,
            "storage_backend": "minio",
            "storage_path": "user/doc/test.pdf",
            "status": "uploaded",
            "checksum_sha256": "a" * 64,
            "uploaded_at": datetime.now(UTC),
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
        resp = DocumentResponse(**data)
        assert resp.page_count is None
        assert resp.document_type is None
        assert resp.classification is None


class TestDocumentUpdate:
    def test_partial_update(self) -> None:
        update = DocumentUpdate(document_type="contract")
        data = update.model_dump(exclude_unset=True)
        assert data == {"document_type": "contract"}

    def test_metadata_alias(self) -> None:
        update = DocumentUpdate.model_validate({"metadata": {"key": "value"}})
        assert update.metadata_ == {"key": "value"}

    def test_empty_update(self) -> None:
        update = DocumentUpdate()
        data = update.model_dump(exclude_unset=True)
        assert data == {}


class TestDownloadResponse:
    def test_valid(self) -> None:
        resp = DownloadResponse(url="https://example.com/file.pdf", expires_in=3600)
        assert resp.url == "https://example.com/file.pdf"
        assert resp.expires_in == 3600

    def test_invalid_expires(self) -> None:
        with pytest.raises(ValidationError):
            DownloadResponse(url="https://example.com/file.pdf", expires_in=0)


class TestDocumentDetailResponse:
    def test_with_empty_lists(self) -> None:
        data = {
            "id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            "filename": "test.pdf",
            "original_filename": "test.pdf",
            "mime_type": "application/pdf",
            "file_size_bytes": 1024,
            "storage_backend": "minio",
            "storage_path": "user/doc/test.pdf",
            "status": "uploaded",
            "checksum_sha256": "a" * 64,
            "uploaded_at": datetime.now(UTC),
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
        resp = DocumentDetailResponse(**data)
        assert resp.pages == []
        assert resp.chunks == []
