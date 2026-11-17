"""OpenNotebook — Qdrant payload schema definition.

Kept free of any ``qdrant_client`` import so the index field list can be unit
tested and referenced without a Qdrant server or the client library.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChunkPayload:
    """Data transfer object for a chunk to be upserted into pgvector or Qdrant."""

    chunk_id: str
    source_id: str
    notebook_id: str
    text: str
    token_count: int
    source_name: str = ""
    page: int | None = None
    section: str | None = None
    start_char: int = 0
    end_char: int = 0
    embedding_model: str = ""
    workspace_id: str = ""
    sensitivity_level: str = "internal"
    allowed_roles: list[str] = field(default_factory=list)
    allowed_users: list[str] = field(default_factory=list)
    vector: list[float] = field(default_factory=list)

# Fields that retrieval filters on and therefore must be payload-indexed.
# Without these indexes Qdrant performs a full scan for every filtered query.
PAYLOAD_INDEX_FIELDS: list[str] = [
    "notebook_id",
    "source_id",
    "workspace_id",
    "sensitivity_level",
    "allowed_roles",
    "allowed_users",
    "embedding_model",
]

# All indexed fields are keyword (string / array-of-string) fields.
PAYLOAD_INDEX_FIELD_TYPE = "keyword"


def dimension_matches(configured: int, existing: int | None) -> bool:
    """Return True if an existing collection's vector size is compatible.

    A mismatch means the embedding model changed (e.g. 384-dim BGE to a 1536-dim
    model). Re-indexing into the same collection would corrupt it, so a new
    collection must be used for a side-by-side re-index.
    """
    return existing is None or existing == configured
