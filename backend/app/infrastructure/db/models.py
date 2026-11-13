"""OpenNotebook — SQLAlchemy 2 async models for all database tables.

Matches the schema from ``opennotebook-build-prompt.md`` exactly.
Tables: users, notebooks, sources, source_summaries, chat_sessions,
messages, settings, audit_log.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base


# ── Users ────────────────────────────────────────────────────────────────────


class User(Base):
    """Application user account."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)

    # Relationships
    notebooks: Mapped[list[Notebook]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    settings: Mapped[UserSettings | None] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    workspace_memberships: Mapped[list[WorkspaceMember]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"


# ── Multi-Tenancy & RBAC ───────────────────────────────────────────────────


class Organization(Base):
    """Enterprise tenant organization (e.g. Acme Corp)."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)

    # Relationships
    workspaces: Mapped[list[Workspace]] = relationship(
        back_populates="organization", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Organization id={self.id} name={self.name!r} slug={self.slug!r}>"


class Workspace(Base):
    """Department, team, or project boundary within an organization."""

    __tablename__ = "workspaces"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    enable_pii_redaction: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    default_sensitivity: Mapped[str] = mapped_column(Text, server_default="internal", nullable=False)

    # Relationships
    organization: Mapped[Organization] = relationship(back_populates="workspaces")
    members: Mapped[list[WorkspaceMember]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan", lazy="selectin"
    )
    notebooks: Mapped[list[Notebook]] = relationship(
        back_populates="workspace", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Workspace id={self.id} name={self.name!r}>"


class WorkspaceMember(Base):
    """Membership and Role-Based Access Control (RBAC) in a workspace."""

    __tablename__ = "workspace_members"
    __table_args__ = (
        CheckConstraint(
            "role IN ('owner', 'admin', 'member', 'viewer')",
            name="ck_workspace_members_role",
        ),
        Index("ix_workspace_members_workspace_user", "workspace_id", "user_id", unique=True),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(Text, server_default="member", nullable=False)

    # Relationships
    workspace: Mapped[Workspace] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="workspace_memberships")

    def __repr__(self) -> str:
        return f"<WorkspaceMember workspace_id={self.workspace_id} user_id={self.user_id} role={self.role}>"


# ── Notebooks ────────────────────────────────────────────────────────────────


class Notebook(Base):
    """A user's notebook — the primary unit of organisation."""

    __tablename__ = "notebooks"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    user: Mapped[User] = relationship(back_populates="notebooks")
    workspace: Mapped[Workspace | None] = relationship(back_populates="notebooks")
    sources: Mapped[list[Source]] = relationship(
        back_populates="notebook", cascade="all, delete-orphan", lazy="selectin"
    )
    chat_sessions: Mapped[list[ChatSession]] = relationship(
        back_populates="notebook", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Notebook id={self.id} name={self.name!r}>"


# ── Sources ──────────────────────────────────────────────────────────────────


class Source(Base):
    """An uploaded or ingested source document within a notebook."""

    __tablename__ = "sources"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('pdf', 'docx', 'txt', 'md', 'url', 'youtube', 'image')",
            name="ck_sources_source_type",
        ),
        Index("ix_sources_notebook_id", "notebook_id"),
        Index("ix_sources_checksum", "checksum"),
    )

    notebook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notebooks.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="PENDING")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    sensitivity_level: Mapped[str] = mapped_column(Text, server_default="internal", nullable=False)
    pii_redacted: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    pii_entities_count: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    storage_type: Mapped[str] = mapped_column(Text, server_default="minio", nullable=False)
    checksum: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    allowed_roles: Mapped[list[str]] = mapped_column(
        JSONB, server_default="[]", nullable=False
    )
    allowed_users: Mapped[list[str]] = mapped_column(
        JSONB, server_default="[]", nullable=False
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, server_default="{}", nullable=False
    )

    # Relationships
    notebook: Mapped[Notebook] = relationship(back_populates="sources")
    summaries: Mapped[list[SourceSummary]] = relationship(
        back_populates="source", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Source id={self.id} name={self.name!r} type={self.source_type}>"


# ── Source Summaries ─────────────────────────────────────────────────────────


class SourceSummary(Base):
    """AI-generated summary of a source document."""

    __tablename__ = "source_summaries"

    # Override: source_summaries only has created_at per spec (no updated_at in spec)
    # But Base provides both — we keep both for consistency.

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    executive_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_findings: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    entities: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    suggested_questions: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    source: Mapped[Source] = relationship(back_populates="summaries")

    def __repr__(self) -> str:
        return f"<SourceSummary id={self.id} source_id={self.source_id}>"


# ── Chat Sessions ────────────────────────────────────────────────────────────


class ChatSession(Base):
    """A chat conversation session within a notebook."""

    __tablename__ = "chat_sessions"

    notebook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notebooks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(Text, server_default="New chat", nullable=False)

    # Relationships
    notebook: Mapped[Notebook] = relationship(back_populates="chat_sessions")
    messages: Mapped[list[Message]] = relationship(
        back_populates="session", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<ChatSession id={self.id} title={self.title!r}>"


# ── Messages ─────────────────────────────────────────────────────────────────


class Message(Base):
    """A single message in a chat session (user or assistant)."""

    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant')",
            name="ck_messages_role",
        ),
        Index("ix_messages_session_id", "session_id"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list[Any]] = mapped_column(
        JSONB, server_default="[]", nullable=False
    )
    retrieval_meta: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default="{}", nullable=False
    )

    # Relationships
    session: Mapped[ChatSession] = relationship(back_populates="messages")

    def __repr__(self) -> str:
        return f"<Message id={self.id} role={self.role} session_id={self.session_id}>"


# ── Message Feedback ─────────────────────────────────────────────────────────


class MessageFeedback(Base):
    """User feedback (thumbs up/down) on an assistant message."""

    __tablename__ = "message_feedback"
    __table_args__ = (
        CheckConstraint(
            "rating IN ('up', 'down')",
            name="ck_message_feedback_rating",
        ),
        Index("ix_message_feedback_message_id", "message_id"),
    )

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    rating: Mapped[str] = mapped_column(Text, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<MessageFeedback message_id={self.message_id} rating={self.rating}>"


# ── Settings ─────────────────────────────────────────────────────────────────


class UserSettings(Base):
    """Per-user model registry and preference settings."""

    __tablename__ = "settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    llm_model: Mapped[str] = mapped_column(
        Text, server_default="llama3:8b-instruct", nullable=False
    )
    embedding_model: Mapped[str] = mapped_column(
        Text, server_default="BAAI/bge-small-en-v1.5", nullable=False
    )
    reranker_model: Mapped[str] = mapped_column(
        Text, server_default="BAAI/bge-reranker-base", nullable=False
    )
    llm_temperature: Mapped[Decimal] = mapped_column(
        Numeric, server_default="0.1", nullable=False
    )
    context_window: Mapped[int] = mapped_column(
        Integer, server_default="8192", nullable=False
    )
    max_chunks: Mapped[int] = mapped_column(
        Integer, server_default="10", nullable=False
    )

    # Relationships
    user: Mapped[User] = relationship(back_populates="settings")

    def __repr__(self) -> str:
        return f"<UserSettings id={self.id} user_id={self.user_id}>"


# ── Audit Log ────────────────────────────────────────────────────────────────


class AuditLog(Base):
    """Immutable audit trail for all mutations (Security requirement)."""

    __tablename__ = "audit_log"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[str] = mapped_column(Text, nullable=False)
    resource_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    user: Mapped[User | None] = relationship(back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} action={self.action} resource={self.resource_type}>"


# ── Failed Jobs (DLQ) ───────────────────────────────────────────────────────


class FailedJob(Base):
    """Dead letter queue entry for permanently failed background tasks."""

    __tablename__ = "failed_jobs"

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_name: Mapped[str] = mapped_column(Text, nullable=False)
    error: Mapped[str] = mapped_column(Text, nullable=False)
    traceback: Mapped[str | None] = mapped_column(Text, nullable=True)
    retried: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)

    # Relationships
    source: Mapped[Source] = relationship()

    def __repr__(self) -> str:
        return f"<FailedJob id={self.id} source_id={self.source_id} task={self.task_name}>"


# ── Enterprise Connectors ───────────────────────────────────────────────────


class ConnectorConfig(Base):
    """Enterprise external data connector configuration."""

    __tablename__ = "connector_configs"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    notebook_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notebooks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    connector_type: Mapped[str] = mapped_column(Text, nullable=False)  # "web", "s3", "gdrive", "sharepoint"
    config_json: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}", nullable=False)
    schedule_cron: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, server_default="ACTIVE", nullable=False)  # "ACTIVE", "PAUSED", "ERROR"
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    workspace: Mapped[Workspace] = relationship(lazy="selectin")
    notebook: Mapped[Notebook | None] = relationship(lazy="selectin")

    def __repr__(self) -> str:
        return f"<ConnectorConfig id={self.id} type={self.connector_type} name={self.name!r}>"


