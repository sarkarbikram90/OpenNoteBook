"""OpenNotebook — JWT authentication and password hashing.

Provides:
- bcrypt password hashing (cost factor 12)
- JWT access token (15 min) and refresh token (7 days)
- Token decoding with type validation
- Token revocation via JTI blacklist
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

import bcrypt
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import get_settings

settings = get_settings()

# ── Password Hashing ────────────────────────────────────────────────────────


def hash_password(plain: str) -> str:
    """Hash a plaintext password using bcrypt with configured cost factor."""
    salt = bcrypt.gensalt(rounds=settings.bcrypt_cost_factor)
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ── Token Payload ────────────────────────────────────────────────────────────


class TokenPayload(BaseModel):
    """Decoded JWT payload."""

    sub: str  # user_id
    exp: datetime
    iat: datetime
    jti: str
    type: Literal["access", "refresh"]


# ── Token Revocation ─────────────────────────────────────────────────────────

# In-memory JTI blacklist. Will be replaced with Redis in a later phase.
_revoked_jtis: set[str] = set()


def revoke_token(jti: str) -> None:
    """Add a JTI to the revocation blacklist."""
    _revoked_jtis.add(jti)


def is_token_revoked(jti: str) -> bool:
    """Check whether a JTI has been revoked."""
    return jti in _revoked_jtis


# ── Token Creation ───────────────────────────────────────────────────────────


def create_access_token(user_id: str) -> str:
    """Create a short-lived access token (15 min by default).

    Args:
        user_id: The UUID of the user (stored as ``sub`` claim).

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(UTC)
    jti = str(uuid.uuid4())
    payload = {
        "sub": user_id,
        "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
        "iat": now,
        "jti": jti,
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str) -> str:
    """Create a long-lived refresh token (7 days by default).

    Args:
        user_id: The UUID of the user (stored as ``sub`` claim).

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(UTC)
    jti = str(uuid.uuid4())
    payload = {
        "sub": user_id,
        "exp": now + timedelta(days=settings.jwt_refresh_token_expire_days),
        "iat": now,
        "jti": jti,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> TokenPayload:
    """Decode and validate a JWT token.

    Args:
        token: Encoded JWT string.

    Returns:
        Validated token payload.

    Raises:
        JWTError: If the token is invalid, expired, or revoked.
    """
    try:
        raw = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        raise

    payload = TokenPayload(**raw)

    if is_token_revoked(payload.jti):
        raise JWTError("Token has been revoked")

    return payload
