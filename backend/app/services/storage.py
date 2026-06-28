"""Document storage service wrapping MinIO operations."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

from app.config import get_settings
from app.storage.minio import MinioStorage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StorageResult:
    """Result of a successful document upload."""

    storage_path: str
    checksum: str
    size: int


class DocumentStorageService:
    """High-level document storage operations backed by MinIO.

    Args:
        storage: Optional ``MinioStorage`` instance. Created from settings if omitted.
    """

    def __init__(self, storage: MinioStorage | None = None) -> None:
        settings = get_settings()
        self._storage = storage or MinioStorage(settings)
        self._bucket_ensured = False

    async def _ensure_bucket(self) -> None:
        if not self._bucket_ensured:
            await self._storage.ensure_bucket()
            self._bucket_ensured = True

    async def upload_document(
        self,
        file_bytes: bytes,
        filename: str,
        document_id: str,
        user_id: str,
        content_type: str = "application/octet-stream",
    ) -> StorageResult:
        """Upload a document to MinIO.

        Args:
            file_bytes: Raw file content.
            filename: Sanitised filename for the object key.
            document_id: Document UUID string.
            user_id: Owner UUID string.
            content_type: MIME type of the file.

        Returns:
            ``StorageResult`` with the storage path, SHA-256 checksum, and byte size.

        Raises:
            RuntimeError: If the upload fails.
        """
        await self._ensure_bucket()
        storage_path = self._build_storage_path(user_id, document_id, filename)
        checksum = self._compute_checksum(file_bytes)
        size = len(file_bytes)

        await self._storage.upload_file(
            object_name=storage_path,
            data=file_bytes,
            length=size,
            content_type=content_type,
        )

        logger.info(
            "Document uploaded: path=%s size=%d checksum=%s",
            storage_path,
            size,
            checksum,
        )

        return StorageResult(storage_path=storage_path, checksum=checksum, size=size)

    async def download_document(self, storage_path: str) -> bytes:
        """Download a document from MinIO.

        Args:
            storage_path: The object key returned by ``upload_document``.

        Returns:
            Raw bytes of the document.
        """
        return await self._storage.download_file(object_name=storage_path)

    async def get_presigned_url(
        self,
        storage_path: str,
        expiry_seconds: int = 3600,
    ) -> str:
        """Generate a presigned download URL.

        Args:
            storage_path: The object key.
            expiry_seconds: URL validity duration in seconds.

        Returns:
            Presigned URL string.
        """
        return await self._storage.get_presigned_url(
            object_name=storage_path,
            expires=expiry_seconds,
        )

    async def delete_document(self, storage_path: str) -> None:
        """Delete a document from MinIO.

        Args:
            storage_path: The object key to remove.
        """
        await self._storage.delete_file(object_name=storage_path)
        logger.info("Document deleted from storage: %s", storage_path)

    @staticmethod
    def _build_storage_path(user_id: str, document_id: str, filename: str) -> str:
        return f"{user_id}/{document_id}/{filename}"

    @staticmethod
    def _compute_checksum(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()
