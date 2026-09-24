"""OpenNotebook — Qdrant payload schema definition.

Kept free of any ``qdrant_client`` import so the index field list can be unit
tested and referenced without a Qdrant server or the client library.
"""

from __future__ import annotations

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
