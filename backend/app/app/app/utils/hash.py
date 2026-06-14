"""SHA-256 content hashing utilities."""

import hashlib


def content_hash(data: bytes) -> str:
    """Compute SHA-256 hex digest of the given bytes.

    Args:
        data: Raw bytes to hash.

    Returns:
        Hexadecimal SHA-256 digest string.
    """
    return hashlib.sha256(data).hexdigest()
