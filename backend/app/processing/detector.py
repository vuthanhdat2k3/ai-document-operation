from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_MAGIC_SIGNATURES: list[tuple[bytes, str]] = [
    (b"%PDF-", "application/pdf"),
    (b"PK\x03\x04", None),  # ZIP-based — need extension check
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "application/vnd.ms-excel"),  # OLE2
]

_ZIP_EXTENSION_MAP: dict[str, str] = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

_EXTENSION_MAP: dict[str, str] = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".csv": "text/csv",
    ".txt": "text/plain",
    ".rtf": "application/rtf",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".ods": "application/vnd.oasis.opendocument.spreadsheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def detect_file_type(file_path: Path) -> str:
    """Detect the MIME type of *file_path*.

    Uses magic-byte detection first, then falls back to the file extension.

    Args:
        file_path: Path to the file.

    Returns:
        A MIME type string (e.g. ``"application/pdf"``).
        Returns ``"application/octet-stream"`` if the type cannot be determined.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    mime = _detect_by_magic(file_path)
    if mime:
        return mime

    return _detect_by_extension(file_path)


def _detect_by_magic(file_path: Path) -> str | None:
    try:
        with open(file_path, "rb") as fh:
            header = fh.read(8)
    except OSError:
        logger.debug("Could not read magic bytes from %s", file_path, exc_info=True)
        return None

    for signature, mime in _MAGIC_SIGNATURES:
        if header.startswith(signature):
            if mime is not None:
                return mime
            # ZIP-based format — need extension disambiguation
            return _detect_zip_by_extension(file_path)
    return None


def _detect_zip_by_extension(file_path: Path) -> str | None:
    suffix = file_path.suffix.lower()
    return _ZIP_EXTENSION_MAP.get(suffix)


def _detect_by_extension(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    mime = _EXTENSION_MAP.get(suffix)
    if mime:
        return mime
    logger.warning("Unknown file extension '%s' for %s", suffix, file_path)
    return "application/octet-stream"
