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


class SignedUploadRequest(BaseModel):
    """Request body to generate a V4 signed upload URL for direct client uploads."""

    model_config = ConfigDict(strict=True)

    filename: str = Field(..., min_length=1, max_length=255, description="Original filename")
    content_type: str = Field(
        default="application/octet-stream",
        min_length=1,
        max_length=128,
        description="MIME content type for the upload",
    )
    size_bytes: int | None = Field(
        default=None,
        ge=1,
        description="Optional file size in bytes for pre-flight validation",
    )
    sha256: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        description="Optional SHA-256 hex digest for deduplication",
    )


class SignedUploadResponse(BaseModel):
    """Response containing a pre-registered source ID and signed PUT URL."""

    model_config = ConfigDict(strict=True)

    source_id: uuid.UUID
    object_name: str
    upload_url: str
    method: str = "PUT"
    content_type: str
    expires_in_seconds: int
    status: str = "UPLOADED"
    duplicate: bool = False


class SignedDownloadResponse(BaseModel):
    """Response containing a signed GET URL for downloading a source document."""

    model_config = ConfigDict(strict=True)

    source_id: uuid.UUID
    object_name: str
    download_url: str
    expires_in_seconds: int


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
    checksum: str | None = None
    content_type: str | None = None
    allowed_roles: list[str] = Field(default_factory=list)
    allowed_users: list[str] = Field(default_factory=list)
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
    duplicate: bool = False


# ── SSE Event Schemas ───────────────────────────────────────────────────────


class SourceStatusEvent(BaseModel):
    """Schema for SSE status events."""

    source_id: str
    status: str
    chunk_count: int | None = None
    error_message: str | None = None
