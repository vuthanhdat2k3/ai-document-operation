"""MinIO object storage client wrapper with async support via thread executor."""

from __future__ import annotations

import asyncio
import io
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import BinaryIO

from minio import Minio

from app.config import Settings

logger = logging.getLogger(__name__)

_EXECUTOR = ThreadPoolExecutor(max_workers=4)


class MinioStorage:
    """Synchronous MinIO client wrapped with async convenience methods.

    The underlying ``minio`` Python SDK is synchronous; all public I/O methods
    are ``async`` and delegate to a thread-pool executor so they never block
    the event loop.

    Args:
        settings: Application settings containing MinIO connection details.
    """

    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.MINIO_BUCKET
        self._client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_USE_SSL,
        )

    async def ensure_bucket(self, bucket_name: str | None = None) -> None:
        """Create the bucket if it does not already exist.

        Args:
            bucket_name: Override bucket name. Defaults to settings bucket.
        """
        name = bucket_name or self._bucket
        loop = asyncio.get_running_loop()
        exists = await loop.run_in_executor(_EXECUTOR, self._client.bucket_exists, name)
        if not exists:
            await loop.run_in_executor(_EXECUTOR, self._client.make_bucket, name)
            logger.info("Created MinIO bucket: %s", name)
        else:
            logger.debug("MinIO bucket already exists: %s", name)

    async def upload_file(
        self,
        object_name: str,
        data: bytes | BinaryIO,
        length: int | None = None,
        content_type: str = "application/octet-stream",
        bucket_name: str | None = None,
    ) -> str:
        """Upload an object to MinIO.

        Args:
            object_name: Target key (path) inside the bucket.
            data: File content as ``bytes`` or a readable binary stream.
            length: Byte length of *data*. Required when *data* is a stream.
            content_type: MIME type of the object.
            bucket_name: Override bucket name.

        Returns:
            The object name (key) of the uploaded file.
        """
        name = bucket_name or self._bucket
        if isinstance(data, bytes):
            stream: BinaryIO = io.BytesIO(data)
            length = len(data)
        else:
            stream = data

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            _EXECUTOR,
            lambda: self._client.put_object(
                bucket_name=name,
                object_name=object_name,
                data=stream,
                length=length,
                content_type=content_type,
            ),
        )
        logger.info("Uploaded %s/%s (%s)", name, object_name, content_type)
        return object_name

    async def download_file(
        self,
        object_name: str,
        bucket_name: str | None = None,
    ) -> bytes:
        """Download an object from MinIO.

        Args:
            object_name: Key of the object to retrieve.
            bucket_name: Override bucket name.

        Returns:
            Raw bytes of the object.
        """
        name = bucket_name or self._bucket
        loop = asyncio.get_running_loop()

        def _download() -> bytes:
            response = self._client.get_object(bucket_name=name, object_name=object_name)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()

        data = await loop.run_in_executor(_EXECUTOR, _download)
        logger.debug("Downloaded %s/%s (%d bytes)", name, object_name, len(data))
        return data

    async def delete_file(
        self,
        object_name: str,
        bucket_name: str | None = None,
    ) -> None:
        """Delete an object from MinIO.

        Args:
            object_name: Key of the object to delete.
            bucket_name: Override bucket name.
        """
        name = bucket_name or self._bucket
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            _EXECUTOR,
            lambda: self._client.remove_object(bucket_name=name, object_name=object_name),
        )
        logger.info("Deleted %s/%s", name, object_name)

    async def get_presigned_url(
        self,
        object_name: str,
        expires: int = 3600,
        bucket_name: str | None = None,
    ) -> str:
        """Generate a presigned download URL.

        Args:
            object_name: Key of the object.
            expires: URL validity in seconds (default 1 hour).
            bucket_name: Override bucket name.

        Returns:
            Presigned URL string.
        """
        name = bucket_name or self._bucket
        loop = asyncio.get_running_loop()
        url = await loop.run_in_executor(
            _EXECUTOR,
            lambda: self._client.presigned_get_object(
                bucket_name=name,
                object_name=object_name,
                expires=expires,
            ),
        )
        return url  # type: ignore[no-any-return]

    async def health_check(self) -> bool:
        """Verify MinIO connectivity by listing buckets.

        Returns:
            ``True`` if the server responds successfully.
        """
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(_EXECUTOR, self._client.list_buckets)
            return True
        except Exception:
            logger.exception("MinIO health check failed")
            return False
