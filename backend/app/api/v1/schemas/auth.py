"""OpenNotebook — Auth request/response schemas (Pydantic v2 strict mode)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegisterRequest(BaseModel):
    """Request body for user registration."""

    model_config = ConfigDict(strict=True)

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class UserLoginRequest(BaseModel):
    """Request body for user login."""

    model_config = ConfigDict(strict=True)

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Response containing JWT access and refresh tokens."""

    model_config = ConfigDict(strict=True)

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefreshRequest(BaseModel):
    """Request body to refresh an access token."""

    model_config = ConfigDict(strict=True)

    refresh_token: str


class UserResponse(BaseModel):
    """Public-facing user representation."""

    model_config = ConfigDict(strict=True, from_attributes=True)

    id: uuid.UUID
    email: str
    is_active: bool
    created_at: datetime
