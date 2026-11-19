"""OpenNotebook — Dedicated Cloud Run HTTP Worker Entrypoint.

Serves as a serverless ingestion worker on Google Cloud Run where Celery + Redis
may not be provisioned. Handles:
- ``POST /pubsub/gcs-finalize``: Pub/Sub push notifications for GCS ``OBJECT_FINALIZE``
- ``POST /tasks/process-source/{source_id}``: Internal API-triggered ingestion
- ``POST /tasks/reindex-source/{source_id}``: Internal API-triggered re-indexing
- ``GET /health``: Liveness/readiness probe

Unlike FastAPI ``BackgroundTasks`` on the API service, each ingestion job runs
inside the worker's HTTP request lifecycle (in a threadpool) so Cloud Run keeps
CPU allocated for the entire extraction/OCR/chunking/embedding pipeline and
Pub/Sub only ACKs once processing succeeds.
"""

from __future__ import annotations

import hmac
import logging
import uuid
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query, status
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.metrics import pubsub_events_total
from app.infrastructure.db.models import Notebook, Source
from app.infrastructure.pubsub.gcs_events import (
    is_generation_already_processed,
    parse_pubsub_push_envelope,
    parse_raw_object_key,
    record_generation_on_metadata,
)
from app.infrastructure.rust_accel import is_rust_available
from app.worker.tasks.process_source import (
    _get_sync_session,
    execute_process_source,
    execute_reindex_source,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="OpenNotebook Ingestion Worker",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
)


def verify_worker_token(
    expected_token: str,
    *,
    header_token: str | None = None,
    query_token: str | None = None,
    authorization: str | None = None,
    app_env: str = "development",
) -> None:
    """Validate internal worker or Pub/Sub push token in constant time.

    Fails closed in production if no verification token is configured.
    """
    if not expected_token:
        if app_env.lower() in ("production", "prod"):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Worker endpoint disabled: verification token not configured in production",
            )
        return

    candidate = (header_token or query_token or "").strip()
    if not candidate and authorization and authorization.lower().startswith("bearer "):
        candidate = authorization[7:].strip()

    if not candidate or not hmac.compare_digest(candidate, expected_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid worker authentication token",
        )


@app.get("/health", status_code=status.HTTP_200_OK)
async def worker_health() -> dict[str, Any]:
    """Liveness and capability check for the Cloud Run ingestion worker."""
    settings = get_settings()
    return {
        "status": "ok",
        "service": "opennotebook-worker",
        "rust_accel": is_rust_available(),
        "storage_provider": settings.storage_provider,
        "vector_store_provider": settings.vector_store_provider,
    }


def _register_and_process_gcs_event(payload: dict[str, Any]) -> dict[str, Any]:
    """Synchronously record GCS event idempotently and run ingestion."""
    try:
        event = parse_pubsub_push_envelope(payload)
    except ValueError as exc:
        pubsub_events_total.labels(event_type="OBJECT_FINALIZE", status="invalid").inc()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if event is None:
        return {"status": "ignored", "reason": "non_finalize_event"}

    parsed_key = parse_raw_object_key(event.object_name)
    if parsed_key is None:
        pubsub_events_total.labels(event_type=event.event_type, status="ignored").inc()
        return {
            "status": "ignored",
            "reason": "non_raw_object",
            "object_name": event.object_name,
        }

    session = _get_sync_session()
    try:
        source = session.execute(
            select(Source).where(Source.id == parsed_key.source_id)
        ).scalar_one_or_none()

        if source is not None:
            if is_generation_already_processed(
                source.status, source.metadata_, event.generation
            ):
                pubsub_events_total.labels(
                    event_type=event.event_type, status="duplicate"
                ).inc()
                return {
                    "status": "duplicate_ignored",
                    "source_id": str(source.id),
                    "generation": event.generation,
                }

            source.storage_path = event.object_name
            source.storage_type = "gcs"
            source.content_type = event.content_type or source.content_type
            if not source.checksum and event.metadata.get("sha256"):
                source.checksum = event.metadata["sha256"]
            source.metadata_ = record_generation_on_metadata(source.metadata_, event)
            source.status = "QUEUED"
            source.error_message = None
            session.commit()
        else:
            notebook = session.execute(
                select(Notebook).where(Notebook.id == parsed_key.notebook_id)
            ).scalar_one_or_none()
            if notebook is None:
                pubsub_events_total.labels(
                    event_type=event.event_type, status="ignored"
                ).inc()
                return {
                    "status": "ignored",
                    "reason": "notebook_not_found",
                    "notebook_id": str(parsed_key.notebook_id),
                }

            source = Source(
                id=parsed_key.source_id,
                notebook_id=parsed_key.notebook_id,
                name=event.metadata.get("original_filename") or parsed_key.filename,
                source_type=parsed_key.source_type,
                storage_path=event.object_name,
                storage_type="gcs",
                content_type=event.content_type,
                checksum=event.metadata.get("sha256"),
                status="QUEUED",
                metadata_=record_generation_on_metadata(event.metadata, event),
            )
            session.add(source)
            session.commit()

        source_id = str(source.id)
    finally:
        session.close()

    pubsub_events_total.labels(event_type=event.event_type, status="accepted").inc()
    result = execute_process_source(source_id)
    return {
        "status": "processed",
        "source_id": source_id,
        "notebook_id": str(parsed_key.notebook_id),
        "generation": event.generation,
        "result": result,
    }


@app.post("/pubsub/gcs-finalize", status_code=status.HTTP_200_OK)
async def handle_worker_pubsub_gcs_finalize(
    payload: dict[str, Any],
    token: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Process a GCS OBJECT_FINALIZE Pub/Sub push notification end-to-end."""
    settings = get_settings()
    verify_worker_token(
        settings.pubsub_verification_token.strip(),
        query_token=token,
        authorization=authorization,
        app_env=settings.app_env,
    )
    return await run_in_threadpool(_register_and_process_gcs_event, payload)


@app.post("/tasks/process-source/{source_id}", status_code=status.HTTP_200_OK)
async def handle_process_source_task(
    source_id: uuid.UUID,
    x_worker_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Execute source ingestion synchronously inside the Cloud Run worker."""
    settings = get_settings()
    expected = (settings.worker_auth_token or settings.pubsub_verification_token).strip()
    verify_worker_token(
        expected,
        header_token=x_worker_token,
        authorization=authorization,
        app_env=settings.app_env,
    )
    result = await run_in_threadpool(execute_process_source, str(source_id))
    return {"status": "processed", "source_id": str(source_id), "result": result}


@app.post("/tasks/reindex-source/{source_id}", status_code=status.HTTP_200_OK)
async def handle_reindex_source_task(
    source_id: uuid.UUID,
    x_worker_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Execute source re-indexing synchronously inside the Cloud Run worker."""
    settings = get_settings()
    expected = (settings.worker_auth_token or settings.pubsub_verification_token).strip()
    verify_worker_token(
        expected,
        header_token=x_worker_token,
        authorization=authorization,
        app_env=settings.app_env,
    )
    result = await run_in_threadpool(execute_reindex_source, str(source_id))
    return {"status": "reindexed", "source_id": str(source_id), "result": result}
