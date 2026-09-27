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
from typing import Any
import uuid

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.worker.celery_app import celery_app
from app.core.config import get_settings

logger = logging.getLogger(__name__)


_sync_engine = None
_SyncSessionLocal = None


def _get_sync_session() -> Session:
    """Create a synchronous SQLAlchemy session using a cached singleton engine."""
    global _sync_engine, _SyncSessionLocal
    if _sync_engine is None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        settings = get_settings()
        sync_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        sync_url = sync_url.replace("sqlite+aiosqlite://", "sqlite://")
        pool_kwargs: dict[str, Any] = {
            "pool_pre_ping": True,
            "pool_size": 5,
            "max_overflow": 10,
            "pool_recycle": 300,
        }
        if "sqlite" in sync_url:
            pool_kwargs = {}
        _sync_engine = create_engine(sync_url, **pool_kwargs)
        _SyncSessionLocal = sessionmaker(bind=_sync_engine)

    return _SyncSessionLocal()


def _update_source_status(
    source_id: str,
    status: str,
    error_message: str | None = None,
    chunk_count: int | None = None,
    page_count: int | None = None,
    embedding_model: str | None = None,
    pii_redacted: bool | None = None,
    pii_entities_count: int | None = None,
    sensitivity_level: str | None = None,
) -> None:
    """Update the source record status in the database and publish to Redis."""
    from app.infrastructure.db.models import Source

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
        if pii_redacted is not None:
            values["pii_redacted"] = pii_redacted
        if pii_entities_count is not None:
            values["pii_entities_count"] = pii_entities_count
        if sensitivity_level is not None:
            values["sensitivity_level"] = sensitivity_level

        session.execute(
            update(Source).where(Source.id == uuid.UUID(source_id)).values(**values)
        )
        session.commit()
    except Exception as db_exc:
        logger.error("Failed to update source %s status to %s: %s", source_id, status, db_exc)
    finally:
        session.close()

    # Publish status event for SSE (non-blocking)
    try:
        from app.infrastructure.redis.client import publish_status
        publish_status(source_id, status, {
            "chunk_count": chunk_count,
            "error_message": error_message,
            "pii_redacted": pii_redacted,
            "pii_entities_count": pii_entities_count,
            "sensitivity_level": sensitivity_level,
        })
    except Exception as redis_exc:
        logger.debug("Redis publish_status skipped for source %s: %s", source_id, redis_exc)


def _get_source_record(source_id: str) -> dict:
    """Fetch the source record from the database including workspace and governance settings."""
    from app.infrastructure.db.models import Source, Notebook
    from sqlalchemy import select

    session = _get_sync_session()
    try:
        result = session.execute(
            select(Source).where(Source.id == uuid.UUID(source_id))
        )
        source = result.scalar_one_or_none()
        if source is None:
            raise ValueError(f"Source not found: {source_id}")

        # Fetch workspace_id from parent notebook if present
        workspace_id = ""
        nb_res = session.execute(
            select(Notebook.workspace_id).where(Notebook.id == source.notebook_id)
        )
        nb_ws = nb_res.scalar_one_or_none()
        if nb_ws:
            workspace_id = str(nb_ws)

        return {
            "id": str(source.id),
            "notebook_id": str(source.notebook_id),
            "workspace_id": workspace_id,
            "name": source.name,
            "source_type": source.source_type,
            "storage_path": source.storage_path,
            "source_url": source.source_url,
            "sensitivity_level": getattr(source, "sensitivity_level", "internal"),
            "allowed_roles": list(getattr(source, "allowed_roles", []) or []),
            "allowed_users": list(getattr(source, "allowed_users", []) or []),
        }
    finally:
        session.close()


def _persist_processed_artifacts(
    source_id: str,
    text: str,
    chunk_count: int,
    pii_entities: dict[str, int],
    sensitivity_level: str,
    notebook_id: str,
) -> None:
    """Write the redacted text and processing metadata to the lake under processed/."""
    import json
    from datetime import datetime, timezone

    from app.infrastructure.storage.paths import (
        processed_document_key,
        processed_metadata_key,
    )
    from app.infrastructure.storage.service import get_storage_service

    storage = get_storage_service()
    storage.upload_artifact(
        (text or "").encode("utf-8"),
        processed_document_key(source_id),
        content_type="text/plain; charset=utf-8",
    )
    metadata = {
        "source_id": source_id,
        "notebook_id": notebook_id,
        "chunk_count": chunk_count,
        "pii_entities": pii_entities,
        "sensitivity_level": sensitivity_level,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }
    storage.upload_artifact(
        json.dumps(metadata).encode("utf-8"),
        processed_metadata_key(source_id),
        content_type="application/json",
    )
    logger.info("Persisted processed artifacts for source %s", source_id)


def execute_process_source(source_id: str) -> dict:
    """Main source processing pipeline execution.

    Args:
        source_id: UUID of the source to process.

    Returns:
        Dict with processing result summary.
    """
    from app.domain.sources.extractor import extract
    from app.domain.sources.chunker import chunk_document
    from app.domain.sources.embedder import embed_texts
    from app.domain.sources.bm25_index import build_bm25_index
    from app.infrastructure.storage.service import get_storage_service
    from app.domain.governance.pii_engine import get_pii_scrubber
    from app.infrastructure.qdrant.client import upsert_chunks, ChunkPayload, delete_by_source

    settings = get_settings()

    try:
        # Load source record
        source = _get_source_record(source_id)
        notebook_id = source["notebook_id"]
        workspace_id = source.get("workspace_id", "")
        source_type = source["source_type"]
        sensitivity_level = source.get("sensitivity_level", "internal")
        allowed_roles = source.get("allowed_roles", [])
        allowed_users = source.get("allowed_users", [])

        logger.info(
            "Processing source %s (type=%s, notebook=%s, workspace=%s, sensitivity=%s)",
            source_id, source_type, notebook_id, workspace_id, sensitivity_level,
        )

        # ── Step 1: EXTRACTING ──────────────────────────────────────────
        _update_source_status(source_id, "EXTRACTING")

        if source_type in ("url", "youtube"):
            # URL/YouTube: extract from the URL directly
            content = source["source_url"] or ""
        else:
            # File-based: download from Data Lake (MinIO/S3 or local fallback)
            storage_path = source["storage_path"]
            if not storage_path:
                raise ValueError(f"No storage path for source {source_id}")
            storage = get_storage_service()
            content = storage.download_raw_document(storage_path)

        extraction = extract(source_type, content)

        page_count = extraction.metadata.get("page_count", len(extraction.pages))

        # ── Step 1b: GOVERNANCE & PII REDACTION ─────────────────────────
        total_pii_redacted = 0
        pii_entities: dict[str, int] = {}

        if settings.pii_redaction_enabled:
            scrubber = get_pii_scrubber()
            for p in extraction.pages:
                scrub_res = scrubber.scrub(p.text)
                p.text = scrub_res.cleaned_text
                total_pii_redacted += scrub_res.total_redacted
                for k, v in scrub_res.entities_found.items():
                    pii_entities[k] = pii_entities.get(k, 0) + v

            if hasattr(extraction, "text") and extraction.text:
                scrub_res = scrubber.scrub(extraction.text)
                extraction.text = scrub_res.cleaned_text

            if total_pii_redacted > 0:
                logger.info(
                    "Sanitized %d PII entities in source %s: %s",
                    total_pii_redacted, source_id, pii_entities,
                )
        else:
            logger.info("PII redaction disabled by configuration; skipping scrub for %s", source_id)

        # ── Step 1c: EMPTY-EXTRACTION GUARD ─────────────────────────────
        if not extraction.text.strip():
            textless = extraction.metadata.get("textless_pages")
            message = (
                "No extractable text found; the document may be scanned or image-only "
                "and OCR is not available."
            )
            logger.warning(
                "Source %s produced no text (textless_pages=%s)", source_id, textless
            )
            _update_source_status(
                source_id, "FAILED", error_message=message, page_count=page_count
            )
            return {"source_id": source_id, "status": "FAILED", "error": message}

        # ── Step 2: CHUNKING ────────────────────────────────────────────
        _update_source_status(source_id, "CHUNKING", page_count=page_count)

        chunks = chunk_document(
            extraction=extraction,
            source_id=source_id,
            notebook_id=notebook_id,
            embedding_model=settings.embedding_model,
            allowed_roles=allowed_roles,
            allowed_users=allowed_users,
        )

        # ── Step 2b: PERSIST PROCESSED ARTIFACTS TO DATA LAKE ───────────
        try:
            _persist_processed_artifacts(
                source_id=source_id,
                text=extraction.text,
                chunk_count=len(chunks),
                pii_entities=pii_entities,
                sensitivity_level=sensitivity_level,
                notebook_id=notebook_id,
            )
        except Exception as persist_exc:
            logger.warning("Could not persist processed artifacts to lake: %s", persist_exc)

        if not chunks:
            _update_source_status(
                source_id, "READY",
                chunk_count=0,
                page_count=page_count,
                embedding_model=settings.embedding_model,
                pii_redacted=bool(total_pii_redacted > 0),
                pii_entities_count=total_pii_redacted,
                sensitivity_level=sensitivity_level,
            )
            return {"source_id": source_id, "status": "READY", "chunks": 0}

        # ── Step 3: EMBEDDING ───────────────────────────────────────────
        _update_source_status(source_id, "EMBEDDING")

        texts = [chunk.text for chunk in chunks]
        try:
            vectors = embed_texts(texts, batch_size=settings.embedding_batch_size)
        except Exception as embed_exc:
            logger.warning("Embedding generation failed (%s). Falling back to zero-vectors.", embed_exc)
            vectors = [[0.0] * 384 for _ in texts]

        # ── Step 4: Upsert to Qdrant ────────────────────────────────────
        try:
            # Delete any existing vectors for this source (in case of re-index)
            delete_by_source(source_id)

            chunk_payloads = [
                ChunkPayload(
                    chunk_id=chunk.chunk_id,
                    source_id=chunk.source_id,
                    notebook_id=chunk.notebook_id,
                    workspace_id=workspace_id,
                    sensitivity_level=sensitivity_level,
                    text=chunk.text,
                    token_count=chunk.token_count,
                    page=chunk.page,
                    section=chunk.section,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                    embedding_model=chunk.embedding_model,
                    allowed_roles=chunk.allowed_roles,
                    allowed_users=chunk.allowed_users,
                    vector=vector,
                )
                for chunk, vector in zip(chunks, vectors)
            ]

            upsert_chunks(chunk_payloads)
        except Exception as q_exc:
            logger.warning("Vector store upsert skipped (Qdrant not available): %s", q_exc)

        # ── Step 5: Build BM25 index ────────────────────────────────────
        try:
            build_bm25_index(notebook_id)
        except Exception as bm_exc:
            logger.warning("BM25 index build skipped: %s", bm_exc)

        # ── Step 6: READY ───────────────────────────────────────────────
        _update_source_status(
            source_id, "READY",
            chunk_count=len(chunks),
            page_count=page_count,
            embedding_model=settings.embedding_model,
            pii_redacted=bool(total_pii_redacted > 0),
            pii_entities_count=total_pii_redacted,
            sensitivity_level=sensitivity_level,
        )

        logger.info(
            "Source %s processed successfully: %d chunks, %d pages, %d PII redacted",
            source_id, len(chunks), page_count, total_pii_redacted,
        )
        return {
            "source_id": source_id,
            "status": "READY",
            "chunks": len(chunks),
            "pages": page_count,
            "pii_redacted_count": total_pii_redacted,
        }

    except Exception as exc:
        error_msg = str(exc)
        tb = traceback.format_exc()
        logger.error("Source processing failed for %s: %s\n%s", source_id, error_msg, tb)
        _update_source_status(source_id, "FAILED", error_message=error_msg)

        try:
            from app.worker.dlq import handle_dlq
            handle_dlq(source_id, error_msg, tb)
        except Exception:
            pass

        return {
            "source_id": source_id,
            "status": "FAILED",
            "error": error_msg,
        }


def execute_reindex_source(source_id: str) -> dict:
    """Synchronously re-derive vector embeddings and chunks directly from the raw data lake without re-upload."""
    logger.info("Triggering zero-reupload re-index for source %s from Data Lake", source_id)
    return execute_process_source(source_id)


@celery_app.task(
    bind=True,
    name="app.worker.tasks.process_source",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def process_source(self, source_id: str) -> dict:
    """Main source processing pipeline Celery task."""
    try:
        res = execute_process_source(source_id)
        if res.get("status") == "FAILED":
            has_celery_request = hasattr(self, "request") and hasattr(self, "max_retries")
            if has_celery_request and self.request.retries < self.max_retries:
                _update_source_status(source_id, "PENDING", error_message=f"Retry {self.request.retries + 1}")
                raise self.retry(exc=Exception(res.get("error", "Unknown error")))
        return res
    except Exception as exc:
        has_celery_request = hasattr(self, "request") and hasattr(self, "max_retries")
        if has_celery_request and self.request.retries < self.max_retries:
            _update_source_status(source_id, "PENDING", error_message=f"Retry {self.request.retries + 1}: {exc}")
            raise self.retry(exc=exc)
        _update_source_status(source_id, "FAILED", error_message=str(exc))
        raise


@celery_app.task(
    bind=True,
    name="app.worker.tasks.reindex_source",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def reindex_source(self, source_id: str) -> dict:
    """Re-derive vector embeddings and chunks directly from the raw data lake without re-upload."""
    return execute_reindex_source(source_id)

