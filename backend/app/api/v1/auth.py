"""OpenNotebook — Authentication endpoints.

Provides user registration, login, token refresh, and logout.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request, status
from jose import JWTError
from sqlalchemy import select

from app.api.v1.schemas.auth import (
    TokenRefreshRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.core.audit import record_audit_event
from app.core.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    revoke_token,
    verify_password,
)
from app.core.deps import CurrentUser, DbSession
from app.core.limiter import limiter
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
@limiter.limit("20/minute")
async def register(request: Request, body: UserRegisterRequest, db: DbSession) -> TokenResponse:
    """Create a new user account and return JWT tokens.

    - Validates that the email is not already taken.
    - Hashes the password with bcrypt (cost factor 12).
    - Returns an access + refresh token pair.
    - Records audit log event.
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

    user_id = str(user.id)

    # Record audit log
    await record_audit_event(
        db=db,
        action="user.register",
        resource_type="user",
        resource_id=user_id,
        user_id=user.id,
        details={"email": body.email},
    )

    # Generate tokens
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
@limiter.limit("30/minute")
async def login(request: Request, body: UserLoginRequest, db: DbSession) -> TokenResponse:
    """Authenticate a user and return JWT tokens.

    - Verifies email exists and password matches.
    - Returns an access + refresh token pair.
    - Records audit log event.
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

    # Record audit log
    await record_audit_event(
        db=db,
        action="user.login",
        resource_type="user",
        resource_id=user_id,
        user_id=user.id,
        details={"email": body.email},
    )

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
    - Records audit log event.
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

    # Record audit log
    await record_audit_event(
        db=db,
        action="user.refresh_token",
        resource_type="user",
        resource_id=user_id,
        user_id=user.id,
    )

    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout (revoke current token)",
)
async def logout(
    current_user: CurrentUser,
    db: DbSession,
    authorization: str | None = Header(None),
) -> None:
    """Revoke the current access token by adding its JTI to the blacklist."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        try:
            payload = decode_token(token)
            revoke_token(payload.jti)
        except Exception:
            pass

    await record_audit_event(
        db=db,
        action="user.logout",
        resource_type="user",
        resource_id=str(current_user.id),
        user_id=current_user.id,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
async def me(current_user: CurrentUser) -> UserResponse:
    """Return the profile of the currently authenticated user."""
    return UserResponse.model_validate(current_user)
