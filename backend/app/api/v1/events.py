"""OpenNotebook — Google Cloud Pub/Sub event ingestion endpoints.

Receives Cloud Storage ``OBJECT_FINALIZE`` notifications pushed via Google
Cloud Pub/Sub, enforces object-generation idempotency, and triggers the
asynchronous document processing worker.
"""

from __future__ import annotations

import hmac
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, status
from sqlalchemy import select

from app.api.v1.sources import _dispatch_source_task
from app.core.config import get_settings
from app.core.deps import DbSession
from app.core.metrics import pubsub_events_total
from app.infrastructure.db.models import Notebook, Source
from app.infrastructure.pubsub.gcs_events import (
    is_generation_already_processed,
    parse_pubsub_push_envelope,
    parse_raw_object_key,
    record_generation_on_metadata,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/events", tags=["events"])


def _verify_pubsub_token(
    expected_token: str,
    query_token: str | None,
    authorization: str | None,
) -> None:
    """Validate optional Pub/Sub push verification token in constant time."""
    if not expected_token:
        return

    candidate = (query_token or "").strip()
    if not candidate and authorization and authorization.lower().startswith("bearer "):
        candidate = authorization[7:].strip()

    if not candidate or not hmac.compare_digest(candidate, expected_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Pub/Sub verification token",
        )


@router.post(
    "/gcs-finalize",
    status_code=status.HTTP_200_OK,
    summary="Handle GCS OBJECT_FINALIZE notifications from Google Cloud Pub/Sub",
)
async def handle_gcs_finalize_event(
    payload: dict[str, Any],
    db: DbSession,
    background_tasks: BackgroundTasks,
    token: str | None = Query(default=None, description="Optional Pub/Sub verification token"),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Process a Cloud Storage OBJECT_FINALIZE notification idempotently.

    Returns HTTP 200 for ignored or duplicate events so Pub/Sub acknowledges
    delivery without unnecessary retries, and HTTP 400/500 on malformed or
    transient failures so Pub/Sub applies its retry / DLQ policy.
    """
    settings = get_settings()
    _verify_pubsub_token(
        settings.pubsub_verification_token.strip(),
        token,
        authorization,
    )

    try:
        event = parse_pubsub_push_envelope(payload)
    except ValueError as exc:
        pubsub_events_total.labels(
            event_type="OBJECT_FINALIZE", status="invalid"
        ).inc()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if event is None:
        return {"status": "ignored", "reason": "non_finalize_event"}

    parsed_key = parse_raw_object_key(event.object_name)
    if parsed_key is None:
        pubsub_events_total.labels(
            event_type=event.event_type, status="ignored"
        ).inc()
        return {
            "status": "ignored",
            "reason": "non_raw_object",
            "object_name": event.object_name,
        }

    result = await db.execute(
        select(Source).where(Source.id == parsed_key.source_id)
    )
    source = result.scalar_one_or_none()

    if source is not None:
        if is_generation_already_processed(
            source.status, source.metadata_, event.generation
        ):
            pubsub_events_total.labels(
                event_type=event.event_type, status="duplicate"
            ).inc()
            logger.info(
                "Ignoring duplicate GCS OBJECT_FINALIZE for source %s (generation=%s)",
                source.id,
                event.generation,
            )
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
        await db.flush()
    else:
        nb_result = await db.execute(
            select(Notebook).where(Notebook.id == parsed_key.notebook_id)
        )
        notebook = nb_result.scalar_one_or_none()
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
        db.add(source)
        await db.flush()

    pubsub_events_total.labels(
        event_type=event.event_type, status="accepted"
    ).inc()
    _dispatch_source_task(source.id, background_tasks)

    return {
        "status": "queued",
        "source_id": str(source.id),
        "notebook_id": str(source.notebook_id),
        "object_name": event.object_name,
        "generation": event.generation,
    }
