"""OpenNotebook — PostgreSQL + pgvector vector store client.

Provides:
1. ``ensure_collection`` — enables ``CREATE EXTENSION IF NOT EXISTS vector`` on
   PostgreSQL and ensures the ``document_chunks`` table exists.
2. ``upsert_chunks`` — batch upsert of chunk payloads and embeddings into
   ``document_chunks`` (writing both JSONB ``embedding`` and native pgvector
   ``embedding_vec`` when the PostgreSQL ``vector`` extension is active).
3. ``search_chunks`` — cosine similarity search using pgvector ``<=>`` operator
   with automatic fallback to exact cosine similarity over ``embedding`` JSONB.
4. ``delete_by_source``, ``delete_by_notebook``, ``get_all_chunks_for_notebook``,
   and ``get_chunks_by_ids``.
"""

from __future__ import annotations

import logging
import math
import uuid
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.core.metrics import vector_store_operations_total
from app.infrastructure.db.models import DocumentChunk
from app.infrastructure.qdrant.schema import ChunkPayload

logger = logging.getLogger(__name__)


def _get_session() -> Session:
    """Return a synchronous SQLAlchemy session for vector store operations."""
    from app.worker.tasks.process_source import _get_sync_session

    return _get_sync_session()


def _format_vector_literal(vector: list[float]) -> str:
    """Format a float list as a pgvector literal ``[0.1,0.2,...]``."""
    return "[" + ",".join(f"{float(v):.8f}" for v in vector) + "]"


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two equal-length float vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _row_to_payload(row: DocumentChunk, score: float | None = None) -> dict[str, Any]:
    """Convert a ``DocumentChunk`` ORM instance into a retrieval payload dict."""
    payload: dict[str, Any] = {
        "chunk_id": row.chunk_id,
        "source_id": str(row.source_id),
        "source_name": row.source_name or "Unknown",
        "notebook_id": str(row.notebook_id),
        "workspace_id": row.workspace_id or "",
        "sensitivity_level": row.sensitivity_level or "internal",
        "allowed_roles": list(row.allowed_roles or []),
        "allowed_users": list(row.allowed_users or []),
        "text": row.text,
        "token_count": row.token_count,
        "page": row.page,
        "section": row.section,
        "start_char": row.start_char,
        "end_char": row.end_char,
        "embedding_model": row.embedding_model or "",
    }
    if score is not None:
        payload["_dense_score"] = float(score)
    return payload


def ensure_collection() -> None:
    """Ensure the ``document_chunks`` table and optional ``pgvector`` extension exist."""
    session = _get_session()
    try:
        bind = session.get_bind()
        DocumentChunk.__table__.create(bind=bind, checkfirst=True)
        if bind.dialect.name == "postgresql":
            try:
                session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                session.execute(
                    text(
                        "ALTER TABLE document_chunks "
                        "ADD COLUMN IF NOT EXISTS embedding_vec vector"
                    )
                )
                session.commit()
            except Exception as pg_exc:
                session.rollback()
                logger.info(
                    "PostgreSQL vector extension not active (%s); using JSONB cosine fallback",
                    pg_exc,
                )
        vector_store_operations_total.labels(
            backend="pgvector", operation="ensure_collection", status="success"
        ).inc()
    except Exception:
        vector_store_operations_total.labels(
            backend="pgvector", operation="ensure_collection", status="error"
        ).inc()
        raise
    finally:
        session.close()


def upsert_chunks(chunks: list[ChunkPayload]) -> None:
    """Batch upsert ``ChunkPayload`` entries into ``document_chunks``."""
    if not chunks:
        return

    session = _get_session()
    try:
        bind = session.get_bind()
        DocumentChunk.__table__.create(bind=bind, checkfirst=True)

        chunk_ids = [c.chunk_id for c in chunks]
        session.execute(
            delete(DocumentChunk).where(DocumentChunk.chunk_id.in_(chunk_ids))
        )

        for chunk in chunks:
            row = DocumentChunk(
                id=uuid.uuid4(),
                chunk_id=chunk.chunk_id,
                source_id=uuid.UUID(str(chunk.source_id)),
                notebook_id=uuid.UUID(str(chunk.notebook_id)),
                workspace_id=chunk.workspace_id,
                source_name=chunk.source_name,
                text=chunk.text,
                token_count=chunk.token_count,
                page=chunk.page,
                section=chunk.section,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
                embedding_model=chunk.embedding_model,
                sensitivity_level=chunk.sensitivity_level,
                allowed_roles=list(chunk.allowed_roles or []),
                allowed_users=list(chunk.allowed_users or []),
                embedding=[float(v) for v in chunk.vector],
            )
            session.add(row)

        session.commit()

        # Populate native pgvector column when running on PostgreSQL with pgvector
        if bind.dialect.name == "postgresql":
            try:
                for chunk in chunks:
                    if chunk.vector:
                        vec_literal = _format_vector_literal(chunk.vector)
                        session.execute(
                            text(
                                "UPDATE document_chunks "
                                "SET embedding_vec = CAST(:vec AS vector) "
                                "WHERE chunk_id = :cid"
                            ),
                            {"vec": vec_literal, "cid": chunk.chunk_id},
                        )
                session.commit()
            except Exception:
                session.rollback()

        vector_store_operations_total.labels(
            backend="pgvector", operation="upsert", status="success"
        ).inc()
        logger.info("Upserted %d chunks into PostgreSQL document_chunks", len(chunks))
    except Exception:
        session.rollback()
        vector_store_operations_total.labels(
            backend="pgvector", operation="upsert", status="error"
        ).inc()
        raise
    finally:
        session.close()


def search_chunks(
    query_vector: list[float],
    notebook_id: str,
    limit: int = 20,
    source_filter: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Perform cosine similarity search over ``document_chunks`` for a notebook."""
    if not query_vector:
        return []

    session = _get_session()
    try:
        nb_uuid = uuid.UUID(str(notebook_id))
        bind = session.get_bind()

        # 1. Try native pgvector cosine distance `<=>` operator on PostgreSQL
        if bind.dialect.name == "postgresql":
            try:
                vec_literal = _format_vector_literal(query_vector)
                sql = (
                    "SELECT chunk_id, 1 - (embedding_vec <=> CAST(:qvec AS vector)) AS score "
                    "FROM document_chunks "
                    "WHERE notebook_id = :nb_id AND embedding_vec IS NOT NULL "
                    "ORDER BY embedding_vec <=> CAST(:qvec AS vector) "
                    "LIMIT :lim"
                )
                scored_rows = session.execute(
                    text(sql),
                    {"qvec": vec_literal, "nb_id": str(nb_uuid), "lim": int(limit * 2)},
                ).fetchall()
                if scored_rows:
                    score_by_cid = {str(r[0]): float(r[1]) for r in scored_rows}
                    stmt = select(DocumentChunk).where(
                        DocumentChunk.chunk_id.in_(list(score_by_cid.keys()))
                    )
                    if source_filter:
                        filter_uuids = [uuid.UUID(s) for s in source_filter]
                        stmt = stmt.where(DocumentChunk.source_id.in_(filter_uuids))
                    orm_rows = list(session.execute(stmt).scalars().all())
                    orm_rows.sort(
                        key=lambda r: score_by_cid.get(r.chunk_id, 0.0),
                        reverse=True,
                    )
                    vector_store_operations_total.labels(
                        backend="pgvector", operation="search", status="success"
                    ).inc()
                    return [
                        _row_to_payload(r, score=score_by_cid.get(r.chunk_id, 0.0))
                        for r in orm_rows[:limit]
                    ]
            except Exception:
                session.rollback()

        # 2. Fallback: cosine similarity over JSONB `embedding` column
        stmt = select(DocumentChunk).where(DocumentChunk.notebook_id == nb_uuid)
        if source_filter:
            filter_uuids = [uuid.UUID(s) for s in source_filter]
            stmt = stmt.where(DocumentChunk.source_id.in_(filter_uuids))

        rows = list(session.execute(stmt).scalars().all())
        scored: list[tuple[float, DocumentChunk]] = []
        for row in rows:
            emb = [float(x) for x in (row.embedding or [])]
            sim = _cosine_similarity(query_vector, emb)
            scored.append((sim, row))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        vector_store_operations_total.labels(
            backend="pgvector", operation="search", status="success"
        ).inc()
        return [_row_to_payload(row, score=sim) for sim, row in scored[:limit]]
    except Exception:
        vector_store_operations_total.labels(
            backend="pgvector", operation="search", status="error"
        ).inc()
        raise
    finally:
        session.close()


def delete_by_source(source_id: str) -> None:
    """Delete all chunks belonging to a source."""
    session = _get_session()
    try:
        src_uuid = uuid.UUID(str(source_id))
        session.execute(
            delete(DocumentChunk).where(DocumentChunk.source_id == src_uuid)
        )
        session.commit()
        vector_store_operations_total.labels(
            backend="pgvector", operation="delete_by_source", status="success"
        ).inc()
    except Exception:
        session.rollback()
        vector_store_operations_total.labels(
            backend="pgvector", operation="delete_by_source", status="error"
        ).inc()
        raise
    finally:
        session.close()


def delete_by_notebook(notebook_id: str) -> None:
    """Delete all chunks belonging to a notebook."""
    session = _get_session()
    try:
        nb_uuid = uuid.UUID(str(notebook_id))
        session.execute(
            delete(DocumentChunk).where(DocumentChunk.notebook_id == nb_uuid)
        )
        session.commit()
        vector_store_operations_total.labels(
            backend="pgvector", operation="delete_by_notebook", status="success"
        ).inc()
    except Exception:
        session.rollback()
        vector_store_operations_total.labels(
            backend="pgvector", operation="delete_by_notebook", status="error"
        ).inc()
        raise
    finally:
        session.close()


def get_all_chunks_for_notebook(notebook_id: str) -> list[dict[str, Any]]:
    """Retrieve all chunk payloads for a notebook (used for BM25 indexing)."""
    session = _get_session()
    try:
        nb_uuid = uuid.UUID(str(notebook_id))
        rows = list(
            session.execute(
                select(DocumentChunk).where(DocumentChunk.notebook_id == nb_uuid)
            )
            .scalars()
            .all()
        )
        return [_row_to_payload(r) for r in rows]
    finally:
        session.close()


def get_chunks_by_ids(chunk_ids: list[str]) -> list[dict[str, Any]]:
    """Retrieve specific chunk payloads by their chunk IDs."""
    if not chunk_ids:
        return []

    session = _get_session()
    try:
        rows = list(
            session.execute(
                select(DocumentChunk).where(DocumentChunk.chunk_id.in_(chunk_ids))
            )
            .scalars()
            .all()
        )
        return [_row_to_payload(r) for r in rows]
    except Exception as exc:
        logger.warning("Failed to retrieve chunks by IDs from pgvector: %s", exc)
        return []
    finally:
        session.close()
