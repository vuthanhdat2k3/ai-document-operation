"""Password hashing and verification using bcrypt directly."""

import bcrypt


def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt.

    Args:
        plain: Plaintext password.

    Returns:
        Bcrypt hash string.
    """
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash.

    Args:
        plain: Plaintext password to check.
        hashed: Stored bcrypt hash.

    Returns:
        ``True`` if the password matches.
    """
    return bcrypt.checkpw(plain.encode(), hashed.encode())
