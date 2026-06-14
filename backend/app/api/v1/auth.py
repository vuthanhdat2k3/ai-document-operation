"""Authentication API endpoints: register, login, refresh, me."""
import uuid
from datetime import datetime
from uuid import UUID


import jwt
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.error_handler import UnauthorizedError, ValidationErrorDetail
from app.api.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.auth.dependencies import get_current_user
from app.auth.jwt import create_access_token, create_refresh_token, decode_token
from app.auth.password import hash_password, verify_password
from app.db.models.user import User
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> UserResponse:
    """Register a new user account.

    Args:
        body: Registration payload with email, password, and full_name.
        db: Async database session.

    Returns:
        The newly created user profile.

    Raises:
        ValidationErrorDetail: If the email is already registered.
    """
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none() is not None:
        raise ValidationErrorDetail("Email is already registered.")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role="viewer",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return UserResponse.from_model(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> TokenResponse:
    """Authenticate a user and return JWT tokens.

    Args:
        body: Login payload with email and password.
        db: Async database session.

    Returns:
        Access and refresh token pair.

    Raises:
        UnauthorizedError: If credentials are invalid.
    """
    result = await db.execute(
        select(User).where(User.email == body.email, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.hashed_password):
        raise UnauthorizedError("Invalid email or password.")
    if not user.is_active:
        raise UnauthorizedError("User account is deactivated.")

    access_token = create_access_token(user_id=str(user.id), role=user.role)
    refresh_token = create_refresh_token(user_id=str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> TokenResponse:
    """Exchange a refresh token for a new access/refresh token pair.

    Args:
        body: Payload containing the refresh token.
        db: Async database session.

    Returns:
        New access and refresh token pair.

    Raises:
        UnauthorizedError: If the refresh token is invalid or the user
            no longer exists.
    """
    try:
        payload = decode_token(body.refresh_token)
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Refresh token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("Invalid refresh token.") from exc

    if payload.get("type") != "refresh":
        raise UnauthorizedError("Invalid token type.")

    try:
        user_id = UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise UnauthorizedError("Invalid token subject.") from exc

    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise UnauthorizedError("User not found or deactivated.")

    new_access = create_access_token(user_id=str(user.id), role=user.role)
    new_refresh = create_refresh_token(user_id=str(user.id))

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
    )


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> UserResponse:
    """Return the current authenticated user's profile.

    Args:
        current_user: The authenticated user from the JWT token.

    Returns:
        User profile information.
    """
    return UserResponse.from_model(current_user)
