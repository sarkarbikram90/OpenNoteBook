"""OpenNotebook — Source management API endpoints.

Provides source upload (file + URL/YouTube), listing, deletion, re-index,
and real-time SSE status streaming.
"""

from __future__ import annotations

import json
import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select

from app.api.v1.schemas.sources import (
    SourceListResponse,
    SourceResponse,
    SourceUploadResponse,
    SourceUploadURL,
)
from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession
from app.infrastructure.db.models import Notebook, Source

router = APIRouter(prefix="/notebooks/{notebook_id}/sources", tags=["sources"])

# Supported MIME types for file uploads
_ALLOWED_MIME_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "txt",
    "text/markdown": "md",
    "text/x-markdown": "md",
}

# Allowed file extensions as fallback
_ALLOWED_EXTENSIONS = {
    ".pdf": "pdf",
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
    file: UploadFile = File(..., description="PDF, DOCX, TXT, or Markdown file"),
) -> SourceUploadResponse:
    """Upload a file source and queue it for async processing.

    1. Validates file type (MIME + extension) and size (≤50MB).
    2. Uploads to MinIO.
    3. Creates Source record with PENDING status.
    4. Dispatches ``process_source`` Celery task.
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

    # Upload to MinIO
    source_id = uuid.uuid4()
    object_name = f"sources/{source_id}/{file.filename}"

    from app.infrastructure.minio.client import upload_file
    upload_file(content, object_name, content_type=file.content_type or "application/octet-stream")

    # Create source record
    source = Source(
        id=source_id,
        notebook_id=notebook_id,
        name=file.filename,
        source_type=source_type,
        storage_path=object_name,
        status="PENDING",
    )
    db.add(source)
    await db.flush()

    # Dispatch Celery task
    from app.worker.tasks.process_source import process_source
    process_source.delay(str(source_id))

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
) -> SourceUploadResponse:
    """Ingest a web page URL or YouTube video and queue for processing."""
    await _verify_notebook_ownership(notebook_id, user.id, db)

    source_id = uuid.uuid4()
    name = body.name or body.url[:100]

    source = Source(
        id=source_id,
        notebook_id=notebook_id,
        name=name,
        source_type=body.source_type,
        source_url=body.url,
        status="PENDING",
    )
    db.add(source)
    await db.flush()

    # Dispatch Celery task
    from app.worker.tasks.process_source import process_source
    process_source.delay(str(source_id))

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
) -> SourceListResponse:
    """List all sources in a notebook."""
    await _verify_notebook_ownership(notebook_id, user.id, db)

    result = await db.execute(
        select(Source)
        .where(Source.notebook_id == notebook_id)
        .order_by(Source.created_at.desc())
    )
    sources = list(result.scalars().all())
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

    # Clean up MinIO file
    if source.storage_path:
        try:
            from app.infrastructure.minio.client import delete_file
            delete_file(source.storage_path)
        except Exception:
            pass

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

    from app.worker.tasks.process_source import process_source
    process_source.delay(str(source_id))

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
        async for event in subscribe_status(str(source_id)):
            data = json.dumps(event)
            yield f"event: status\ndata: {data}\n\n"

            if event.get("status") in ("READY", "FAILED"):
                yield f"event: done\ndata: {{}}\n\n"
                break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
