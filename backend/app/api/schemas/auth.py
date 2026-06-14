"""Auth request/response schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """User registration request body."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    """User login request body."""

    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """Refresh token request body."""

    refresh_token: str


class TokenResponse(BaseModel):
    """JWT token pair response."""

    model_config = ConfigDict(frozen=True)

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Public user information."""

    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    @classmethod
    def from_model(cls, user: Any) -> "UserResponse":
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
        )


class MessageResponse(BaseModel):
    """Generic message response."""

    model_config = ConfigDict(frozen=True)

    message: str
