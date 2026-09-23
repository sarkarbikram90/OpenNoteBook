"""Add multi-tenancy organizations, workspaces, and workspace_members tables.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-01
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Organizations ────────────────────────────────────────────────────────
    op.create_table(
        "organizations",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"])
    op.execute(
        """
        CREATE TRIGGER update_organizations_updated_at
        BEFORE UPDATE ON organizations
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """
    )

    # ── Workspaces ───────────────────────────────────────────────────────────
    op.create_table(
        "workspaces",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_workspaces_organization_id", "workspaces", ["organization_id"])
    op.execute(
        """
        CREATE TRIGGER update_workspaces_updated_at
        BEFORE UPDATE ON workspaces
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """
    )

    # ── Workspace Members (RBAC) ─────────────────────────────────────────────
    op.create_table(
        "workspace_members",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.Text(), server_default=sa.text("'member'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "role IN ('owner', 'admin', 'member', 'viewer')",
            name="ck_workspace_members_role",
        ),
    )
    op.create_index("ix_workspace_members_workspace_user", "workspace_members", ["workspace_id", "user_id"], unique=True)
    op.create_index("ix_workspace_members_user_id", "workspace_members", ["user_id"])
    op.execute(
        """
        CREATE TRIGGER update_workspace_members_updated_at
        BEFORE UPDATE ON workspace_members
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """
    )

    # ── Add workspace_id to Notebooks ────────────────────────────────────────
    op.add_column("notebooks", sa.Column("workspace_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_notebooks_workspace_id",
        "notebooks",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_notebooks_workspace_id", "notebooks", ["workspace_id"])


def downgrade() -> None:
    op.drop_constraint("fk_notebooks_workspace_id", "notebooks", type_="foreignkey")
    op.drop_index("ix_notebooks_workspace_id", table_name="notebooks")
    op.drop_column("notebooks", "workspace_id")

    op.execute("DROP TRIGGER IF EXISTS update_workspace_members_updated_at ON workspace_members;")
    op.drop_index("ix_workspace_members_user_id", table_name="workspace_members")
    op.drop_index("ix_workspace_members_workspace_user", table_name="workspace_members")
    op.drop_table("workspace_members")

    op.execute("DROP TRIGGER IF EXISTS update_workspaces_updated_at ON workspaces;")
    op.drop_index("ix_workspaces_organization_id", table_name="workspaces")
    op.drop_table("workspaces")

    op.execute("DROP TRIGGER IF EXISTS update_organizations_updated_at ON organizations;")
    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_table("organizations")
