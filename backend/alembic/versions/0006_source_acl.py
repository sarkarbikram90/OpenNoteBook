"""Add document-level ACL columns (allowed_roles, allowed_users) to sources.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-24
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sources",
        sa.Column("allowed_roles", JSONB(), server_default="[]", nullable=False),
    )
    op.add_column(
        "sources",
        sa.Column("allowed_users", JSONB(), server_default="[]", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("sources", "allowed_users")
    op.drop_column("sources", "allowed_roles")
