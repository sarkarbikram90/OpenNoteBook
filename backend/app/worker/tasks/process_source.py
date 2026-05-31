"""OpenNotebook — Source processing Celery task.

Orchestrates the full async pipeline:
1. EXTRACTING — fetch file from MinIO (or scrape URL), extract text
2. CHUNKING — semantic chunk with metadata
3. EMBEDDING — batch embed (64 at a time)
4. Upsert vectors to Qdrant with full payload
5. Build BM25 index for notebook
6. READY — update source status + chunk_count

Each status transition publishes to Redis for SSE real-time progress.
On failure after max retries, the task logs to the DLQ.
"""

from __future__ import annotations

import logging
import traceback
import uuid

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.worker.celery_app import celery_app
from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _get_sync_session() -> Session:
    """Create a synchronous SQLAlchemy session for use in Celery tasks.

    Celery tasks run in a synchronous context, so we need a sync engine
    and session rather than the async ones used by FastAPI.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    settings = get_settings()
    # Convert async URL to sync URL
    sync_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(sync_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _update_source_status(
    source_id: str,
    status: str,
    error_message: str | None = None,
    chunk_count: int | None = None,
    page_count: int | None = None,
    embedding_model: str | None = None,
) -> None:
    """Update the source record status in the database and publish to Redis."""
    from app.infrastructure.db.models import Source
    from app.infrastructure.redis.client import publish_status

    session = _get_sync_session()
    try:
        values: dict = {"status": status}
        if error_message is not None:
            values["error_message"] = error_message
        if chunk_count is not None:
            values["chunk_count"] = chunk_count
        if page_count is not None:
            values["page_count"] = page_count
        if embedding_model is not None:
            values["embedding_model"] = embedding_model

        session.execute(
            update(Source).where(Source.id == uuid.UUID(source_id)).values(**values)
        )
        session.commit()
    finally:
        session.close()

    # Publish status event for SSE
    publish_status(source_id, status, {
        "chunk_count": chunk_count,
        "error_message": error_message,
    })


def _get_source_record(source_id: str) -> dict:
    """Fetch the source record from the database."""
    from app.infrastructure.db.models import Source
    from sqlalchemy import select

    session = _get_sync_session()
    try:
        result = session.execute(
            select(Source).where(Source.id == uuid.UUID(source_id))
        )
        source = result.scalar_one_or_none()
        if source is None:
            raise ValueError(f"Source not found: {source_id}")
        return {
            "id": str(source.id),
            "notebook_id": str(source.notebook_id),
            "name": source.name,
            "source_type": source.source_type,
            "storage_path": source.storage_path,
            "source_url": source.source_url,
        }
    finally:
        session.close()


@celery_app.task(
    bind=True,
    name="app.worker.tasks.process_source",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def process_source(self, source_id: str) -> dict:
    """Main source processing pipeline task.

    Args:
        source_id: UUID of the source to process.

    Returns:
        Dict with processing result summary.
    """
    from app.domain.sources.extractor import extract
    from app.domain.sources.chunker import chunk_document
    from app.domain.sources.embedder import embed_texts
    from app.domain.sources.bm25_index import build_bm25_index
    from app.infrastructure.minio.client import download_file
    from app.infrastructure.qdrant.client import upsert_chunks, ChunkPayload, delete_by_source

    settings = get_settings()

    try:
        # Load source record
        source = _get_source_record(source_id)
        notebook_id = source["notebook_id"]
        source_type = source["source_type"]

        logger.info(
            "Processing source %s (type=%s, notebook=%s)",
            source_id, source_type, notebook_id,
        )

        # ── Step 1: EXTRACTING ──────────────────────────────────────────
        _update_source_status(source_id, "EXTRACTING")

        if source_type in ("url", "youtube"):
            # URL/YouTube: extract from the URL directly
            content = source["source_url"] or ""
        else:
            # File-based: download from MinIO
            storage_path = source["storage_path"]
            if not storage_path:
                raise ValueError(f"No storage path for source {source_id}")
            content = download_file(storage_path)

        extraction = extract(source_type, content)

        page_count = extraction.metadata.get("page_count", len(extraction.pages))

        # ── Step 2: CHUNKING ────────────────────────────────────────────
        _update_source_status(source_id, "CHUNKING", page_count=page_count)

        chunks = chunk_document(
            extraction=extraction,
            source_id=source_id,
            notebook_id=notebook_id,
            embedding_model=settings.embedding_model,
        )

        if not chunks:
            _update_source_status(
                source_id, "READY",
                chunk_count=0,
                page_count=page_count,
                embedding_model=settings.embedding_model,
            )
            return {"source_id": source_id, "status": "READY", "chunks": 0}

        # ── Step 3: EMBEDDING ───────────────────────────────────────────
        _update_source_status(source_id, "EMBEDDING")

        texts = [chunk.text for chunk in chunks]
        vectors = embed_texts(texts, batch_size=settings.embedding_batch_size)

        # ── Step 4: Upsert to Qdrant ────────────────────────────────────
        # Delete any existing vectors for this source (in case of re-index)
        delete_by_source(source_id)

        chunk_payloads = [
            ChunkPayload(
                chunk_id=chunk.chunk_id,
                source_id=chunk.source_id,
                notebook_id=chunk.notebook_id,
                text=chunk.text,
                token_count=chunk.token_count,
                page=chunk.page,
                section=chunk.section,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
                embedding_model=chunk.embedding_model,
                vector=vector,
            )
            for chunk, vector in zip(chunks, vectors)
        ]

        upsert_chunks(chunk_payloads)

        # ── Step 5: Build BM25 index ────────────────────────────────────
        build_bm25_index(notebook_id)

        # ── Step 6: READY ───────────────────────────────────────────────
        _update_source_status(
            source_id, "READY",
            chunk_count=len(chunks),
            page_count=page_count,
            embedding_model=settings.embedding_model,
        )

        logger.info(
            "Source %s processed successfully: %d chunks, %d pages",
            source_id, len(chunks), page_count,
        )
        return {
            "source_id": source_id,
            "status": "READY",
            "chunks": len(chunks),
            "pages": page_count,
        }

    except Exception as exc:
        error_msg = str(exc)
        tb = traceback.format_exc()
        logger.error("Source processing failed for %s: %s", source_id, error_msg)

        if self.request.retries < self.max_retries:
            _update_source_status(source_id, "PENDING", error_message=f"Retry {self.request.retries + 1}: {error_msg}")
            raise self.retry(exc=exc)

        # Max retries exhausted — move to DLQ
        _update_source_status(source_id, "FAILED", error_message=error_msg)

        from app.worker.dlq import handle_dlq
        handle_dlq(source_id, error_msg, tb)

        return {
            "source_id": source_id,
            "status": "FAILED",
            "error": error_msg,
        }
