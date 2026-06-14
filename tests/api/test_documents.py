"""Tests for document CRUD API endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings


@pytest.fixture()
def test_settings() -> Settings:
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


def _make_document(**overrides):
    defaults = {
        "id": uuid.uuid4(),
        "user_id": uuid.UUID("00000000-0000-0000-0000-000000000001"),
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
        "deleted_at": None,
        "page_count": None,
        "document_type": None,
        "classification": None,
        "metadata_": {},
        "processed_at": None,
    }
    defaults.update(overrides)
    return MagicMock(**defaults)


@pytest.fixture()
def mock_doc_service():
    svc = AsyncMock()
    svc.create_document = AsyncMock()
    svc.list_documents = AsyncMock(return_value=([], 0))
    svc.get_document = AsyncMock()
    svc.update_document = AsyncMock()
    svc.delete_document = AsyncMock()
    return svc


@pytest.fixture()
async def client(test_settings, mock_doc_service):
    from app.main import create_app

    with patch("app.config.get_settings", return_value=test_settings):
        app = create_app(test_settings)

        async def _override_service():
            return mock_doc_service

        from app.api.v1.documents import _get_document_service

        app.dependency_overrides[_get_document_service] = _override_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


@pytest.mark.asyncio()
class TestUploadDocument:
    async def test_upload_success(self, client, mock_doc_service):
        doc = _make_document()
        mock_doc_service.create_document.return_value = doc

        response = await client.post(
            "/api/v1/documents/",
            files={"file": ("test.pdf", b"%PDF-1.4 fake content", "application/pdf")},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["filename"] == "test.pdf"

    async def test_upload_empty_file(self, client):
        response = await client.post(
            "/api/v1/documents/",
            files={"file": ("empty.pdf", b"", "application/pdf")},
        )
        assert response.status_code in (413, 422)


@pytest.mark.asyncio()
class TestListDocuments:
    async def test_list_empty(self, client, mock_doc_service):
        mock_doc_service.list_documents.return_value = ([], 0)
        response = await client.get("/api/v1/documents/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    async def test_list_with_pagination(self, client, mock_doc_service):
        doc = _make_document()
        mock_doc_service.list_documents.return_value = ([doc], 1)
        response = await client.get("/api/v1/documents/?page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1


@pytest.mark.asyncio()
class TestGetDocument:
    async def test_get_success(self, client, mock_doc_service):
        doc = _make_document()
        mock_doc_service.get_document.return_value = doc
        doc_id = str(doc.id)
        response = await client.get(f"/api/v1/documents/{doc_id}")
        assert response.status_code == 200

    async def test_get_not_found(self, client, mock_doc_service):
        from app.services.document_service import DocumentNotFoundError

        mock_doc_service.get_document.side_effect = DocumentNotFoundError("not found")
        doc_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/documents/{doc_id}")
        assert response.status_code == 404


@pytest.mark.asyncio()
class TestDeleteDocument:
    async def test_delete_success(self, client, mock_doc_service):
        mock_doc_service.delete_document.return_value = None
        doc_id = str(uuid.uuid4())
        response = await client.delete(f"/api/v1/documents/{doc_id}")
        assert response.status_code == 204

    async def test_delete_not_found(self, client, mock_doc_service):
        from app.services.document_service import DocumentNotFoundError

        mock_doc_service.delete_document.side_effect = DocumentNotFoundError("not found")
        doc_id = str(uuid.uuid4())
        response = await client.delete(f"/api/v1/documents/{doc_id}")
        assert response.status_code == 404


@pytest.mark.asyncio()
class TestUpdateDocument:
    async def test_update_success(self, client, mock_doc_service):
        doc = _make_document(document_type="contract")
        mock_doc_service.update_document.return_value = doc
        doc_id = str(doc.id)
        response = await client.patch(
            f"/api/v1/documents/{doc_id}",
            json={"document_type": "contract"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["document_type"] == "contract"

    async def test_update_empty_body(self, client):
        doc_id = str(uuid.uuid4())
        response = await client.patch(f"/api/v1/documents/{doc_id}", json={})
        assert response.status_code == 422
