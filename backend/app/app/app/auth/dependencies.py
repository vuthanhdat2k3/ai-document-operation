"""FastAPI dependencies for authentication and authorization."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import jwt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select

from app.api.middleware.error_handler import ForbiddenError, UnauthorizedError
from app.auth.jwt import decode_token
from app.db.models.user import User

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),  # noqa: B008
    db: AsyncSession = Depends(__import__("app.db.session", fromlist=["get_db"]).get_db),  # noqa: B008
) -> User:
    """Extract and validate the current user from the JWT bearer token.

    Args:
        token: OAuth2 bearer token from the ``Authorization`` header.
        db: Async database session.

    Returns:
        The authenticated ``User`` ORM instance.

    Raises:
        UnauthorizedError: If the token is invalid, expired, or the user
            does not exist / is inactive.
    """
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("Invalid authentication token.") from exc

    if payload.get("type") != "access":
        raise UnauthorizedError("Invalid token type.")

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Token missing subject claim.")

    try:
        uid = UUID(user_id)
    except ValueError as exc:
        raise UnauthorizedError("Invalid user ID in token.") from exc

    result = await db.execute(
        select(User).where(User.id == uid, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise UnauthorizedError("User not found.")
    if not user.is_active:
        raise UnauthorizedError("User account is deactivated.")

    return user


def require_role(*roles: str):
    """FastAPI dependency factory that checks the current user's role.

    Args:
        *roles: Allowed role names (e.g. ``"admin"``, ``"analyst"``).

    Returns:
        A FastAPI dependency that raises 403 if the user's role is not
        in the allowed set.
    """

    async def _role_checker(
        current_user: User = Depends(get_current_user),  # noqa: B008
    ) -> User:
        if current_user.role not in roles:
            raise ForbiddenError(
                f"Role '{current_user.role}' is not authorized. "
                f"Required: {', '.join(roles)}."
            )
        return current_user

    return _role_checker
