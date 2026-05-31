"""OpenNotebook — Pydantic v2 schemas for Source endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ── Request Schemas ─────────────────────────────────────────────────────────


class SourceUploadURL(BaseModel):
    """Request body for uploading a URL or YouTube source."""

    model_config = ConfigDict(strict=True)

    url: str = Field(..., min_length=1, max_length=2048, description="URL or YouTube URL to ingest")
    source_type: str = Field(..., pattern="^(url|youtube)$", description="Source type: url or youtube")
    name: str | None = Field(None, max_length=255, description="Optional display name")


# ── Response Schemas ────────────────────────────────────────────────────────


class SourceResponse(BaseModel):
    """Response schema for a source document."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    notebook_id: uuid.UUID
    name: str
    source_type: str
    status: str
    error_message: str | None = None
    page_count: int | None = None
    chunk_count: int | None = None
    embedding_model: str | None = None
    storage_path: str | None = None
    source_url: str | None = None
    metadata_: dict[str, Any] = Field(default_factory=dict, alias="metadata_")
    created_at: datetime
    updated_at: datetime


class SourceListResponse(BaseModel):
    """Response schema for listing sources."""

    model_config = ConfigDict(strict=True)

    sources: list[SourceResponse]
    total: int


class SourceUploadResponse(BaseModel):
    """Response for a successful source upload (202 Accepted)."""

    model_config = ConfigDict(strict=True)

    source_id: uuid.UUID
    status: str = "PENDING"
    message: str = "Source uploaded and queued for processing"


# ── SSE Event Schemas ───────────────────────────────────────────────────────


class SourceStatusEvent(BaseModel):
    """Schema for SSE status events."""

    source_id: str
    status: str
    chunk_count: int | None = None
    error_message: str | None = None
