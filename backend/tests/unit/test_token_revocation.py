"""OpenNotebook — Unit tests for JWT token revocation."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch
import pytest
from jose import JWTError

import app.infrastructure.redis.client
from app.core.auth import (
    _revoked_jtis,
    create_access_token,
    decode_token,
    is_token_revoked,
    revoke_token,
)


@pytest.fixture(autouse=True)
def clear_revocation_cache():
    """Clear in-memory revocation set before and after each test."""
    _revoked_jtis.clear()
    yield
    _revoked_jtis.clear()


def test_revoke_token_with_redis():
    """Revoking a token records it in Redis and in-memory set with expected TTL."""
    mock_redis = MagicMock()
    test_jti = str(uuid.uuid4())

    with patch("app.infrastructure.redis.client.get_sync_redis", return_value=mock_redis):
        revoke_token(test_jti, expires_in_seconds=3600)

    assert test_jti in _revoked_jtis
    mock_redis.setex.assert_called_once_with(f"revoked_jti:{test_jti}", 3600, "1")


def test_revoke_token_redis_failure_fallback():
    """If Redis fails, revoke_token should not raise and should still record in local memory."""
    test_jti = str(uuid.uuid4())

    with patch("app.infrastructure.redis.client.get_sync_redis", side_effect=Exception("Redis down")):
        revoke_token(test_jti)

    assert test_jti in _revoked_jtis
    assert is_token_revoked(test_jti) is True


def test_is_token_revoked_from_memory():
    """is_token_revoked returns True immediately if found in memory set."""
    test_jti = str(uuid.uuid4())
    _revoked_jtis.add(test_jti)

    assert is_token_revoked(test_jti) is True


def test_is_token_revoked_from_redis():
    """is_token_revoked checks Redis if not in local memory."""
    mock_redis = MagicMock()
    mock_redis.exists.return_value = 1
    test_jti = str(uuid.uuid4())

    with patch("app.infrastructure.redis.client.get_sync_redis", return_value=mock_redis):
        revoked = is_token_revoked(test_jti)

    assert revoked is True
    mock_redis.exists.assert_called_once_with(f"revoked_jti:{test_jti}")


def test_is_token_not_revoked():
    """is_token_revoked returns False when absent from both memory and Redis."""
    mock_redis = MagicMock()
    mock_redis.exists.return_value = 0
    test_jti = str(uuid.uuid4())

    with patch("app.infrastructure.redis.client.get_sync_redis", return_value=mock_redis):
        revoked = is_token_revoked(test_jti)

    assert revoked is False


def test_decode_token_raises_when_revoked():
    """decode_token rejects revoked access tokens."""
    user_id = str(uuid.uuid4())
    token = create_access_token(user_id)

    # Decode once to get JTI and verify it is valid initially
    payload = decode_token(token)
    assert payload.sub == user_id

    # Revoke it
    revoke_token(payload.jti)

    with pytest.raises(JWTError, match="revoked"):
        decode_token(token)
