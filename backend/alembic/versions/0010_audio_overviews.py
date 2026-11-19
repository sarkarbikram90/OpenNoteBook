"""Create audio_overviews table for Studio Audio Overviews.

Revision ID: 0010
Revises: 0009
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audio_overviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "notebook_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("notebooks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("focus_topic", sa.Text(), nullable=True),
        sa.Column("tone", sa.Text(), server_default="deep_dive", nullable=False),
        sa.Column("status", sa.Text(), server_default="READY", nullable=False),
        sa.Column(
            "script_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("audio_storage_path", sa.Text(), nullable=True),
        sa.Column("storage_type", sa.Text(), server_default="local", nullable=False),
        sa.Column("duration_seconds", sa.Integer(), server_default="0", nullable=False),
        sa.Column("source_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_audio_overviews_notebook_id", "audio_overviews", ["notebook_id"])
    op.create_index("ix_audio_overviews_user_id", "audio_overviews", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_audio_overviews_user_id", table_name="audio_overviews")
    op.drop_index("ix_audio_overviews_notebook_id", table_name="audio_overviews")
    op.drop_table("audio_overviews")
