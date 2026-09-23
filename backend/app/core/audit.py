"""OpenNotebook — Active Audit Logging Service.

Provides immutable audit trail recording for security and enterprise compliance (SOC 2, ISO 27001).
All mutating actions and security-relevant events MUST be recorded.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models import AuditLog

logger = logging.getLogger(__name__)


async def record_audit_event(
    db: AsyncSession,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    user_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    """Record an immutable audit log entry in PostgreSQL.

    Args:
        db: Active async database session.
        action: Event action name (e.g., 'user.login', 'notebook.create').
        resource_type: Type of resource affected ('user', 'notebook', 'source', etc.).
        resource_id: Optional UUID or identifier of the affected resource.
        user_id: Optional ID of the user performing the action.
        details: Optional JSON-serializable dictionary with extra context (IP, diffs, etc.).

    Returns:
        The created AuditLog ORM instance.
    """
    audit_entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        details=details or {},
    )
    db.add(audit_entry)
    try:
        await db.flush()
        logger.info(
            "Audit event recorded: action=%s resource_type=%s resource_id=%s user_id=%s",
            action,
            resource_type,
            resource_id,
            user_id,
        )
    except Exception as exc:
        logger.error("Failed to record audit event %s: %s", action, exc)

    return audit_entry
