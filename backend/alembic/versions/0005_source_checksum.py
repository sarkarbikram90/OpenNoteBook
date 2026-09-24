"""Add checksum and content_type columns to sources (Stage 2: dedup).

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-24
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("checksum", sa.Text(), nullable=True))
    op.add_column("sources", sa.Column("content_type", sa.Text(), nullable=True))
    op.create_index("ix_sources_checksum", "sources", ["checksum"])

    # Backfill from the provenance hash already stored in the metadata JSONB.
    op.execute(
        """
        UPDATE sources
        SET checksum = metadata->>'sha256'
        WHERE checksum IS NULL AND metadata ? 'sha256';
        """
    )


def downgrade() -> None:
    op.drop_index("ix_sources_checksum", table_name="sources")
    op.drop_column("sources", "content_type")
    op.drop_column("sources", "checksum")
