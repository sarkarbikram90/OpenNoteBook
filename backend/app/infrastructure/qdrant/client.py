"""OpenNotebook — Qdrant vector store client.

Provides collection management, batch upsert of chunk embeddings with full
payload metadata, and deletion by source or notebook.  The client is a
module-level singleton.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from app.core.config import get_settings
from app.infrastructure.qdrant.schema import PAYLOAD_INDEX_FIELDS, dimension_matches

logger = logging.getLogger(__name__)


@dataclass
class ChunkPayload:
    """Data transfer object for a chunk to be upserted into Qdrant."""

    chunk_id: str
    source_id: str
    notebook_id: str
    text: str
    token_count: int
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


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    """Return a cached singleton Qdrant client (supports Qdrant Cloud API keys)."""
    settings = get_settings()
    return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)


def ensure_collection() -> None:
    """Create the vector collection if it does not exist.

    Uses cosine distance with the configured embedding dimension (384 for
    BGE-small-en-v1.5).
    """
    settings = get_settings()
    client = get_qdrant_client()
    collections = [c.name for c in client.get_collections().collections]

    if settings.qdrant_collection not in collections:
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(
                size=settings.embedding_dimension,
                distance=Distance.COSINE,
            ),
        )
        logger.info(
            "Created Qdrant collection: %s (dim=%d, cosine)",
            settings.qdrant_collection,
            settings.embedding_dimension,
        )
    else:
        info = client.get_collection(settings.qdrant_collection)
        existing_dim = _collection_dimension(info)
        if not dimension_matches(settings.embedding_dimension, existing_dim):
            raise RuntimeError(
                f"Qdrant collection {settings.qdrant_collection!r} has vector size "
                f"{existing_dim}, but the configured embedding dimension is "
                f"{settings.embedding_dimension}. Use a different collection name "
                f"(QDRANT_COLLECTION) to re-index with a new embedding model."
            )
        logger.debug(
            "Qdrant collection already exists: %s (dim=%s)",
            settings.qdrant_collection,
            existing_dim,
        )

    ensure_payload_indexes()


def _collection_dimension(collection_info: Any) -> int | None:
    """Extract the vector size from a Qdrant collection info object."""
    try:
        vectors = collection_info.config.params.vectors
        size = getattr(vectors, "size", None)
        return int(size) if size is not None else None
    except Exception:
        return None


def ensure_payload_indexes() -> None:
    """Create payload indexes for filtered fields.

    Without these, Qdrant performs a full scan for every metadata-filtered
    query (notebook/source/sensitivity/ACL filters). Creation is idempotent and
    best-effort: an index that already exists is left as-is.
    """
    settings = get_settings()
    client = get_qdrant_client()

    for field_name in PAYLOAD_INDEX_FIELDS:
        try:
            client.create_payload_index(
                collection_name=settings.qdrant_collection,
                field_name=field_name,
                field_schema=PayloadSchemaType.KEYWORD,
            )
        except Exception as exc:  # already exists, or transient
            logger.debug("Payload index for %s not created: %s", field_name, exc)

    logger.info("Ensured payload indexes for %d fields", len(PAYLOAD_INDEX_FIELDS))


def upsert_chunks(chunks: list[ChunkPayload]) -> None:
    """Batch upsert chunk vectors with full metadata payload.

    Each point stores the complete chunk metadata in its payload so that
    retrieval can return everything without a database join.

    Args:
        chunks: List of chunk payloads with pre-computed embedding vectors.
    """
    if not chunks:
        return

    settings = get_settings()
    client = get_qdrant_client()

    points = [
        PointStruct(
            id=chunk.chunk_id,
            vector=chunk.vector,
            payload={
                "chunk_id": chunk.chunk_id,
                "source_id": chunk.source_id,
                "notebook_id": chunk.notebook_id,
                "workspace_id": chunk.workspace_id,
                "sensitivity_level": chunk.sensitivity_level,
                "allowed_roles": chunk.allowed_roles,
                "allowed_users": chunk.allowed_users,
                "text": chunk.text,
                "token_count": chunk.token_count,
                "page": chunk.page,
                "section": chunk.section,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
                "embedding_model": chunk.embedding_model,
            },
        )
        for chunk in chunks
    ]

    # Qdrant supports batch upsert up to ~1000 points at a time
    batch_size = 256
    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        client.upsert(
            collection_name=settings.qdrant_collection,
            points=batch,
        )

    logger.info("Upserted %d chunks into Qdrant", len(chunks))


def delete_by_source(source_id: str) -> None:
    """Delete all vectors belonging to a specific source.

    Args:
        source_id: The UUID of the source whose chunks should be removed.
    """
    settings = get_settings()
    client = get_qdrant_client()
    client.delete(
        collection_name=settings.qdrant_collection,
        points_selector=Filter(
            must=[FieldCondition(key="source_id", match=MatchValue(value=source_id))]
        ),
    )
    logger.info("Deleted Qdrant vectors for source: %s", source_id)


def delete_by_notebook(notebook_id: str) -> None:
    """Delete all vectors belonging to a specific notebook.

    Args:
        notebook_id: The UUID of the notebook whose chunks should be removed.
    """
    settings = get_settings()
    client = get_qdrant_client()
    client.delete(
        collection_name=settings.qdrant_collection,
        points_selector=Filter(
            must=[FieldCondition(key="notebook_id", match=MatchValue(value=notebook_id))]
        ),
    )
    logger.info("Deleted Qdrant vectors for notebook: %s", notebook_id)


def get_all_chunks_for_notebook(notebook_id: str) -> list[dict[str, Any]]:
    """Retrieve all chunk payloads for a notebook (used for BM25 index building).

    Args:
        notebook_id: The UUID of the notebook.

    Returns:
        List of payload dicts from Qdrant.
    """
    settings = get_settings()
    client = get_qdrant_client()

    all_payloads: list[dict[str, Any]] = []
    offset = None

    while True:
        results, next_offset = client.scroll(
            collection_name=settings.qdrant_collection,
            scroll_filter=Filter(
                must=[FieldCondition(key="notebook_id", match=MatchValue(value=notebook_id))]
            ),
            limit=500,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        for point in results:
            if point.payload:
                all_payloads.append(point.payload)

        if next_offset is None:
            break
        offset = next_offset

    return all_payloads


def get_chunks_by_ids(chunk_ids: list[str]) -> list[dict[str, Any]]:
    """Retrieve specific chunk payloads from Qdrant by their point IDs.

    Args:
        chunk_ids: List of chunk ID strings (UUIDs).

    Returns:
        List of payload dicts for the matching chunks.
    """
    if not chunk_ids:
        return []

    settings = get_settings()
    client = get_qdrant_client()

    try:
        points = client.retrieve(
            collection_name=settings.qdrant_collection,
            ids=chunk_ids,
            with_payload=True,
            with_vectors=False,
        )
        return [p.payload for p in points if p.payload]
    except Exception as exc:
        logger.warning("Failed to retrieve chunks by IDs from Qdrant: %s", exc)
        return []
