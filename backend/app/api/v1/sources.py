"""OpenNotebook — Source management API endpoints.

Provides source upload (file + URL/YouTube), listing, deletion, re-index,
and real-time SSE status streaming.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select

from app.api.v1.schemas.sources import (
    SourceListResponse,
    SourceResponse,
    SourceUploadResponse,
    SourceUploadURL,
)
from app.core.audit import record_audit_event
from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession
from app.domain.sources.dedup import find_source_by_checksum
from app.infrastructure.db.models import Notebook, Source
from app.infrastructure.storage.paths import raw_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notebooks/{notebook_id}/sources", tags=["sources"])


def _dispatch_source_task(source_id: uuid.UUID, background_tasks: BackgroundTasks | None = None) -> None:
    """Dispatch source processing to Celery if available, or fallback to in-process execution."""
    from app.infrastructure.redis.client import is_redis_available

    dispatched = False
    if is_redis_available():
        try:
            from app.worker.tasks.process_source import process_source
            process_source.delay(str(source_id))
            dispatched = True
            logger.info("Dispatched source %s to Celery queue", source_id)
        except Exception as exc:
            logger.warning(
                "Celery task dispatch failed for source %s (%s). Falling back to in-process background execution.",
                source_id,
                exc,
            )

    if not dispatched:
        def _in_process_worker():
            try:
                from app.worker.tasks.process_source import execute_process_source
                execute_process_source(str(source_id))
            except Exception as inner_exc:
                logger.error("In-process source processing failed for %s: %s", source_id, inner_exc)
                try:
                    from app.worker.tasks.process_source import _update_source_status
                    _update_source_status(str(source_id), "FAILED", error_message=str(inner_exc))
                except Exception:
                    pass

        if background_tasks is not None:
            background_tasks.add_task(_in_process_worker)
        else:
            import threading
            threading.Thread(target=_in_process_worker, daemon=True).start()


def _dispatch_reindex_task(source_id: uuid.UUID, background_tasks: BackgroundTasks | None = None) -> None:
    """Dispatch reindex to Celery if available, or fallback to in-process execution."""
    from app.infrastructure.redis.client import is_redis_available

    dispatched = False
    if is_redis_available():
        try:
            from app.worker.tasks.process_source import reindex_source
            reindex_source.delay(str(source_id))
            dispatched = True
            logger.info("Dispatched reindex for source %s to Celery", source_id)
        except Exception as exc:
            logger.warning(
                "Celery reindex dispatch failed for source %s (%s). Falling back to in-process execution.",
                source_id,
                exc,
            )

    if not dispatched:
        def _in_process_reindex():
            try:
                from app.worker.tasks.process_source import execute_reindex_source
                execute_reindex_source(str(source_id))
            except Exception as inner_exc:
                logger.error("In-process reindex failed for %s: %s", source_id, inner_exc)
                try:
                    from app.worker.tasks.process_source import _update_source_status
                    _update_source_status(str(source_id), "FAILED", error_message=str(inner_exc))
                except Exception:
                    pass

        if background_tasks is not None:
            background_tasks.add_task(_in_process_reindex)
        else:
            import threading
            threading.Thread(target=_in_process_reindex, daemon=True).start()

# Supported MIME types for file uploads
_ALLOWED_MIME_TYPES = {
    "application/pdf": "pdf",
    "image/jpeg": "image",
    "image/png": "image",
    "image/webp": "image",
    "image/tiff": "image",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "txt",
    "text/markdown": "md",
    "text/x-markdown": "md",
}

# Allowed file extensions as fallback
_ALLOWED_EXTENSIONS = {
    ".pdf": "pdf",
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".webp": "image",
    ".tif": "image",
    ".tiff": "image",
    ".docx": "docx",
    ".txt": "txt",
    ".md": "md",
}


# ── Helpers ─────────────────────────────────────────────────────────────────


async def _verify_notebook_ownership(
    notebook_id: uuid.UUID, user_id: uuid.UUID, db: DbSession
) -> Notebook:
    """Verify the notebook exists and belongs to the current user."""
    result = await db.execute(
        select(Notebook).where(
            Notebook.id == notebook_id,
            Notebook.user_id == user_id,
        )
    )
    notebook = result.scalar_one_or_none()
    if notebook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notebook not found",
        )
    return notebook


def _detect_source_type(filename: str, content_type: str | None) -> str:
    """Detect source type from MIME type or filename extension."""
    # Try MIME type first
    if content_type and content_type in _ALLOWED_MIME_TYPES:
        return _ALLOWED_MIME_TYPES[content_type]

    # Fall back to file extension
    for ext, stype in _ALLOWED_EXTENSIONS.items():
        if filename.lower().endswith(ext):
            return stype

    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail=f"Unsupported file type. Allowed: PDF, DOCX, TXT, Markdown",
    )


# ── File Upload Endpoint ───────────────────────────────────────────────────


@router.post(
    "/upload",
    response_model=SourceUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a file source",
)
async def upload_file_source(
    notebook_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF, DOCX, TXT, or Markdown file"),
) -> SourceUploadResponse:
    """Upload a file source and queue it for async processing.

    1. Validates file type (MIME + extension) and size (≤50MB).
    2. Uploads to MinIO.
    3. Creates Source record with PENDING status.
    4. Dispatches ``process_source`` Celery task (or fallback).
    5. Returns 202 Accepted with source_id.
    """
    settings = get_settings()
    await _verify_notebook_ownership(notebook_id, user.id, db)

    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    source_type = _detect_source_type(file.filename, file.content_type)

    # Read file content and check size
    content = await file.read()
    max_size = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {settings.max_upload_size_mb}MB limit",
        )

    # Upload to the configured object-storage provider (GCS, MinIO/S3, or local).
    from app.infrastructure.storage.service import get_storage_service, StorageService

    file_hash = StorageService.calculate_file_hash(content)

    # Deduplicate: skip if an identical document already exists in this notebook.
    existing = await find_source_by_checksum(db, notebook_id, file_hash)
    if existing is not None:
        await record_audit_event(
            db=db,
            action="source.upload.duplicate",
            resource_type="source",
            resource_id=str(existing.id),
            user_id=user.id,
            details={"name": file.filename, "checksum": file_hash},
        )
        return SourceUploadResponse(
            source_id=existing.id,
            status=existing.status,
            message="Duplicate document detected; using existing source",
            duplicate=True,
        )

    source_id = uuid.uuid4()
    object_name = raw_key(str(notebook_id), str(source_id), file.filename)

    storage = get_storage_service()
    storage.upload_raw_document(
        content,
        object_name,
        content_type=file.content_type or "application/octet-stream",
        metadata={
            "sha256": file_hash,
            "source_id": str(source_id),
            "notebook_id": str(notebook_id),
            "original_filename": file.filename,
        },
    )

    # Create source record with provenance metadata
    source = Source(
        id=source_id,
        notebook_id=notebook_id,
        name=file.filename,
        source_type=source_type,
        storage_path=object_name,
        storage_type=storage.provider,
        content_type=file.content_type,
        checksum=file_hash,
        status="PENDING",
        metadata_={"sha256": file_hash, "size_bytes": len(content)},
    )
    db.add(source)
    await db.flush()

    await record_audit_event(
        db=db,
        action="source.upload",
        resource_type="source",
        resource_id=str(source_id),
        user_id=user.id,
        details={"name": file.filename, "source_type": source_type, "notebook_id": str(notebook_id)},
    )

    # Dispatch Celery task with background task fallback
    _dispatch_source_task(source_id, background_tasks)

    return SourceUploadResponse(source_id=source_id)


# ── URL / YouTube Upload Endpoint ──────────────────────────────────────────


@router.post(
    "/url",
    response_model=SourceUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a URL or YouTube source",
)
async def upload_url_source(
    notebook_id: uuid.UUID,
    body: SourceUploadURL,
    user: CurrentUser,
    db: DbSession,
    background_tasks: BackgroundTasks,
) -> SourceUploadResponse:
    """Ingest a web page URL or YouTube video and queue for processing."""
    await _verify_notebook_ownership(notebook_id, user.id, db)

    source_id = uuid.uuid4()
    name = body.name or body.url[:100]

    from app.infrastructure.storage.service import get_storage_service

    # URL/transcript sources have no raw upload, but their processed artifacts
    # must still be written to the configured object-storage provider.
    storage_provider = get_storage_service().provider
    source = Source(
        id=source_id,
        notebook_id=notebook_id,
        name=name,
        source_type=body.source_type,
        source_url=body.url,
        storage_type=storage_provider,
        status="PENDING",
    )
    db.add(source)
    await db.flush()

    await record_audit_event(
        db=db,
        action="source.upload_url",
        resource_type="source",
        resource_id=str(source_id),
        user_id=user.id,
        details={"name": name, "url": str(body.url), "notebook_id": str(notebook_id)},
    )

    # Dispatch Celery task with background task fallback
    _dispatch_source_task(source_id, background_tasks)

    return SourceUploadResponse(source_id=source_id)


# ── List Sources ────────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=SourceListResponse,
    summary="List sources in a notebook",
)
async def list_sources(
    notebook_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    background_tasks: BackgroundTasks,
) -> SourceListResponse:
    """List all sources in a notebook."""
    await _verify_notebook_ownership(notebook_id, user.id, db)

    result = await db.execute(
        select(Source)
        .where(Source.notebook_id == notebook_id)
        .order_by(Source.created_at.desc())
    )
    sources = list(result.scalars().all())

    # Auto-heal: Check if any sources are stuck in PENDING or EXTRACTING for > 30 seconds
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    for s in sources:
        if s.status in ("PENDING", "EXTRACTING", "CHUNKING", "EMBEDDING"):
            created = getattr(s, "created_at", None)
            if created:
                created_dt = created.replace(tzinfo=timezone.utc) if created.tzinfo is None else created
                if (now - created_dt).total_seconds() > 30:
                    logger.info("Found stuck source %s in status %s; triggering auto-heal reprocess", s.id, s.status)
                    _dispatch_source_task(s.id, background_tasks)

    responses = [SourceResponse.model_validate(s) for s in sources]
    return SourceListResponse(sources=responses, total=len(responses))


# ── Get Source ──────────────────────────────────────────────────────────────


@router.get(
    "/{source_id}",
    response_model=SourceResponse,
    summary="Get source details",
)
async def get_source(
    notebook_id: uuid.UUID,
    source_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> SourceResponse:
    """Retrieve details for a specific source."""
    await _verify_notebook_ownership(notebook_id, user.id, db)

    result = await db.execute(
        select(Source).where(
            Source.id == source_id,
            Source.notebook_id == notebook_id,
        )
    )
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    return SourceResponse.model_validate(source)


# ── Delete Source ───────────────────────────────────────────────────────────


@router.delete(
    "/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a source",
)
async def delete_source(
    notebook_id: uuid.UUID,
    source_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> None:
    """Delete a source and its indexed data.

    Removes vectors from Qdrant, the file from MinIO, and rebuilds the
    BM25 index for the notebook.
    """
    await _verify_notebook_ownership(notebook_id, user.id, db)

    result = await db.execute(
        select(Source).where(
            Source.id == source_id,
            Source.notebook_id == notebook_id,
        )
    )
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    # Clean up Qdrant vectors
    try:
        from app.infrastructure.qdrant.client import delete_by_source
        delete_by_source(str(source_id))
    except Exception:
        pass

    # Delete raw and processed objects from the provider recorded for this source.
    try:
        from app.infrastructure.storage.paths import (
            processed_document_key,
            processed_metadata_key,
        )
        from app.infrastructure.storage.service import get_storage_service

        storage = get_storage_service(provider=source.storage_type)
        if source.storage_path:
            storage.delete_raw_document(source.storage_path)
        storage.delete_raw_document(processed_document_key(str(source_id)))
        storage.delete_raw_document(processed_metadata_key(str(source_id)))
    except Exception as storage_exc:
        logger.exception("Could not delete stored objects for source %s", source_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not delete source objects from configured storage",
        ) from storage_exc

    await record_audit_event(
        db=db,
        action="source.delete",
        resource_type="source",
        resource_id=str(source_id),
        user_id=user.id,
        details={"name": source.name, "notebook_id": str(notebook_id)},
    )

    # Delete from database
    await db.execute(
        delete(Source).where(Source.id == source_id)
    )

    # Rebuild BM25 index (best-effort)
    try:
        from app.domain.sources.bm25_index import build_bm25_index
        build_bm25_index(str(notebook_id))
    except Exception:
        pass


# ── Reindex Source ──────────────────────────────────────────────────────────


@router.post(
    "/{source_id}/reindex",
    response_model=SourceUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Re-index a source",
)
async def reindex_source(
    notebook_id: uuid.UUID,
    source_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    background_tasks: BackgroundTasks,
) -> SourceUploadResponse:
    """Re-process a source (e.g. after embedding model change).

    Resets the source status to PENDING and re-dispatches the processing task.
    """
    await _verify_notebook_ownership(notebook_id, user.id, db)

    result = await db.execute(
        select(Source).where(
            Source.id == source_id,
            Source.notebook_id == notebook_id,
        )
    )
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    source.status = "PENDING"
    source.error_message = None
    await db.flush()

    _dispatch_source_task(source_id, background_tasks)

    return SourceUploadResponse(source_id=source_id)


# ── SSE Status Endpoint ────────────────────────────────────────────────────


@router.get(
    "/{source_id}/status",
    summary="Stream source processing status (SSE)",
)
async def stream_source_status(
    notebook_id: uuid.UUID,
    source_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> StreamingResponse:
    """Stream real-time processing status updates via Server-Sent Events.

    The stream emits events for each status transition (EXTRACTING, CHUNKING,
    EMBEDDING, READY, FAILED) and closes on terminal states.
    """
    await _verify_notebook_ownership(notebook_id, user.id, db)

    # Verify source exists
    result = await db.execute(
        select(Source).where(
            Source.id == source_id,
            Source.notebook_id == notebook_id,
        )
    )
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    # If already terminal, return a single event
    if source.status in ("READY", "FAILED"):
        async def single_event():
            data = json.dumps({
                "source_id": str(source_id),
                "status": source.status,
                "chunk_count": source.chunk_count,
                "error_message": source.error_message,
            })
            yield f"event: status\ndata: {data}\n\n"
            yield f"event: done\ndata: {{}}\n\n"

        return StreamingResponse(
            single_event(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Subscribe to Redis pub/sub for live updates
    from app.infrastructure.redis.client import subscribe_status

    async def event_stream():
        # Emit current status first
        data = json.dumps({
            "source_id": str(source_id),
            "status": source.status,
        })
        yield f"event: status\ndata: {data}\n\n"

        # Stream updates from Redis
        try:
            async for event in subscribe_status(str(source_id)):
                data = json.dumps(event)
                yield f"event: status\ndata: {data}\n\n"

                if event.get("status") in ("READY", "FAILED"):
                    yield f"event: done\ndata: {{}}\n\n"
                    break
        except Exception:
            yield f"event: done\ndata: {{}}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Zero-Reupload Re-index Endpoint ─────────────────────────────────────────


@router.post(
    "/{source_id}/reindex",
    response_model=SourceUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Re-index an existing source from Data Lake",
)
async def reindex_source_endpoint(
    source_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    background_tasks: BackgroundTasks,
) -> SourceUploadResponse:
    """Re-derive chunks and vector embeddings directly from the data lake."""
    result = await db.execute(
        select(Source)
        .join(Notebook, Source.notebook_id == Notebook.id)
        .where(
            Source.id == source_id,
            Notebook.user_id == user.id,
        )
    )
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    source.status = "PENDING"
    source.error_message = None
    await db.flush()

    _dispatch_reindex_task(source_id, background_tasks)

    return SourceUploadResponse(source_id=source_id)

