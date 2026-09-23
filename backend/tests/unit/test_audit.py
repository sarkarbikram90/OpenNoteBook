"""OpenNotebook — Unit tests for the Active Audit Logging Service."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.core.audit import record_audit_event
from app.infrastructure.db.models import AuditLog


@pytest.mark.asyncio
async def test_record_audit_event_success() -> None:
    """Validate that audit events are properly constructed and flushed to the database."""
    mock_db = AsyncMock()
    user_id = uuid.uuid4()
    resource_id = str(uuid.uuid4())

    entry = await record_audit_event(
        db=mock_db,
        action="notebook.create",
        resource_type="notebook",
        resource_id=resource_id,
        user_id=user_id,
        details={"name": "AI Safety Research"},
    )

    mock_db.add.assert_called_once()
    mock_db.flush.assert_awaited_once()

    assert entry.action == "notebook.create"
    assert entry.resource_type == "notebook"
    assert entry.resource_id == resource_id
    assert entry.user_id == user_id
    assert entry.details == {"name": "AI Safety Research"}


@pytest.mark.asyncio
async def test_record_audit_event_handles_db_exception() -> None:
    """Audit recording failure should not crash the caller."""
    mock_db = AsyncMock()
    mock_db.flush.side_effect = Exception("DB Connection Error")

    entry = await record_audit_event(
        db=mock_db,
        action="user.login",
        resource_type="user",
        user_id=uuid.uuid4(),
    )

    assert entry.action == "user.login"
