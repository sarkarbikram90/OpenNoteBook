"""OpenNotebook — Pydantic v2 schemas for Chat endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ── Request Schemas ─────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    """Request body for the streaming chat endpoint."""

    model_config = ConfigDict(strict=True)

    question: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="The user's question to ask against notebook sources",
    )
    session_id: uuid.UUID | None = Field(
        None,
        description="Existing chat session ID to continue.  Omit to start a new session.",
    )
    source_filter: list[uuid.UUID] | None = Field(
        None,
        description="Optional list of source UUIDs to restrict retrieval to",
    )


class ExportRequest(BaseModel):
    """Request body for session export."""

    model_config = ConfigDict(strict=True)

    format: Literal["markdown", "pdf"] = Field(
        "markdown",
        description="Export format: markdown or pdf",
    )


# ── Response Schemas ────────────────────────────────────────────────────────


class CitationDetail(BaseModel):
    """A single citation reference in an assistant message."""

    model_config = ConfigDict(strict=True)

    chunk_id: str
    source_name: str
    source_id: str
    page: int | None = None
    section: str | None = None
    relevance_score: float = 0.0


class MessageResponse(BaseModel):
    """A single chat message (user or assistant)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_meta: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class MessageListResponse(BaseModel):
    """Response for listing messages in a session."""

    model_config = ConfigDict(strict=True)

    messages: list[MessageResponse]
    total: int


class ChatSessionResponse(BaseModel):
    """A chat session with message count."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    notebook_id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class ChatSessionListResponse(BaseModel):
    """Response for listing chat sessions."""

    model_config = ConfigDict(strict=True)

    sessions: list[ChatSessionResponse]
    total: int


# ── Search Schemas ──────────────────────────────────────────────────────────


class SearchRequest(BaseModel):
    """Request body for the notebook search endpoint."""

    model_config = ConfigDict(strict=True)

    query: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="Search query",
    )
    top_k: int = Field(10, ge=1, le=50, description="Number of results to return")
    source_filter: list[uuid.UUID] | None = Field(
        None,
        description="Optional list of source UUIDs to restrict search to",
    )


class SearchChunkResult(BaseModel):
    """A single search result chunk."""

    model_config = ConfigDict(strict=True)

    chunk_id: str
    source_id: str
    source_name: str
    text: str
    page: int | None = None
    section: str | None = None
    relevance_score: float = 0.0
    token_count: int = 0


class SearchResponse(BaseModel):
    """Response for the search endpoint."""

    model_config = ConfigDict(strict=True)

    results: list[SearchChunkResult]
    total: int
    latency_ms: float
