"""Add enterprise connector_configs table and governance/data lake columns.

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-15
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Workspace Governance Columns ─────────────────────────────────────────
    op.add_column(
        "workspaces",
        sa.Column("enable_pii_redaction", sa.Boolean(), server_default="true", nullable=False),
    )
    op.add_column(
        "workspaces",
        sa.Column("default_sensitivity", sa.Text(), server_default="internal", nullable=False),
    )

    # ── Source Governance & Storage Columns ───────────────────────────────────
    op.add_column(
        "sources",
        sa.Column("sensitivity_level", sa.Text(), server_default="internal", nullable=False),
    )
    op.add_column(
        "sources",
        sa.Column("pii_redacted", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "sources",
        sa.Column("pii_entities_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "sources",
        sa.Column("storage_type", sa.Text(), server_default="minio", nullable=False),
    )
    op.create_index("ix_sources_sensitivity_level", "sources", ["sensitivity_level"])

    # ── Enterprise Connectors Table ──────────────────────────────────────────
    op.create_table(
        "connector_configs",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("notebook_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("connector_type", sa.Text(), nullable=False),
        sa.Column("config_json", JSONB(), server_default="{}", nullable=False),
        sa.Column("schedule_cron", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="ACTIVE", nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["notebook_id"], ["notebooks.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_connector_configs_workspace_id", "connector_configs", ["workspace_id"])
    op.create_index("ix_connector_configs_notebook_id", "connector_configs", ["notebook_id"])
    op.execute(
        """
        CREATE TRIGGER update_connector_configs_updated_at
        BEFORE UPDATE ON connector_configs
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """
    )


def downgrade() -> None:
    op.drop_table("connector_configs")
    op.drop_index("ix_sources_sensitivity_level", table_name="sources")
    op.drop_column("sources", "storage_type")
    op.drop_column("sources", "pii_entities_count")
    op.drop_column("sources", "pii_redacted")
    op.drop_column("sources", "sensitivity_level")
    op.drop_column("workspaces", "default_sensitivity")
    op.drop_column("workspaces", "enable_pii_redaction")
