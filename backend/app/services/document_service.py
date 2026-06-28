"""Document business-logic service combining validation, storage, and persistence."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import delete as sa_delete, func, select
from sqlalchemy.orm import selectinload

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models.document import Document
from app.db.models.document_page import DocumentChunk
from app.services.storage import DocumentStorageService
from app.services.validation import FileValidator, ValidationResult
from app.vector.client import QdrantClientWrapper

logger = logging.getLogger(__name__)


class DocumentServiceError(Exception):
    """Base exception for document service operations."""


class DocumentNotFoundError(DocumentServiceError):
    """Raised when a document cannot be located."""


class DocumentPermissionError(DocumentServiceError):
    """Raised when a user lacks permission to access a document."""


class DocumentValidationError(DocumentServiceError):
    """Raised when file validation fails."""

    def __init__(self, result: ValidationResult) -> None:
        self.result = result
        super().__init__(f"Validation failed: {'; '.join(result.errors)}")


class DocumentService:
    """Orchestrates document validation, storage, and database operations.

    Args:
        validator: Optional ``FileValidator`` override.
        storage: Optional ``DocumentStorageService`` override.
    """

    def __init__(
        self,
        validator: FileValidator | None = None,
        storage: DocumentStorageService | None = None,
    ) -> None:
        self._validator = validator or FileValidator()
        self._storage = storage or DocumentStorageService()

    async def create_document(
        self,
        filename: str,
        content_type: str,
        file_size: int,
        file_bytes: bytes,
        user_id: uuid.UUID,
        db: AsyncSession,
    ) -> Document:
        """Validate, upload, and persist a new document.

        Args:
            filename: Original filename from the upload.
            content_type: MIME type reported by the client.
            file_size: Size of the file in bytes.
            file_bytes: Raw file content.
            user_id: ID of the uploading user.
            db: Active async database session.

        Returns:
            The newly created ``Document`` ORM instance.

        Raises:
            DocumentValidationError: If file validation fails.
        """
        file_header = file_bytes[:8]
        result = self._validator.validate_file(
            filename=filename,
            content_type=content_type,
            file_size=file_size,
            file_header=file_header,
        )
        if not result.is_valid:
            raise DocumentValidationError(result)

        detected_mime = result.detected_mime_type or content_type
        doc_id = uuid.uuid4()

        sanitized = FileValidator._sanitize_filename(filename)

        storage_result = await self._storage.upload_document(
            file_bytes=file_bytes,
            filename=sanitized,
            document_id=str(doc_id),
            user_id=str(user_id),
            content_type=detected_mime,
        )

        document = Document(
            id=doc_id,
            user_id=user_id,
            filename=sanitized,
            original_filename=filename,
            mime_type=detected_mime,
            file_size_bytes=storage_result.size,
            storage_path=storage_result.storage_path,
            storage_backend="minio",
            checksum_sha256=storage_result.checksum,
            status="uploaded",
            uploaded_at=datetime.now(UTC),
        )

        db.add(document)
        await db.flush()
        await db.refresh(document)

        logger.info(
            "Document created: id=%s user=%s file=%s",
            document.id,
            user_id,
            sanitized,
        )
        return document

    async def get_document(
        self,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
        db: AsyncSession,
    ) -> Document:
        """Retrieve a document by ID, verifying ownership.

        Args:
            document_id: The document UUID.
            user_id: The requesting user's UUID.
            db: Active async database session.

        Returns:
            The ``Document`` instance.

        Raises:
            DocumentNotFoundError: If the document does not exist.
            DocumentPermissionError: If the document belongs to another user.
        """
        stmt = (
            select(Document)
            .options(selectinload(Document.pages))
            .where(
                Document.id == document_id,
                Document.deleted_at.is_(None),
            )
        )
        result = await db.execute(stmt)
        document = result.scalar_one_or_none()

        if document is None:
            raise DocumentNotFoundError(f"Document {document_id} not found.")

        if document.user_id != user_id:
            raise DocumentPermissionError(
                f"User {user_id} does not have access to document {document_id}."
            )

        return document

    async def list_documents(
        self,
        user_id: uuid.UUID,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        document_type: str | None = None,
    ) -> tuple[list[Document], int]:
        """List documents for a user with optional filters and pagination.

        Args:
            user_id: The requesting user's UUID.
            db: Active async database session.
            page: 1-indexed page number.
            page_size: Number of results per page (max 100).
            status: Optional status filter.
            document_type: Optional document type filter.

        Returns:
            Tuple of (list of documents, total count).
        """
        page = max(1, page)
        page_size = max(1, min(page_size, 100))

        base_filter = (
            Document.user_id == user_id,
            Document.deleted_at.is_(None),
        )

        count_stmt = select(func.count()).select_from(Document).where(*base_filter)
        if status:
            count_stmt = count_stmt.where(Document.status == status)
        if document_type:
            count_stmt = count_stmt.where(Document.document_type == document_type)

        total_result = await db.execute(count_stmt)
        total = total_result.scalar_one()

        query = (
            select(Document)
            .where(*base_filter)
            .order_by(Document.uploaded_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        if status:
            query = query.where(Document.status == status)
        if document_type:
            query = query.where(Document.document_type == document_type)

        rows_result = await db.execute(query)
        documents = list(rows_result.scalars().all())

        return documents, total

    async def update_document(
        self,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
        updates: dict,
        db: AsyncSession,
    ) -> Document:
        """Update mutable fields on a document.

        Args:
            document_id: The document UUID.
            user_id: The requesting user's UUID.
            updates: Dictionary of field names to new values.
                Allowed keys: ``status``, ``document_type``, ``classification``,
                ``metadata_``, ``page_count``.
            db: Active async database session.

        Returns:
            The updated ``Document`` instance.

        Raises:
            DocumentNotFoundError: If the document does not exist.
            DocumentPermissionError: If the document belongs to another user.
            ValueError: If the updates contain disallowed fields.
        """
        allowed_fields = {"status", "document_type", "classification", "metadata_", "page_count"}
        invalid = set(updates.keys()) - allowed_fields
        if invalid:
            raise ValueError(f"Cannot update fields: {', '.join(sorted(invalid))}")

        document = await self.get_document(document_id, user_id, db)

        for field, value in updates.items():
            setattr(document, field, value)

        await db.flush()
        await db.refresh(document)

        logger.info("Document updated: id=%s fields=%s", document_id, list(updates.keys()))
        return document

    async def delete_document(
        self,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
        db: AsyncSession,
    ) -> None:
        """Soft-delete a document and clean up all associated data.

        Performs, in order:
        1. Delete file from MinIO storage (best-effort).
        2. Delete vector index points from Qdrant (best-effort).
        3. Hard-delete DocumentChunks from PostgreSQL (indexed data, not
           user-facing).
        4. Soft-delete the Document record itself (audit trail).

        Args:
            document_id: The document UUID.
            user_id: The requesting user's UUID.
            db: Active async database session.

        Raises:
            DocumentNotFoundError: If the document does not exist.
            DocumentPermissionError: If the document belongs to another user.
        """
        document = await self.get_document(document_id, user_id, db)

        # 1. Delete file from MinIO storage (best-effort)
        try:
            storage_service = DocumentStorageService()
            await storage_service.delete_document(document.storage_path)
            logger.info("File deleted from storage: %s", document.storage_path)
        except Exception:
            logger.warning("Failed to delete file from storage: %s", document.storage_path, exc_info=True)

        # 2. Delete vector index points from Qdrant (best-effort)
        try:
            settings = get_settings()
            qdrant = QdrantClientWrapper(settings)
            await qdrant.delete_points_by_filter(
                collection_name="document_chunks",
                filter_dict={
                    "must": [{"key": "document_id", "match": {"value": str(document_id)}}],
                },
            )
            await qdrant.close()
            logger.info("Qdrant points deleted for document: %s", document_id)
        except Exception:
            logger.warning("Failed to delete Qdrant points for document: %s", document_id, exc_info=True)

        # 3. Hard-delete DocumentChunks from PostgreSQL
        try:
            await db.execute(
                sa_delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
            )
            logger.info("DocumentChunks hard-deleted for document: %s", document_id)
        except Exception:
            logger.warning(
                "Failed to delete DocumentChunks for document: %s", document_id, exc_info=True
            )

        # 4. Soft-delete the Document record (audit trail)
        document.deleted_at = datetime.now(UTC)
        document.status = "archived"
        await db.flush()

        logger.info("Document soft-deleted: id=%s", document_id)
