"""File handling utilities."""

import re
from pathlib import Path


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename by removing unsafe characters.

    Strips path separators, null bytes, and replaces sequences of
    non-alphanumeric characters (except ``-``, ``_``, ``.``) with underscores.

    Args:
        filename: The original filename to sanitize.

    Returns:
        A safe filename string.
    """
    name = Path(filename).name
    name = name.replace("\x00", "")
    name = re.sub(r"[^\w\-.]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "unnamed"


def get_file_extension(filename: str) -> str:
    """Extract the lowercase file extension without the leading dot.

    Args:
        filename: The filename to extract the extension from.

    Returns:
        The lowercase extension string (e.g. ``"pdf"``), or empty string
        if no extension is found.
    """
    return Path(filename).suffix.lstrip(".").lower()
