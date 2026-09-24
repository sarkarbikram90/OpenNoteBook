"""OpenNotebook — evaluation dataset schema and loader."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class EvalCase(BaseModel):
    """A single gold Q&A evaluation case."""

    model_config = ConfigDict(extra="ignore")

    id: str
    question: str
    notebook_id: str | None = None
    # Ground-truth targets (chunk IDs preferred; source IDs as a fallback).
    expected_chunk_ids: list[str] = Field(default_factory=list)
    expected_source_ids: list[str] = Field(default_factory=list)
    # Answer checks.
    answer_must_contain: list[str] = Field(default_factory=list)
    answer_must_not_contain: list[str] = Field(default_factory=list)
    should_say_dont_know: bool = False

    @property
    def relevant_ids(self) -> list[str]:
        """Relevant IDs to score retrieval against (chunks preferred)."""
        return self.expected_chunk_ids or self.expected_source_ids


class EvalDataset(BaseModel):
    """A named collection of evaluation cases."""

    model_config = ConfigDict(extra="ignore")

    name: str = "default"
    cases: list[EvalCase] = Field(default_factory=list)


def load_dataset(path: str | Path) -> EvalDataset:
    """Load an evaluation dataset from a JSON file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return EvalDataset.model_validate(data)
