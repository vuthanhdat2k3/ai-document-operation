"""JWT token creation and validation using PyJWT."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.config import get_settings


def create_access_token(
    user_id: str,
    role: str,
    expires_minutes: int | None = None,
) -> str:
    """Create a signed JWT access token.

    Args:
        user_id: The subject (user UUID as string).
        role: User role (e.g. ``"admin"``, ``"viewer"``).
        expires_minutes: Token lifetime in minutes. Defaults to settings value.

    Returns:
        Encoded JWT string.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + timedelta(
        minutes=expires_minutes or settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    )
    payload = {
        "sub": user_id,
        "role": role,
        "exp": expire,
        "iat": now,
        "jti": str(uuid.uuid4()),
        "type": "access",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(
    user_id: str,
    expires_days: int | None = None,
) -> str:
    """Create a signed JWT refresh token.

    Args:
        user_id: The subject (user UUID as string).
        expires_days: Token lifetime in days. Defaults to settings value.

    Returns:
        Encoded JWT string.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + timedelta(
        days=expires_days or settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS,
    )
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": now,
        "jti": str(uuid.uuid4()),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and verify a JWT token.

    Args:
        token: Encoded JWT string.

    Returns:
        Decoded payload dict with keys ``sub``, ``role``, ``exp``, ``iat``,
        ``jti``, ``type``.

    Raises:
        jwt.ExpiredSignatureError: If the token has expired.
        jwt.InvalidTokenError: If the token is malformed or signature is invalid.
    """
    settings = get_settings()
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
