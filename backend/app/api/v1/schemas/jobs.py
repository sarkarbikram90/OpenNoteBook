"""OpenNotebook — Pydantic v2 schemas for Jobs / DLQ endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FailedJobResponse(BaseModel):
    """Response schema for a failed job (DLQ entry)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_id: uuid.UUID
    task_name: str
    error: str
    traceback: str | None = None
    retried: bool
    created_at: datetime


class FailedJobListResponse(BaseModel):
    """Response schema for listing failed jobs."""

    model_config = ConfigDict(strict=True)

    jobs: list[FailedJobResponse]
    total: int


class RetryResponse(BaseModel):
    """Response for a successful job retry."""

    model_config = ConfigDict(strict=True)

    job_id: uuid.UUID
    source_id: uuid.UUID
    message: str = "Job re-dispatched for processing"
