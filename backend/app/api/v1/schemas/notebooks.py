"""OpenNotebook — Pydantic v2 schemas for Notebook endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ── Request Schemas ─────────────────────────────────────────────────────────


class NotebookCreate(BaseModel):
    """Request body for creating a new notebook."""

    model_config = ConfigDict(strict=True)

    name: str = Field(..., min_length=1, max_length=255, description="Notebook name")
    description: str | None = Field(None, max_length=2000, description="Optional description")


class NotebookUpdate(BaseModel):
    """Request body for updating a notebook (partial update)."""

    model_config = ConfigDict(strict=True)

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)


# ── Response Schemas ────────────────────────────────────────────────────────


class NotebookResponse(BaseModel):
    """Response schema for a notebook."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    source_count: int = 0
    created_at: datetime
    updated_at: datetime


class NotebookListResponse(BaseModel):
    """Response schema for listing notebooks."""

    model_config = ConfigDict(strict=True)

    notebooks: list[NotebookResponse]
    total: int
