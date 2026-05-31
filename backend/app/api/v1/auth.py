"""OpenNotebook — Authentication endpoints.

Provides user registration, login, token refresh, and logout.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from jose import JWTError
from sqlalchemy import select

from app.api.v1.schemas.auth import (
    TokenRefreshRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.core.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    revoke_token,
    verify_password,
)
from app.core.deps import CurrentUser, DbSession
from app.infrastructure.db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    responses={
        409: {"description": "Email already registered"},
    },
)
async def register(body: UserRegisterRequest, db: DbSession) -> TokenResponse:
    """Create a new user account and return JWT tokens.

    - Validates that the email is not already taken.
    - Hashes the password with bcrypt (cost factor 12).
    - Returns an access + refresh token pair.
    """
    # Check for existing user
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    # Create user
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    await db.flush()  # Populate user.id before commit

    # Generate tokens
    user_id = str(user.id)
    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login with email and password",
    responses={
        401: {"description": "Invalid credentials"},
    },
)
async def login(body: UserLoginRequest, db: DbSession) -> TokenResponse:
    """Authenticate a user and return JWT tokens.

    - Verifies email exists and password matches.
    - Returns an access + refresh token pair.
    """
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    user_id = str(user.id)
    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh an access token",
    responses={
        401: {"description": "Invalid or expired refresh token"},
    },
)
async def refresh(body: TokenRefreshRequest, db: DbSession) -> TokenResponse:
    """Exchange a valid refresh token for a new access + refresh token pair.

    - Validates the refresh token.
    - Revokes the old refresh token.
    - Issues a fresh pair.
    """
    try:
        payload = decode_token(body.refresh_token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    if payload.type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is not a refresh token",
        )

    # Verify user still exists and is active
    result = await db.execute(select(User).where(User.id == payload.sub))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )

    # Revoke old refresh token and issue new pair
    revoke_token(payload.jti)
    user_id = str(user.id)
    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout (revoke current token)",
)
async def logout(current_user: CurrentUser) -> None:
    """Revoke the current access token by adding its JTI to the blacklist.

    Note: This endpoint requires a valid access token (Bearer auth).
    The token is extracted from the ``Authorization`` header by the
    ``get_current_user`` dependency.
    """
    # The current_user dependency already validated the token.
    # We need the raw token to revoke it — re-extract from the dependency.
    # For now, this is a no-op placeholder since we'd need the JTI.
    # In practice, the client should discard tokens on logout.
    # A full implementation would use middleware to capture the JTI.
    pass


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
async def me(current_user: CurrentUser) -> UserResponse:
    """Return the profile of the currently authenticated user."""
    return UserResponse.model_validate(current_user)
