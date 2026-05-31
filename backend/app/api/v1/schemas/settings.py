"""OpenNotebook — Settings request/response schemas (Pydantic v2 strict mode)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SettingsResponse(BaseModel):
    """Full settings representation returned to the client."""

    model_config = ConfigDict(strict=True, from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    llm_model: str
    embedding_model: str
    reranker_model: str
    llm_temperature: Decimal
    context_window: int
    max_chunks: int
    updated_at: datetime


class SettingsUpdateRequest(BaseModel):
    """Partial update of user settings — all fields optional."""

    model_config = ConfigDict(strict=True)

    llm_model: str | None = Field(None, max_length=255)
    embedding_model: str | None = Field(None, max_length=255)
    reranker_model: str | None = Field(None, max_length=255)
    llm_temperature: Decimal | None = Field(None, ge=0, le=2)
    context_window: int | None = Field(None, ge=512, le=131072)
    max_chunks: int | None = Field(None, ge=1, le=100)
