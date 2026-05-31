"""OpenNotebook — SQLAlchemy declarative base with common mixins.

All models inherit from ``Base`` which provides:
- ``id``: UUID primary key with server-side default
- ``created_at``: timezone-aware timestamp, server-side NOW()
- ``updated_at``: timezone-aware timestamp, auto-updated on change
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Abstract declarative base for all OpenNotebook models."""

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
