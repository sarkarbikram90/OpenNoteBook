"""Allow raster image sources for OCR ingestion.

Revision ID: 0008
Revises: 0007
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_sources_source_type", "sources", type_="check")
    op.create_check_constraint(
        "ck_sources_source_type",
        "sources",
        "source_type IN ('pdf', 'docx', 'txt', 'md', 'url', 'youtube', 'image')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_sources_source_type", "sources", type_="check")
    op.create_check_constraint(
        "ck_sources_source_type",
        "sources",
        "source_type IN ('pdf', 'docx', 'txt', 'md', 'url', 'youtube')",
    )
