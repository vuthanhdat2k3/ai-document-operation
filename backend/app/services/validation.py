"""File validation service with MIME type, size, and magic byte checks."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field

from app.config import get_settings

logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES: dict[str, tuple[str, ...]] = {
    "application/pdf": (".pdf",),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (".docx",),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": (".xlsx",),
    "image/png": (".png",),
    "image/jpeg": (".jpg", ".jpeg"),
    "image/tiff": (".tiff", ".tif"),
}

MAGIC_BYTES: list[tuple[str, bytes, tuple[str, ...]]] = [
    ("application/pdf", b"%PDF", (".pdf",)),
    ("image/png", b"\x89PNG", (".png",)),
    ("image/jpeg", b"\xff\xd8\xff", (".jpg", ".jpeg")),
    ("image/tiff", b"II\x2a\x00", (".tiff", ".tif")),
    ("image/tiff", b"MM\x00\x2a", (".tiff", ".tif")),
]

ZIP_MAGIC = b"PK\x03\x04"

_ZIP_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_ZIP_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_INVALID_FILENAME_RE = re.compile(r"[^\w.\- ]")
_MULTI_DOT_RE = re.compile(r"\.{2,}")


@dataclass(frozen=True)
class ValidationResult:
    """Result of file validation."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    detected_mime_type: str | None = None


class FileValidator:
    """Validates uploaded files against size, MIME type, and magic byte rules.

    Usage::

        validator = FileValidator()
        result = validator.validate_file(
            filename="report.pdf",
            content_type="application/pdf",
            file_size=1024,
            file_header=b"%PDF-1.4 ...",
        )
        if not result.is_valid:
            raise ValueError(result.errors)
    """

    def __init__(
        self,
        max_file_size_bytes: int | None = None,
        allowed_mime_types: dict[str, tuple[str, ...]] | None = None,
    ) -> None:
        settings = get_settings()
        self._max_file_size = max_file_size_bytes or (settings.MAX_FILE_SIZE_MB * 1024 * 1024)
        self._allowed = allowed_mime_types or ALLOWED_MIME_TYPES

    def validate_file(
        self,
        filename: str,
        content_type: str,
        file_size: int,
        file_header: bytes,
    ) -> ValidationResult:
        """Validate a file against all rules.

        Args:
            filename: Original filename from the client.
            content_type: Content-Type header value from the upload.
            file_size: Size of the file in bytes.
            file_header: First 8+ bytes of the file for magic byte detection.

        Returns:
            ``ValidationResult`` indicating success or listing errors.
        """
        errors: list[str] = []

        sanitized = self._sanitize_filename(filename)
        if not sanitized:
            errors.append("Filename is empty or contains only invalid characters.")

        size_err = self._check_size(file_size)
        if size_err:
            errors.append(size_err)

        mime_err, detected = self._check_mime_and_magic(content_type, file_header, filename)
        if mime_err:
            errors.append(mime_err)

        is_valid = len(errors) == 0
        if not is_valid:
            logger.warning("Validation failed for %s: %s", filename, errors)

        return ValidationResult(is_valid=is_valid, errors=errors, detected_mime_type=detected)

    def _check_size(self, file_size: int) -> str | None:
        if file_size <= 0:
            return "File is empty."
        if file_size > self._max_file_size:
            max_mb = self._max_file_size / (1024 * 1024)
            return f"File size {file_size / (1024 * 1024):.1f}MB exceeds maximum allowed size of {max_mb:.0f}MB."
        return None

    def _check_mime_and_magic(
        self,
        content_type: str,
        file_header: bytes,
        filename: str,
    ) -> tuple[str | None, str | None]:
        detected = self._detect_mime_from_magic(file_header, filename)

        ct_normalized = content_type.strip().lower().split(";")[0].strip()

        if ct_normalized not in self._allowed:
            return (
                f"Content type '{ct_normalized}' is not allowed. "
                f"Allowed types: {', '.join(sorted(self._allowed))}.",
                detected,
            )

        if detected is None:
            return (
                "Could not verify file type from magic bytes. "
                "File may be corrupted or of an unsupported format.",
                detected,
            )

        if detected != ct_normalized:
            return (
                f"Content type '{ct_normalized}' does not match detected type '{detected}'.",
                detected,
            )

        ext = os.path.splitext(filename.lower())[1]
        allowed_exts = self._allowed.get(detected, ())
        if ext and ext not in allowed_exts:
            return (
                f"File extension '{ext}' does not match detected type '{detected}'. "
                f"Expected one of: {', '.join(allowed_exts)}.",
                detected,
            )

        return None, detected

    def _detect_mime_from_magic(self, header: bytes, filename: str) -> str | None:
        if not header:
            return None

        ext = os.path.splitext(filename.lower())[1]

        if header[:4] == ZIP_MAGIC:
            return self._detect_zip_subtype(header, ext)

        for mime, magic, extensions in MAGIC_BYTES:
            if header[: len(magic)] == magic:
                if mime == "image/tiff" and ext and ext not in extensions:
                    continue
                return mime

        return None

    def _detect_zip_subtype(self, header: bytes, ext: str) -> str | None:
        if ext in (".docx",):
            return _ZIP_DOCX_MIME
        if ext in (".xlsx",):
            return _ZIP_XLSX_MIME
        if not ext:
            return None
        return None

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        name = filename.strip()
        name = os.path.basename(name)
        name = _INVALID_FILENAME_RE.sub("_", name)
        name = _MULTI_DOT_RE.sub(".", name)
        name = name.strip(". ")
        return name
