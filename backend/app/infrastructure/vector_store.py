"""Unified vector store dispatcher supporting PostgreSQL + pgvector and Qdrant.

Controlled by ``VECTOR_STORE_PROVIDER`` (``pgvector`` or ``qdrant``).
"""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.infrastructure.qdrant.schema import ChunkPayload


def _active_backend() -> str:
    """Return normalized vector store provider name (``pgvector`` or ``qdrant``)."""
    provider = getattr(get_settings(), "vector_store_provider", "qdrant")
    return str(provider or "qdrant").strip().lower()


def ensure_vector_store() -> None:
    """Ensure the configured vector store collection/table is initialized."""
    if _active_backend() == "pgvector":
        from app.infrastructure.pgvector.client import ensure_collection

        ensure_collection()
        return

    from app.infrastructure.qdrant.client import ensure_collection

    ensure_collection()


def upsert_chunks(chunks: list[ChunkPayload]) -> None:
    """Upsert chunk embeddings into the active vector store."""
    if _active_backend() == "pgvector":
        from app.infrastructure.pgvector.client import upsert_chunks as pg_upsert

        pg_upsert(chunks)
        return

    from app.infrastructure.qdrant.client import upsert_chunks as qdrant_upsert

    qdrant_upsert(chunks)


def delete_by_source(source_id: str) -> None:
    """Delete all vectors for ``source_id`` from the active vector store."""
    if _active_backend() == "pgvector":
        from app.infrastructure.pgvector.client import delete_by_source as pg_delete

        pg_delete(source_id)
        return

    from app.infrastructure.qdrant.client import delete_by_source as qdrant_delete

    qdrant_delete(source_id)


def delete_by_notebook(notebook_id: str) -> None:
    """Delete all vectors for ``notebook_id`` from the active vector store."""
    if _active_backend() == "pgvector":
        from app.infrastructure.pgvector.client import (
            delete_by_notebook as pg_delete_nb,
        )

        pg_delete_nb(notebook_id)
        return

    from app.infrastructure.qdrant.client import (
        delete_by_notebook as qdrant_delete_nb,
    )

    qdrant_delete_nb(notebook_id)


def get_all_chunks_for_notebook(notebook_id: str) -> list[dict[str, Any]]:
    """Return all chunk payloads for ``notebook_id`` from the active vector store."""
    if _active_backend() == "pgvector":
        from app.infrastructure.pgvector.client import (
            get_all_chunks_for_notebook as pg_get_all,
        )

        return pg_get_all(notebook_id)

    from app.infrastructure.qdrant.client import (
        get_all_chunks_for_notebook as qdrant_get_all,
    )

    return qdrant_get_all(notebook_id)


def get_chunks_by_ids(chunk_ids: list[str]) -> list[dict[str, Any]]:
    """Return chunk payloads by ``chunk_ids`` from the active vector store."""
    if _active_backend() == "pgvector":
        from app.infrastructure.pgvector.client import (
            get_chunks_by_ids as pg_get_by_ids,
        )

        return pg_get_by_ids(chunk_ids)

    from app.infrastructure.qdrant.client import (
        get_chunks_by_ids as qdrant_get_by_ids,
    )

    return qdrant_get_by_ids(chunk_ids)
