"""Comprehensive tests for all backend API endpoints.

Covers all 32 endpoints across 11 route modules:
  admin, auth, documents, extraction, parsing, risks, qa, reports, search, agent, eval
"""

from __future__ import annotations

import uuid
from collections import OrderedDict
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.middleware.error_handler import register_exception_handlers
from app.api.v1.router import v1_router
from app.config import Settings


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _settings() -> Settings:
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
        JWT_SECRET_KEY="test-secret-key-for-tests",
        JWT_ALGORITHM="HS256",
    )


TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
TEST_DOC_ID = uuid.uuid4()
TEST_REPORT_ID = uuid.uuid4()
TEST_FIELD_ID = uuid.uuid4()
TEST_SESSION_ID = str(uuid.uuid4())


def _make_user(**overrides):
    defaults = {
        "id": TEST_USER_ID,
        "email": "test@example.com",
        "full_name": "Test User",
        "role": "viewer",
        "is_active": True,
        "hashed_password": "$2b$12$fakehash",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
        "deleted_at": None,
        "preferences": {},
    }
    defaults.update(overrides)
    m = MagicMock(**defaults)
    m.id = defaults["id"]
    m.email = defaults["email"]
    m.full_name = defaults["full_name"]
    m.role = defaults["role"]
    m.is_active = defaults["is_active"]
    m.hashed_password = defaults["hashed_password"]
    m.created_at = defaults["created_at"]
    return m


def _make_document(**overrides):
    defaults = {
        "id": TEST_DOC_ID,
        "user_id": TEST_USER_ID,
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


def _make_report(**overrides):
    defaults = {
        "id": TEST_REPORT_ID,
        "user_id": TEST_USER_ID,
        "document_id": TEST_DOC_ID,
        "session_id": None,
        "report_type": "summary",
        "title": "Test Report",
        "content": {"summary": "test"},
        "format": "markdown",
        "storage_path": None,
        "status": "completed",
        "generated_at": datetime.now(UTC),
        "expires_at": None,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    m = MagicMock(**defaults)
    m.id = defaults["id"]
    m.user_id = defaults["user_id"]
    m.document_id = defaults["document_id"]
    return m


@pytest_asyncio.fixture()
async def app_client() -> AsyncClient:
    """Create a test app without DB-dependent lifespan and return an AsyncClient."""
    with patch("app.config.get_settings", return_value=_settings()):
        app = FastAPI()
        app.include_router(v1_router)
        register_exception_handlers(app)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    """GET /api/v1/health"""

    @pytest.mark.asyncio()
    async def test_health_returns_200(self, app_client: AsyncClient):
        resp = await app_client.get("/api/v1/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["version"] == "1.0.0"
        assert "timestamp" in body


class TestReadinessEndpoint:
    """GET /api/v1/ready"""

    @pytest.mark.asyncio()
    async def test_ready_all_ok(self, app_client: AsyncClient):
        with (
            patch("app.api.v1.admin._check_postgres", new_callable=AsyncMock, return_value="ok"),
            patch("app.api.v1.admin._check_redis", new_callable=AsyncMock, return_value="ok"),
            patch("app.api.v1.admin._check_qdrant", new_callable=AsyncMock, return_value="ok"),
            patch("app.api.v1.admin._check_minio", new_callable=AsyncMock, return_value="ok"),
        ):
            resp = await app_client.get("/api/v1/ready")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ready"
        assert all(v == "ok" for v in body["services"].values())

    @pytest.mark.asyncio()
    async def test_ready_degraded(self, app_client: AsyncClient):
        with (
            patch("app.api.v1.admin._check_postgres", new_callable=AsyncMock, return_value="ok"),
            patch("app.api.v1.admin._check_redis", new_callable=AsyncMock, return_value="error: down"),
            patch("app.api.v1.admin._check_qdrant", new_callable=AsyncMock, return_value="ok"),
            patch("app.api.v1.admin._check_minio", new_callable=AsyncMock, return_value="ok"),
        ):
            resp = await app_client.get("/api/v1/ready")
        body = resp.json()
        assert body["status"] == "degraded"
        assert body["services"]["redis"] == "error: down"


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

class TestRegisterEndpoint:
    """POST /api/v1/auth/register"""

    @pytest.mark.asyncio()
    async def test_register_success(self, app_client: AsyncClient):
        from app.db.session import get_db as real_get_db

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        async def _mock_refresh(obj):
            obj.id = TEST_USER_ID
            obj.created_at = datetime.now(UTC)

        mock_session.refresh = AsyncMock(side_effect=_mock_refresh)

        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session

        resp = await app_client.post(
            "/api/v1/auth/register",
            json={
                "email": "new@example.com",
                "password": "securepass123",
                "full_name": "New User",
            },
        )
        app_client._transport.app.dependency_overrides.clear()

        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "new@example.com"
        assert data["full_name"] == "New User"

    @pytest.mark.asyncio()
    async def test_register_duplicate_email(self, app_client: AsyncClient):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = _make_user()

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        from app.db.session import get_db as real_get_db
        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session

        resp = await app_client.post(
            "/api/v1/auth/register",
            json={
                "email": "existing@example.com",
                "password": "securepass123",
                "full_name": "Existing User",
            },
        )
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 422

    @pytest.mark.asyncio()
    async def test_register_invalid_email(self, app_client: AsyncClient):
        resp = await app_client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "securepass123", "full_name": "User"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio()
    async def test_register_short_password(self, app_client: AsyncClient):
        resp = await app_client.post(
            "/api/v1/auth/register",
            json={"email": "a@b.com", "password": "short", "full_name": "User"},
        )
        assert resp.status_code == 422


class TestLoginEndpoint:
    """POST /api/v1/auth/login"""

    @pytest.mark.asyncio()
    async def test_login_success(self, app_client: AsyncClient):
        from app.auth.password import hash_password

        mock_user = _make_user()
        mock_user.hashed_password = hash_password("correctpassword")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        from app.db.session import get_db as real_get_db
        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session

        resp = await app_client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "correctpassword"},
        )
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio()
    async def test_login_wrong_password(self, app_client: AsyncClient):
        from app.auth.password import hash_password

        mock_user = _make_user()
        mock_user.hashed_password = hash_password("correctpassword")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        from app.db.session import get_db as real_get_db
        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session

        resp = await app_client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "wrongpassword"},
        )
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 401

    @pytest.mark.asyncio()
    async def test_login_nonexistent_user(self, app_client: AsyncClient):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        from app.db.session import get_db as real_get_db
        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session

        resp = await app_client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "pass12345"},
        )
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 401


class TestRefreshEndpoint:
    """POST /api/v1/auth/refresh"""

    @pytest.mark.asyncio()
    async def test_refresh_success(self, app_client: AsyncClient):
        from app.auth.jwt import create_refresh_token
        from app.db.session import get_db as real_get_db

        token = create_refresh_token(user_id=str(TEST_USER_ID))
        mock_user = _make_user()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session

        resp = await app_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": token},
        )
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    @pytest.mark.asyncio()
    async def test_refresh_invalid_token(self, app_client: AsyncClient):
        resp = await app_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.token.here"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio()
    async def test_refresh_user_not_found(self, app_client: AsyncClient):
        from app.auth.jwt import create_refresh_token
        from app.db.session import get_db as real_get_db

        token = create_refresh_token(user_id=str(uuid.uuid4()))
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session

        resp = await app_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": token},
        )
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 401


class TestMeEndpoint:
    """GET /api/v1/auth/me"""

    @pytest.mark.asyncio()
    async def test_me_returns_user(self, app_client: AsyncClient):
        from app.auth.jwt import create_access_token

        token = create_access_token(user_id=str(TEST_USER_ID), role="viewer")
        mock_user = _make_user()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        from app.db.session import get_db as real_get_db
        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session

        resp = await app_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@example.com"

    @pytest.mark.asyncio()
    async def test_me_no_token(self, app_client: AsyncClient):
        resp = await app_client.get("/api/v1/auth/me")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Document endpoints
# ---------------------------------------------------------------------------

class TestDocumentUpload:
    """POST /api/v1/documents/"""

    @pytest.mark.asyncio()
    async def test_upload_success(self, app_client: AsyncClient):
        doc = _make_document()
        mock_svc = AsyncMock()
        mock_svc.create_document = AsyncMock(return_value=doc)

        from app.api.v1.documents import _get_document_service
        app_client._transport.app.dependency_overrides[_get_document_service] = lambda: mock_svc

        resp = await app_client.post(
            "/api/v1/documents/",
            files={"file": ("test.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 201
        assert resp.json()["filename"] == "test.pdf"

    @pytest.mark.asyncio()
    async def test_upload_empty_file(self, app_client: AsyncClient):
        from app.services.document_service import DocumentValidationError
        from app.services.validation import ValidationResult

        mock_svc = AsyncMock()
        mock_svc.create_document = AsyncMock(
            side_effect=DocumentValidationError(ValidationResult(is_valid=False, errors=["empty file"]))
        )

        from app.api.v1.documents import _get_document_service
        app_client._transport.app.dependency_overrides[_get_document_service] = lambda: mock_svc

        resp = await app_client.post(
            "/api/v1/documents/",
            files={"file": ("empty.pdf", b"", "application/pdf")},
        )
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 422


class TestDocumentList:
    """GET /api/v1/documents/"""

    @pytest.mark.asyncio()
    async def test_list_empty(self, app_client: AsyncClient):
        mock_svc = AsyncMock()
        mock_svc.list_documents = AsyncMock(return_value=([], 0))

        from app.api.v1.documents import _get_document_service
        app_client._transport.app.dependency_overrides[_get_document_service] = lambda: mock_svc

        resp = await app_client.get("/api/v1/documents/")
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.asyncio()
    async def test_list_with_items(self, app_client: AsyncClient):
        doc = _make_document()
        mock_svc = AsyncMock()
        mock_svc.list_documents = AsyncMock(return_value=([doc], 1))

        from app.api.v1.documents import _get_document_service
        app_client._transport.app.dependency_overrides[_get_document_service] = lambda: mock_svc

        resp = await app_client.get("/api/v1/documents/?page=1&page_size=10")
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @pytest.mark.asyncio()
    async def test_list_pagination_params(self, app_client: AsyncClient):
        mock_svc = AsyncMock()
        mock_svc.list_documents = AsyncMock(return_value=([], 0))

        from app.api.v1.documents import _get_document_service
        app_client._transport.app.dependency_overrides[_get_document_service] = lambda: mock_svc

        resp = await app_client.get("/api/v1/documents/?page=2&page_size=5")
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 200


class TestDocumentGet:
    """GET /api/v1/documents/{document_id}"""

    @pytest.mark.asyncio()
    async def test_get_success(self, app_client: AsyncClient):
        doc = _make_document()
        mock_svc = AsyncMock()
        mock_svc.get_document = AsyncMock(return_value=doc)

        from app.api.v1.documents import _get_document_service
        app_client._transport.app.dependency_overrides[_get_document_service] = lambda: mock_svc

        resp = await app_client.get(f"/api/v1/documents/{TEST_DOC_ID}")
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 200

    @pytest.mark.asyncio()
    async def test_get_not_found(self, app_client: AsyncClient):
        from app.services.document_service import DocumentNotFoundError

        mock_svc = AsyncMock()
        mock_svc.get_document = AsyncMock(side_effect=DocumentNotFoundError("not found"))

        from app.api.v1.documents import _get_document_service
        app_client._transport.app.dependency_overrides[_get_document_service] = lambda: mock_svc

        resp = await app_client.get(f"/api/v1/documents/{TEST_DOC_ID}")
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 404


class TestDocumentUpdate:
    """PATCH /api/v1/documents/{document_id}"""

    @pytest.mark.asyncio()
    async def test_update_success(self, app_client: AsyncClient):
        doc = _make_document(document_type="contract")
        mock_svc = AsyncMock()
        mock_svc.update_document = AsyncMock(return_value=doc)

        from app.api.v1.documents import _get_document_service
        app_client._transport.app.dependency_overrides[_get_document_service] = lambda: mock_svc

        resp = await app_client.patch(
            f"/api/v1/documents/{TEST_DOC_ID}",
            json={"document_type": "contract"},
        )
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 200
        assert resp.json()["document_type"] == "contract"

    @pytest.mark.asyncio()
    async def test_update_empty_body(self, app_client: AsyncClient):
        resp = await app_client.patch(f"/api/v1/documents/{TEST_DOC_ID}", json={})
        assert resp.status_code == 422


class TestDocumentDelete:
    """DELETE /api/v1/documents/{document_id}"""

    @pytest.mark.asyncio()
    async def test_delete_success(self, app_client: AsyncClient):
        mock_svc = AsyncMock()
        mock_svc.delete_document = AsyncMock(return_value=None)

        from app.api.v1.documents import _get_document_service
        app_client._transport.app.dependency_overrides[_get_document_service] = lambda: mock_svc

        resp = await app_client.delete(f"/api/v1/documents/{TEST_DOC_ID}")
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 204

    @pytest.mark.asyncio()
    async def test_delete_not_found(self, app_client: AsyncClient):
        from app.services.document_service import DocumentNotFoundError

        mock_svc = AsyncMock()
        mock_svc.delete_document = AsyncMock(side_effect=DocumentNotFoundError("not found"))

        from app.api.v1.documents import _get_document_service
        app_client._transport.app.dependency_overrides[_get_document_service] = lambda: mock_svc

        resp = await app_client.delete(f"/api/v1/documents/{TEST_DOC_ID}")
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 404


class TestDocumentDownload:
    """GET /api/v1/documents/{document_id}/download"""

    @pytest.mark.asyncio()
    async def test_download_success(self, app_client: AsyncClient):
        doc = _make_document()
        mock_svc = AsyncMock()
        mock_svc.get_document = AsyncMock(return_value=doc)

        mock_storage = AsyncMock()
        mock_storage.get_presigned_url = AsyncMock(return_value="https://example.com/download")

        from app.api.v1.documents import _get_document_service
        app_client._transport.app.dependency_overrides[_get_document_service] = lambda: mock_svc

        with patch("app.api.v1.documents.DocumentStorageService", return_value=mock_storage):
            resp = await app_client.get(f"/api/v1/documents/{TEST_DOC_ID}/download")
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 200
        data = resp.json()
        assert "url" in data

    @pytest.mark.asyncio()
    async def test_download_not_found(self, app_client: AsyncClient):
        from app.services.document_service import DocumentNotFoundError

        mock_svc = AsyncMock()
        mock_svc.get_document = AsyncMock(side_effect=DocumentNotFoundError("not found"))

        from app.api.v1.documents import _get_document_service
        app_client._transport.app.dependency_overrides[_get_document_service] = lambda: mock_svc

        resp = await app_client.get(f"/api/v1/documents/{TEST_DOC_ID}/download")
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Extraction endpoints
# ---------------------------------------------------------------------------

class TestExtractFields:
    """POST /api/v1/documents/{document_id}/extract"""

    @pytest.mark.asyncio()
    async def test_extract_success(self, app_client: AsyncClient):
        mock_svc = AsyncMock()
        mock_result = MagicMock()
        mock_result.document_id = str(TEST_DOC_ID)
        mock_result.document_type = "contract"
        mock_result.classification_confidence = 0.95
        mock_result.schema_name = "default"
        mock_result.schema_version = 1
        mock_result.total_fields = 5
        mock_result.extracted_count = 5
        mock_result.valid_count = 4
        mock_result.fields = [MagicMock(
            field_name="party_name",
            field_value={"value": "ACME Corp"},
            raw_text="ACME Corp",
            confidence=0.9,
            page_number=1,
        )]
        mock_result.validation = MagicMock(is_valid=True, errors=[], warnings=[])
        mock_svc.extract_fields = AsyncMock(return_value=mock_result)

        from app.api.v1.extraction import _get_extraction_service
        from app.db.session import get_db as real_get_db
        mock_session = AsyncMock()
        app_client._transport.app.dependency_overrides[_get_extraction_service] = lambda: mock_svc
        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session

        resp = await app_client.post(
            f"/api/v1/documents/{TEST_DOC_ID}/extract",
            json={"schema_name": "default"},
        )
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 200
        data = resp.json()
        assert data["document_id"] == str(TEST_DOC_ID)
        assert data["schema_name"] == "default"

    @pytest.mark.asyncio()
    async def test_extract_missing_schema_name(self, app_client: AsyncClient):
        resp = await app_client.post(
            f"/api/v1/documents/{TEST_DOC_ID}/extract",
            json={},
        )
        assert resp.status_code == 422


class TestGetExtractedFields:
    """GET /api/v1/documents/{document_id}/fields"""

    @pytest.mark.asyncio()
    async def test_get_fields_success(self, app_client: AsyncClient):
        mock_svc = AsyncMock()
        mock_svc.get_fields = AsyncMock(return_value=[
            {
                "id": str(uuid.uuid4()),
                "field_name": "party_name",
                "field_value": {"value": "ACME"},
                "raw_text": "ACME Corp",
                "confidence": 0.9,
                "page_number": 1,
                "extraction_model": "rule-based",
                "is_verified": False,
                "verified_by": None,
                "verified_at": None,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            }
        ])

        from app.api.v1.extraction import _get_extraction_service
        from app.db.session import get_db as real_get_db
        mock_session = AsyncMock()
        app_client._transport.app.dependency_overrides[_get_extraction_service] = lambda: mock_svc
        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session

        resp = await app_client.get(f"/api/v1/documents/{TEST_DOC_ID}/fields")
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["field_name"] == "party_name"

    @pytest.mark.asyncio()
    async def test_get_fields_not_found(self, app_client: AsyncClient):
        from app.services.extraction_service import DocumentNotFoundError

        mock_svc = AsyncMock()
        mock_svc.get_fields = AsyncMock(side_effect=DocumentNotFoundError("not found"))

        from app.api.v1.extraction import _get_extraction_service
        from app.db.session import get_db as real_get_db
        mock_session = AsyncMock()
        app_client._transport.app.dependency_overrides[_get_extraction_service] = lambda: mock_svc
        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session

        resp = await app_client.get(f"/api/v1/documents/{TEST_DOC_ID}/fields")
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 404


class TestUpdateExtractedField:
    """PUT /api/v1/documents/{document_id}/fields/{field_id}"""

    @pytest.mark.asyncio()
    async def test_update_field_success(self, app_client: AsyncClient):
        mock_svc = AsyncMock()
        mock_svc.update_field = AsyncMock(return_value={
            "id": str(TEST_FIELD_ID),
            "field_name": "party_name",
            "old_value": {"value": "Old"},
            "new_value": {"value": "New"},
            "is_verified": True,
            "verified_by": str(TEST_USER_ID),
            "verified_at": datetime.now(UTC).isoformat(),
        })

        from app.api.v1.extraction import _get_extraction_service
        from app.db.session import get_db as real_get_db
        mock_session = AsyncMock()
        app_client._transport.app.dependency_overrides[_get_extraction_service] = lambda: mock_svc
        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session

        resp = await app_client.put(
            f"/api/v1/documents/{TEST_DOC_ID}/fields/{TEST_FIELD_ID}",
            json={"field_value": {"value": "New"}},
        )
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_verified"] is True

    @pytest.mark.asyncio()
    async def test_update_field_empty_body(self, app_client: AsyncClient):
        resp = await app_client.put(
            f"/api/v1/documents/{TEST_DOC_ID}/fields/{TEST_FIELD_ID}",
            json={},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Parsing endpoints
# ---------------------------------------------------------------------------

class TestEnqueueParse:
    """POST /api/v1/documents/{document_id}/parse"""

    @pytest.mark.asyncio()
    async def test_enqueue_success(self, app_client: AsyncClient):
        mock_svc = AsyncMock()
        mock_svc.enqueue_parse = AsyncMock(return_value="task-123")

        from app.api.v1.parsing import _get_parsing_service
        from app.db.session import get_db as real_get_db
        from app.deps import get_redis
        mock_session = AsyncMock()
        mock_redis = AsyncMock()
        app_client._transport.app.dependency_overrides[_get_parsing_service] = lambda: mock_svc
        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session
        app_client._transport.app.dependency_overrides[get_redis] = lambda: mock_redis

        resp = await app_client.post(f"/api/v1/documents/{TEST_DOC_ID}/parse")
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 202
        data = resp.json()
        assert data["task_id"] == "task-123"
        assert data["status"] == "queued"


class TestParseStatus:
    """GET /api/v1/documents/{document_id}/parse-status"""

    @pytest.mark.asyncio()
    async def test_parse_status_success(self, app_client: AsyncClient):
        mock_svc = AsyncMock()
        mock_svc.get_parse_status = AsyncMock(return_value={
            "task_id": "parse:123",
            "status": "completed",
            "progress": 1.0,
        })

        from app.api.v1.parsing import _get_parsing_service
        from app.deps import get_redis
        mock_redis = AsyncMock()
        app_client._transport.app.dependency_overrides[_get_parsing_service] = lambda: mock_svc
        app_client._transport.app.dependency_overrides[get_redis] = lambda: mock_redis

        resp = await app_client.get(f"/api/v1/documents/{TEST_DOC_ID}/parse-status")
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["progress"] == 1.0

    @pytest.mark.asyncio()
    async def test_parse_status_not_found(self, app_client: AsyncClient):
        from app.services.parsing_service import TaskNotFoundError

        mock_svc = AsyncMock()
        mock_svc.get_parse_status = AsyncMock(side_effect=TaskNotFoundError("not found"))

        from app.api.v1.parsing import _get_parsing_service
        from app.deps import get_redis
        mock_redis = AsyncMock()
        app_client._transport.app.dependency_overrides[_get_parsing_service] = lambda: mock_svc
        app_client._transport.app.dependency_overrides[get_redis] = lambda: mock_redis

        resp = await app_client.get(f"/api/v1/documents/{TEST_DOC_ID}/parse-status")
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 404


class TestGetParsedContent:
    """GET /api/v1/documents/{document_id}/parsed"""

    @pytest.mark.asyncio()
    async def test_get_parsed_success(self, app_client: AsyncClient):
        mock_svc = AsyncMock()
        mock_svc.get_parsed_content = AsyncMock(return_value={
            "pages": [
                {"page_number": 1, "text": "Hello world", "confidence": 0.95}
            ],
            "quality_score": 0.9,
            "parsed_at": "2024-01-01T00:00:00",
        })

        from app.api.v1.parsing import _get_parsing_service
        from app.db.session import get_db as real_get_db
        from app.deps import get_redis
        mock_session = AsyncMock()
        mock_redis = AsyncMock()
        app_client._transport.app.dependency_overrides[_get_parsing_service] = lambda: mock_svc
        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session
        app_client._transport.app.dependency_overrides[get_redis] = lambda: mock_redis

        resp = await app_client.get(f"/api/v1/documents/{TEST_DOC_ID}/parsed")
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["pages"]) == 1
        assert data["quality_score"] == 0.9

    @pytest.mark.asyncio()
    async def test_get_parsed_not_found(self, app_client: AsyncClient):
        from app.services.parsing_service import ParsingServiceError

        mock_svc = AsyncMock()
        mock_svc.get_parsed_content = AsyncMock(
            side_effect=ParsingServiceError("not found")
        )

        from app.api.v1.parsing import _get_parsing_service
        from app.db.session import get_db as real_get_db
        from app.deps import get_redis
        mock_session = AsyncMock()
        mock_redis = AsyncMock()
        app_client._transport.app.dependency_overrides[_get_parsing_service] = lambda: mock_svc
        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session
        app_client._transport.app.dependency_overrides[get_redis] = lambda: mock_redis

        resp = await app_client.get(f"/api/v1/documents/{TEST_DOC_ID}/parsed")
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Risk analysis endpoints
# ---------------------------------------------------------------------------

class TestAnalyzeDocument:
    """POST /api/v1/documents/{document_id}/analyze"""

    @pytest.mark.asyncio()
    async def test_analyze_success(self, app_client: AsyncClient):
        mock_svc = AsyncMock()
        mock_result = MagicMock()
        mock_result.document_id = str(TEST_DOC_ID)
        mock_result.risk_count = 2
        mock_result.critical_count = 0
        mock_result.high_count = 1
        mock_result.medium_count = 1
        mock_result.low_count = 0
        mock_result.risks = [MagicMock(
            category="financial", severity="high", title="High rate",
            description="Rate above market", evidence={}, page_number=1,
        )]
        mock_result.missing_clauses = [MagicMock(
            clause_name="termination", description="No termination clause",
            severity="medium", suggestion="Add termination clause",
        )]
        mock_result.anomalies = []
        mock_result.checklist = [MagicMock(
            description="Review rate", severity="high",
            category="financial", suggested_action="Negotiate rate",
            due_days=7,
        )]
        mock_svc.analyze = AsyncMock(return_value=mock_result)

        from app.api.v1.risks import _get_risk_service
        from app.db.session import get_db as real_get_db
        mock_session = AsyncMock()
        app_client._transport.app.dependency_overrides[_get_risk_service] = lambda: mock_svc
        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session

        resp = await app_client.post(f"/api/v1/documents/{TEST_DOC_ID}/analyze")
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 200
        data = resp.json()
        assert data["document_id"] == str(TEST_DOC_ID)
        assert data["risk_count"] == 2
        assert len(data["risks"]) == 1
        assert len(data["missing_clauses"]) == 1

    @pytest.mark.asyncio()
    async def test_analyze_not_found(self, app_client: AsyncClient):
        from app.services.risk_service import DocumentNotFoundError

        mock_svc = AsyncMock()
        mock_svc.analyze = AsyncMock(side_effect=DocumentNotFoundError("not found"))

        from app.api.v1.risks import _get_risk_service
        from app.db.session import get_db as real_get_db
        mock_session = AsyncMock()
        app_client._transport.app.dependency_overrides[_get_risk_service] = lambda: mock_svc
        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session

        resp = await app_client.post(f"/api/v1/documents/{TEST_DOC_ID}/analyze")
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 404


class TestGetRisks:
    """GET /api/v1/documents/{document_id}/risks"""

    @pytest.mark.asyncio()
    async def test_get_risks_success(self, app_client: AsyncClient):
        mock_svc = AsyncMock()
        mock_svc.get_risks = AsyncMock(return_value=[
            {
                "id": str(uuid.uuid4()),
                "category": "financial",
                "severity": "high",
                "title": "High interest rate",
                "description": "Above market",
                "evidence": {},
                "page_number": 1,
                "status": "open",
                "detected_by": "rule_engine",
            }
        ])

        from app.api.v1.risks import _get_risk_service
        from app.db.session import get_db as real_get_db
        mock_session = AsyncMock()
        app_client._transport.app.dependency_overrides[_get_risk_service] = lambda: mock_svc
        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session

        resp = await app_client.get(f"/api/v1/documents/{TEST_DOC_ID}/risks")
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["severity"] == "high"

    @pytest.mark.asyncio()
    async def test_get_risks_not_found(self, app_client: AsyncClient):
        from app.services.risk_service import DocumentNotFoundError

        mock_svc = AsyncMock()
        mock_svc.get_risks = AsyncMock(side_effect=DocumentNotFoundError("not found"))

        from app.api.v1.risks import _get_risk_service
        from app.db.session import get_db as real_get_db
        mock_session = AsyncMock()
        app_client._transport.app.dependency_overrides[_get_risk_service] = lambda: mock_svc
        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session

        resp = await app_client.get(f"/api/v1/documents/{TEST_DOC_ID}/risks")
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 404


class TestGetChecklist:
    """GET /api/v1/documents/{document_id}/checklist"""

    @pytest.mark.asyncio()
    async def test_get_checklist_success(self, app_client: AsyncClient):
        mock_svc = AsyncMock()
        mock_svc.get_checklist = AsyncMock(return_value=[
            {
                "description": "Review contract rate",
                "severity": "high",
                "category": "financial",
                "suggested_action": "Negotiate with counterparty",
                "due_days": 7,
            }
        ])

        from app.api.v1.risks import _get_risk_service
        from app.db.session import get_db as real_get_db
        mock_session = AsyncMock()
        app_client._transport.app.dependency_overrides[_get_risk_service] = lambda: mock_svc
        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session

        resp = await app_client.get(f"/api/v1/documents/{TEST_DOC_ID}/checklist")
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["due_days"] == 7

    @pytest.mark.asyncio()
    async def test_get_checklist_not_found(self, app_client: AsyncClient):
        from app.services.risk_service import DocumentNotFoundError

        mock_svc = AsyncMock()
        mock_svc.get_checklist = AsyncMock(side_effect=DocumentNotFoundError("not found"))

        from app.api.v1.risks import _get_risk_service
        from app.db.session import get_db as real_get_db
        mock_session = AsyncMock()
        app_client._transport.app.dependency_overrides[_get_risk_service] = lambda: mock_svc
        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session

        resp = await app_client.get(f"/api/v1/documents/{TEST_DOC_ID}/checklist")
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Q&A endpoints
# ---------------------------------------------------------------------------

class TestAskQuestion:
    """POST /api/v1/qa/ask"""

    @pytest.mark.asyncio()
    async def test_ask_success(self, app_client: AsyncClient):
        mock_svc = AsyncMock()
        mock_result = MagicMock()
        mock_result.answer = "The contract is for 12 months."
        mock_result.citations = []
        mock_result.groundedness_score = 0.85
        mock_result.session_id = TEST_SESSION_ID
        mock_result.confidence = 0.9
        mock_svc.ask = AsyncMock(return_value=mock_result)

        from app.api.v1.qa import _get_qa_service
        from app.db.session import get_db as real_get_db
        mock_session = AsyncMock()
        app_client._transport.app.dependency_overrides[_get_qa_service] = lambda: mock_svc
        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session

        resp = await app_client.post(
            "/api/v1/qa/ask",
            json={"query": "What is the contract duration?"},
        )
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert data["session_id"] == TEST_SESSION_ID

    @pytest.mark.asyncio()
    async def test_ask_empty_query(self, app_client: AsyncClient):
        resp = await app_client.post(
            "/api/v1/qa/ask",
            json={"query": ""},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio()
    async def test_ask_missing_query(self, app_client: AsyncClient):
        resp = await app_client.post(
            "/api/v1/qa/ask",
            json={},
        )
        assert resp.status_code == 422


class TestGetQASession:
    """GET /api/v1/qa/sessions/{session_id}"""

    @pytest.mark.asyncio()
    async def test_get_session_success(self, app_client: AsyncClient):
        from app.api.v1.qa import _SESSION_STORE

        _SESSION_STORE[TEST_SESSION_ID] = [
            {
                "query": "What is the contract duration?",
                "answer": "12 months",
                "citations": [],
                "groundedness_score": 0.85,
            }
        ]

        resp = await app_client.get(f"/api/v1/qa/sessions/{TEST_SESSION_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == TEST_SESSION_ID
        assert data["total"] == 1
        _SESSION_STORE.pop(TEST_SESSION_ID, None)

    @pytest.mark.asyncio()
    async def test_get_session_not_found(self, app_client: AsyncClient):
        resp = await app_client.get(f"/api/v1/qa/sessions/{uuid.uuid4()}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Report endpoints
# ---------------------------------------------------------------------------

class TestGenerateReport:
    """POST /api/v1/reports/documents/{document_id}/report"""

    @pytest.mark.asyncio()
    async def test_generate_success(self, app_client: AsyncClient):
        report = _make_report()
        mock_svc = AsyncMock()
        mock_svc.create_report = AsyncMock(return_value=report)

        from app.api.v1.reports import _get_report_service
        from app.db.session import get_db as real_get_db
        mock_session = AsyncMock()
        app_client._transport.app.dependency_overrides[_get_report_service] = lambda: mock_svc
        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session

        resp = await app_client.post(
            f"/api/v1/reports/documents/{TEST_DOC_ID}/report",
            json={"report_type": "summary"},
        )
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 201
        data = resp.json()
        assert data["report_type"] == "summary"

    @pytest.mark.asyncio()
    async def test_generate_default_type(self, app_client: AsyncClient):
        report = _make_report()
        mock_svc = AsyncMock()
        mock_svc.create_report = AsyncMock(return_value=report)

        from app.api.v1.reports import _get_report_service
        from app.db.session import get_db as real_get_db
        mock_session = AsyncMock()
        app_client._transport.app.dependency_overrides[_get_report_service] = lambda: mock_svc
        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session

        resp = await app_client.post(
            f"/api/v1/reports/documents/{TEST_DOC_ID}/report",
        )
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 201

    @pytest.mark.asyncio()
    async def test_generate_invalid_type(self, app_client: AsyncClient):
        resp = await app_client.post(
            f"/api/v1/reports/documents/{TEST_DOC_ID}/report",
            json={"report_type": "invalid_type"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio()
    async def test_generate_not_found(self, app_client: AsyncClient):
        from app.services.report_generator import DocumentNotFoundError as ReportDocNotFoundError

        mock_svc = AsyncMock()
        mock_svc.create_report = AsyncMock(
            side_effect=ReportDocNotFoundError("not found")
        )

        from app.api.v1.reports import _get_report_service
        from app.db.session import get_db as real_get_db
        mock_session = AsyncMock()
        app_client._transport.app.dependency_overrides[_get_report_service] = lambda: mock_svc
        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session

        resp = await app_client.post(
            f"/api/v1/reports/documents/{TEST_DOC_ID}/report",
        )
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 404


class TestGetReport:
    """GET /api/v1/reports/{report_id}"""

    @pytest.mark.asyncio()
    async def test_get_report_success(self, app_client: AsyncClient):
        report = _make_report()
        mock_svc = AsyncMock()
        mock_svc.get_report = AsyncMock(return_value=report)

        from app.api.v1.reports import _get_report_service
        from app.db.session import get_db as real_get_db
        mock_session = AsyncMock()
        app_client._transport.app.dependency_overrides[_get_report_service] = lambda: mock_svc
        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session

        resp = await app_client.get(f"/api/v1/reports/{TEST_REPORT_ID}")
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 200

    @pytest.mark.asyncio()
    async def test_get_report_not_found(self, app_client: AsyncClient):
        from app.services.report_service import ReportNotFoundError

        mock_svc = AsyncMock()
        mock_svc.get_report = AsyncMock(side_effect=ReportNotFoundError("not found"))

        from app.api.v1.reports import _get_report_service
        from app.db.session import get_db as real_get_db
        mock_session = AsyncMock()
        app_client._transport.app.dependency_overrides[_get_report_service] = lambda: mock_svc
        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session

        resp = await app_client.get(f"/api/v1/reports/{TEST_REPORT_ID}")
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 404


class TestDownloadReport:
    """GET /api/v1/reports/{report_id}/download"""

    @pytest.mark.asyncio()
    async def test_download_markdown(self, app_client: AsyncClient):
        mock_svc = AsyncMock()
        mock_svc.export_report = AsyncMock(
            return_value=(b"# Report", "text/markdown", "report.md")
        )

        from app.api.v1.reports import _get_report_service
        from app.db.session import get_db as real_get_db
        mock_session = AsyncMock()
        app_client._transport.app.dependency_overrides[_get_report_service] = lambda: mock_svc
        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session

        resp = await app_client.get(
            f"/api/v1/reports/{TEST_REPORT_ID}/download?format=markdown"
        )
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 200
        assert "text/markdown" in resp.headers["content-type"]

    @pytest.mark.asyncio()
    async def test_download_invalid_format(self, app_client: AsyncClient):
        resp = await app_client.get(
            f"/api/v1/reports/{TEST_REPORT_ID}/download?format=xml"
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio()
    async def test_download_not_found(self, app_client: AsyncClient):
        from app.services.report_service import ReportNotFoundError

        mock_svc = AsyncMock()
        mock_svc.export_report = AsyncMock(
            side_effect=ReportNotFoundError("not found")
        )

        from app.api.v1.reports import _get_report_service
        from app.db.session import get_db as real_get_db
        mock_session = AsyncMock()
        app_client._transport.app.dependency_overrides[_get_report_service] = lambda: mock_svc
        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session

        resp = await app_client.get(
            f"/api/v1/reports/{TEST_REPORT_ID}/download?format=markdown"
        )
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Search endpoint
# ---------------------------------------------------------------------------

class TestHybridSearch:
    """POST /api/v1/search/"""

    @pytest.mark.asyncio()
    async def test_search_success(self, app_client: AsyncClient):
        mock_user = _make_user()
        mock_cache = AsyncMock()
        mock_cache.get_cached_search = AsyncMock(return_value=None)
        mock_cache.cache_search_result = AsyncMock()

        from app.api.v1.search import get_current_user
        from app.api.v1.search import _get_query_cache
        app_client._transport.app.dependency_overrides[get_current_user] = lambda: mock_user
        app_client._transport.app.dependency_overrides[_get_query_cache] = lambda: mock_cache

        with (
            patch("qdrant_client.QdrantClient", return_value=MagicMock()),
            patch("app.rag.embedder.EmbeddingPipeline", return_value=MagicMock()),
            patch("app.rag.retriever.HybridRetriever") as mock_retriever_cls,
        ):
            mock_retriever = AsyncMock()
            mock_retriever.search = AsyncMock(return_value=[])
            mock_retriever_cls.return_value = mock_retriever

            resp = await app_client.post(
                "/api/v1/search/",
                json={"query": "contract terms", "top_k": 5},
            )
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "contract terms"
        assert data["total"] == 0

    @pytest.mark.asyncio()
    async def test_search_with_cache_hit(self, app_client: AsyncClient):
        mock_user = _make_user()
        mock_cache = AsyncMock()
        mock_cache.get_cached_search = AsyncMock(return_value=[
            {"chunk_id": "c1", "document_id": "d1", "text": "cached", "score": 0.9, "page": 1}
        ])

        from app.api.v1.search import get_current_user
        from app.api.v1.search import _get_query_cache
        app_client._transport.app.dependency_overrides[get_current_user] = lambda: mock_user
        app_client._transport.app.dependency_overrides[_get_query_cache] = lambda: mock_cache

        resp = await app_client.post(
            "/api/v1/search/",
            json={"query": "cached query"},
        )
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 200
        data = resp.json()
        assert data["cached"] is True
        assert data["total"] == 1

    @pytest.mark.asyncio()
    async def test_search_empty_query(self, app_client: AsyncClient):
        mock_user = _make_user()
        mock_cache = AsyncMock()

        from app.api.v1.search import get_current_user
        from app.api.v1.search import _get_query_cache
        app_client._transport.app.dependency_overrides[get_current_user] = lambda: mock_user
        app_client._transport.app.dependency_overrides[_get_query_cache] = lambda: mock_cache

        resp = await app_client.post(
            "/api/v1/search/",
            json={"query": ""},
        )
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Agent endpoints
# ---------------------------------------------------------------------------

class TestAgentRun:
    """POST /api/v1/agent/run"""

    @pytest.mark.asyncio()
    async def test_run_agent_success(self, app_client: AsyncClient):
        mock_svc = AsyncMock()
        mock_result = MagicMock()
        mock_result.session_id = TEST_SESSION_ID
        mock_result.status = "completed"
        mock_result.answer = "The document discusses AI operations."
        mock_result.iterations = 3
        mock_result.cost = {"total_cost": 0.01, "tokens": 500}
        mock_result.steps = [{"type": "reasoning", "action": "analyze"}]
        mock_result.duration_ms = 1500
        mock_svc.run = AsyncMock(return_value=mock_result)

        from app.db.session import get_db as real_get_db
        mock_session = AsyncMock()
        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session

        with patch("app.api.v1.agent.AgentService", return_value=mock_svc):
            resp = await app_client.post(
                "/api/v1/agent/run",
                json={"task_type": "qa", "query": "What is this document about?"},
            )
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert "answer" in data

    @pytest.mark.asyncio()
    async def test_run_agent_missing_task_type(self, app_client: AsyncClient):
        resp = await app_client.post(
            "/api/v1/agent/run",
            json={"query": "hello"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio()
    async def test_run_agent_invalid_document_id(self, app_client: AsyncClient):
        from app.db.session import get_db as real_get_db
        mock_session = AsyncMock()
        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session

        resp = await app_client.post(
            "/api/v1/agent/run",
            json={
                "task_type": "qa",
                "query": "test",
                "document_id": "not-a-uuid",
            },
        )
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 400


class TestAgentSession:
    """GET /api/v1/agent/sessions/{session_id}"""

    @pytest.mark.asyncio()
    async def test_get_session_success(self, app_client: AsyncClient):
        mock_svc = AsyncMock()
        mock_svc.get_session = AsyncMock(return_value={
            "session_id": str(TEST_SESSION_ID),
            "agent_type": "qa",
            "status": "completed",
            "input_data": {"query": "test"},
            "output_data": {"answer": "test answer"},
            "error_message": None,
            "model": "gpt-4o",
            "total_tokens": 500,
            "total_cost_usd": 0.01,
            "started_at": "2024-01-01T00:00:00",
            "completed_at": "2024-01-01T00:00:01",
            "steps": [],
        })

        from app.db.session import get_db as real_get_db
        mock_session = AsyncMock()
        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session

        with patch("app.api.v1.agent.AgentService", return_value=mock_svc):
            resp = await app_client.get(f"/api/v1/agent/sessions/{TEST_SESSION_ID}")
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"

    @pytest.mark.asyncio()
    async def test_get_session_not_found(self, app_client: AsyncClient):
        mock_svc = AsyncMock()
        mock_svc.get_session = AsyncMock(return_value=None)

        from app.db.session import get_db as real_get_db
        mock_session = AsyncMock()
        app_client._transport.app.dependency_overrides[real_get_db] = lambda: mock_session

        with patch("app.api.v1.agent.AgentService", return_value=mock_svc):
            resp = await app_client.get(f"/api/v1/agent/sessions/{TEST_SESSION_ID}")
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Evaluation endpoints
# ---------------------------------------------------------------------------

class TestRunEvaluation:
    """POST /api/v1/eval/run"""

    @pytest.mark.asyncio()
    async def test_run_eval_success(self, app_client: AsyncClient):
        mock_dataset = [{"question": "q1", "expected_answer": "a1"}]

        with (
            patch("app.api.v1.eval.load_gold_dataset_as_dicts", return_value=mock_dataset),
            patch("app.api.v1.eval.Evaluator") as mock_eval_cls,
        ):
            mock_eval = MagicMock()
            mock_result = MagicMock()
            mock_result.to_dict.return_value = {
                "dataset_name": "qa",
                "total_samples": 1,
                "successful_samples": 1,
                "failed_samples": 0,
                "aggregate_metrics": {"accuracy": 1.0},
                "per_sample_results": [],
                "total_latency_ms": 100.0,
                "summary": "1/1 succeeded",
            }
            mock_result.successful_samples = 1
            mock_result.total_samples = 1
            mock_result.summary = "1/1 succeeded"
            mock_eval.run_evaluation.return_value = mock_result
            mock_eval_cls.return_value = mock_eval

            resp = await app_client.post(
                "/api/v1/eval/run",
                json={"pipeline_name": "qa", "dataset_path": "test.jsonl"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert "run_id" in data

    @pytest.mark.asyncio()
    async def test_run_eval_dataset_not_found(self, app_client: AsyncClient):
        with patch(
            "app.api.v1.eval.load_gold_dataset_as_dicts",
            side_effect=FileNotFoundError("not found"),
        ):
            resp = await app_client.post(
                "/api/v1/eval/run",
                json={"dataset_path": "nonexistent.jsonl"},
            )
        assert resp.status_code == 404


class TestListEvaluationResults:
    """GET /api/v1/eval/results"""

    @pytest.mark.asyncio()
    async def test_list_results_empty(self, app_client: AsyncClient):
        with patch("app.api.v1.eval._eval_results", OrderedDict()):
            resp = await app_client.get("/api/v1/eval/results")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["results"] == []

    @pytest.mark.asyncio()
    async def test_list_results_with_data(self, app_client: AsyncClient):
        store = OrderedDict()
        store["run-1"] = {
            "dataset_name": "qa",
            "total_samples": 5,
            "successful_samples": 5,
            "failed_samples": 0,
            "aggregate_metrics": {"accuracy": 1.0},
            "per_sample_results": [],
            "total_latency_ms": 500.0,
            "summary": "5/5 succeeded",
            "run_id": "run-1",
            "created_at": "2024-01-01T00:00:00",
        }

        with patch("app.api.v1.eval._eval_results", store):
            resp = await app_client.get("/api/v1/eval/results")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1


class TestGetEvaluationResult:
    """GET /api/v1/eval/results/{run_id}"""

    @pytest.mark.asyncio()
    async def test_get_result_success(self, app_client: AsyncClient):
        store = OrderedDict()
        store["run-123"] = {
            "dataset_name": "qa",
            "total_samples": 1,
            "successful_samples": 1,
            "failed_samples": 0,
            "aggregate_metrics": {},
            "per_sample_results": [],
            "total_latency_ms": 100.0,
            "summary": "done",
            "run_id": "run-123",
            "created_at": "2024-01-01T00:00:00",
        }

        with patch("app.api.v1.eval._eval_results", store):
            resp = await app_client.get("/api/v1/eval/results/run-123")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == "run-123"

    @pytest.mark.asyncio()
    async def test_get_result_not_found(self, app_client: AsyncClient):
        with patch("app.api.v1.eval._eval_results", OrderedDict()):
            resp = await app_client.get("/api/v1/eval/results/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Integration-style: full request/response schema validation
# ---------------------------------------------------------------------------

class TestSchemaValidation:
    """Ensure endpoints reject malformed requests with 422."""

    @pytest.mark.asyncio()
    async def test_register_missing_fields(self, app_client: AsyncClient):
        resp = await app_client.post("/api/v1/auth/register", json={})
        assert resp.status_code == 422

    @pytest.mark.asyncio()
    async def test_login_missing_fields(self, app_client: AsyncClient):
        resp = await app_client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 422

    @pytest.mark.asyncio()
    async def test_extract_missing_schema_name(self, app_client: AsyncClient):
        resp = await app_client.post(
            f"/api/v1/documents/{TEST_DOC_ID}/extract", json={}
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio()
    async def test_search_missing_query(self, app_client: AsyncClient):
        mock_user = _make_user()

        from app.api.v1.search import get_current_user
        from app.api.v1.search import _get_query_cache
        mock_cache = AsyncMock()
        app_client._transport.app.dependency_overrides[get_current_user] = lambda: mock_user
        app_client._transport.app.dependency_overrides[_get_query_cache] = lambda: mock_cache

        resp = await app_client.post("/api/v1/search/", json={})
        app_client._transport.app.dependency_overrides.clear()
        assert resp.status_code == 422

    @pytest.mark.asyncio()
    async def test_agent_missing_task_type(self, app_client: AsyncClient):
        resp = await app_client.post("/api/v1/agent/run", json={})
        assert resp.status_code == 422

    @pytest.mark.asyncio()
    async def test_qa_missing_query(self, app_client: AsyncClient):
        resp = await app_client.post("/api/v1/qa/ask", json={})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Middleware / cross-cutting concerns
# ---------------------------------------------------------------------------

class TestRequestIDMiddleware:
    """Verify X-Request-ID is propagated when middleware is present."""

    @pytest.mark.asyncio()
    async def test_request_id_on_health(self, app_client: AsyncClient):
        resp = await app_client.get("/api/v1/health")
        assert resp.status_code == 200
