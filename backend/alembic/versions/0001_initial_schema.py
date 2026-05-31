"""Initial schema — all 8 tables.

Revision ID: 0001
Revises:
Create Date: 2026-05-31
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Updated_at trigger function ──────────────────────────────────────
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    # ── Users ────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.execute(
        """
        CREATE TRIGGER update_users_updated_at
        BEFORE UPDATE ON users
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """
    )

    # ── Notebooks ────────────────────────────────────────────────────────
    op.create_table(
        "notebooks",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_notebooks_user_id", "notebooks", ["user_id"])
    op.execute(
        """
        CREATE TRIGGER update_notebooks_updated_at
        BEFORE UPDATE ON notebooks
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """
    )

    # ── Sources ──────────────────────────────────────────────────────────
    op.create_table(
        "sources",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("notebook_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'PENDING'"), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=True),
        sa.Column("embedding_model", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["notebook_id"], ["notebooks.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "source_type IN ('pdf', 'docx', 'txt', 'md', 'url', 'youtube')",
            name="ck_sources_source_type",
        ),
    )
    op.create_index("ix_sources_notebook_id", "sources", ["notebook_id"])
    op.execute(
        """
        CREATE TRIGGER update_sources_updated_at
        BEFORE UPDATE ON sources
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """
    )

    # ── Source Summaries ─────────────────────────────────────────────────
    op.create_table(
        "source_summaries",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("executive_summary", sa.Text(), nullable=True),
        sa.Column("key_findings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("entities", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("suggested_questions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_source_summaries_source_id", "source_summaries", ["source_id"])
    op.execute(
        """
        CREATE TRIGGER update_source_summaries_updated_at
        BEFORE UPDATE ON source_summaries
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """
    )

    # ── Chat Sessions ────────────────────────────────────────────────────
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("notebook_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), server_default=sa.text("'New chat'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["notebook_id"], ["notebooks.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_chat_sessions_notebook_id", "chat_sessions", ["notebook_id"])
    op.execute(
        """
        CREATE TRIGGER update_chat_sessions_updated_at
        BEFORE UPDATE ON chat_sessions
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """
    )

    # ── Messages ─────────────────────────────────────────────────────────
    op.create_table(
        "messages",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("retrieval_meta", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_messages_role"),
    )
    op.create_index("ix_messages_session_id", "messages", ["session_id"])
    op.execute(
        """
        CREATE TRIGGER update_messages_updated_at
        BEFORE UPDATE ON messages
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """
    )

    # ── Settings ─────────────────────────────────────────────────────────
    op.create_table(
        "settings",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("llm_model", sa.Text(), server_default=sa.text("'llama3:8b-instruct'"), nullable=False),
        sa.Column("embedding_model", sa.Text(), server_default=sa.text("'BAAI/bge-small-en-v1.5'"), nullable=False),
        sa.Column("reranker_model", sa.Text(), server_default=sa.text("'BAAI/bge-reranker-base'"), nullable=False),
        sa.Column("llm_temperature", sa.Numeric(), server_default=sa.text("0.1"), nullable=False),
        sa.Column("context_window", sa.Integer(), server_default=sa.text("8192"), nullable=False),
        sa.Column("max_chunks", sa.Integer(), server_default=sa.text("10"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id"),
    )
    op.execute(
        """
        CREATE TRIGGER update_settings_updated_at
        BEFORE UPDATE ON settings
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """
    )

    # ── Audit Log ────────────────────────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=False),
        sa.Column("resource_id", sa.Text(), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("settings")
    op.drop_table("messages")
    op.drop_table("chat_sessions")
    op.drop_table("source_summaries")
    op.drop_table("sources")
    op.drop_table("notebooks")
    op.drop_table("users")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")
