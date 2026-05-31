"""OpenNotebook — FastAPI dependency injection.

Provides reusable dependencies for database sessions and authentication.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import decode_token
from app.infrastructure.db.models import User
from app.infrastructure.db.session import get_db

# ── Security Scheme ──────────────────────────────────────────────────────────

_bearer_scheme = HTTPBearer(auto_error=True)


# ── Dependencies ─────────────────────────────────────────────────────────────

# Re-export get_db so routes can import from one place
DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
    db: DbSession,
) -> User:
    """Extract and validate the Bearer token, then load the user from the DB.

    Raises:
        HTTPException 401: If the token is invalid, expired, revoked,
            or the user does not exist / is inactive.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise credentials_exception

    if payload.type != "access":
        raise credentials_exception

    result = await db.execute(
        select(User).where(User.id == payload.sub)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    return user


# Annotated type alias for route handlers
CurrentUser = Annotated[User, Depends(get_current_user)]
