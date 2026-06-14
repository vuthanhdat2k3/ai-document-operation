"""Local filesystem storage backend — development fallback.

Implements the same async interface as ``MinioStorage`` so the two are
interchangeable via dependency injection. Files are stored under a
configurable base directory.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path
from typing import BinaryIO
from urllib.parse import quote

logger = logging.getLogger(__name__)


class LocalFileStorage:
    """Async file-system storage for local development.

    All methods mirror :class:`MinioStorage` so either can be injected
    without changing calling code.

    Args:
        base_dir: Root directory where files are stored.
        url_prefix: HTTP path prefix used when generating URLs
            (e.g. ``"/uploads"``).
    """

    def __init__(self, base_dir: str | Path = "uploads", url_prefix: str = "/uploads") -> None:
        self._base = Path(base_dir).resolve()
        self._base.mkdir(parents=True, exist_ok=True)
        self._url_prefix = url_prefix.rstrip("/")

    def _resolve(self, object_name: str) -> Path:
        """Resolve an object name to an absolute path, preventing path traversal.

        Args:
            object_name: Relative key / path.

        Returns:
            Absolute ``Path`` inside the base directory.

        Raises:
            ValueError: If the resolved path escapes the base directory.
        """
        target = (self._base / object_name).resolve()
        if not str(target).startswith(str(self._base)):
            raise ValueError(f"Path traversal detected: {object_name}")
        return target

    @staticmethod
    def _write_stream(dest: Path, data: BinaryIO) -> None:
        """Write a binary stream to a file (runs in thread)."""
        with open(dest, "wb") as fh:
            shutil.copyfileobj(data, fh)

    async def ensure_bucket(self, bucket_name: str | None = None) -> None:
        """No-op for local storage (directory is created at init).

        Args:
            bucket_name: Ignored — present for interface compatibility.
        """
        self._base.mkdir(parents=True, exist_ok=True)

    async def upload_file(
        self,
        object_name: str,
        data: bytes | BinaryIO,
        length: int | None = None,
        content_type: str = "application/octet-stream",
        bucket_name: str | None = None,
    ) -> str:
        """Write file content to disk.

        Args:
            object_name: Relative path under the base directory.
            data: ``bytes`` or readable binary stream.
            length: Ignored for local storage.
            content_type: Stored for future reference (unused on disk).
            bucket_name: Ignored — present for interface compatibility.

        Returns:
            The object name.
        """
        dest = self._resolve(object_name)
        dest.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(data, bytes):
            await asyncio.to_thread(dest.write_bytes, data)
        else:
            await asyncio.to_thread(self._write_stream, dest, data)

        logger.info("Stored locally: %s (%s)", dest, content_type)
        return object_name

    async def download_file(
        self,
        object_name: str,
        bucket_name: str | None = None,
    ) -> bytes:
        """Read a file from disk.

        Args:
            object_name: Relative path under the base directory.
            bucket_name: Ignored.

        Returns:
            File contents as bytes.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        src = self._resolve(object_name)
        if not await asyncio.to_thread(src.exists):
            raise FileNotFoundError(f"Object not found: {object_name}")
        return await asyncio.to_thread(src.read_bytes)

    async def delete_file(
        self,
        object_name: str,
        bucket_name: str | None = None,
    ) -> None:
        """Delete a file from disk.

        Args:
            object_name: Relative path under the base directory.
            bucket_name: Ignored.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        src = self._resolve(object_name)
        if not await asyncio.to_thread(src.exists):
            raise FileNotFoundError(f"Object not found: {object_name}")
        await asyncio.to_thread(src.unlink)
        logger.info("Deleted locally: %s", src)

    async def get_presigned_url(
        self,
        object_name: str,
        expires: int = 3600,
        bucket_name: str | None = None,
    ) -> str:
        """Return a static local URL for the object.

        In development this is a simple path; no expiry is enforced.

        Args:
            object_name: Relative path.
            expires: Ignored for local storage.
            bucket_name: Ignored.

        Returns:
            URL path string (e.g. ``/uploads/doc.pdf``).
        """
        safe_name = quote(object_name, safe="/")
        return f"{self._url_prefix}/{safe_name}"

    async def health_check(self) -> bool:
        """Verify the base directory exists and is writable.

        Returns:
            ``True`` if the directory is accessible.
        """
        try:
            await asyncio.to_thread(self._base.mkdir, True, True)
            test_file = self._base / ".health_check"

            def _write_and_clean() -> None:
                test_file.write_text("ok")
                test_file.unlink()

            await asyncio.to_thread(_write_and_clean)
            return True
        except Exception:
            logger.exception("Local storage health check failed")
            return False
