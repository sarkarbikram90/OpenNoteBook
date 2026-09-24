"""OpenNotebook — scheduled connector synchronization.

Two Celery tasks:
    poll_connectors   (Celery beat) finds connectors whose cron schedule is due
                      and enqueues a sync for each.
    sync_connector    runs one connector's incremental sync, deduplicates
                      documents against the notebook, stores new raw files in
                      the lake, creates Source rows, and dispatches processing.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


# ── Beat: poll due connectors ───────────────────────────────────────────────


@celery_app.task(name="app.worker.tasks.connector_sync.poll_connectors")
def poll_connectors() -> dict[str, int]:
    """Dispatch syncs for connectors whose schedule is due."""
    from sqlalchemy import select

    from app.domain.connectors.scheduling import is_schedule_due
    from app.infrastructure.db.models import ConnectorConfig
    from app.worker.tasks.process_source import _get_sync_session

    session = _get_sync_session()
    now = datetime.now(UTC)
    dispatched = 0
    checked = 0
    try:
        connectors = (
            session.execute(select(ConnectorConfig).where(ConnectorConfig.status == "ACTIVE"))
            .scalars()
            .all()
        )
        for connector in connectors:
            checked += 1
            if connector.schedule_cron and is_schedule_due(
                connector.schedule_cron, now, connector.last_sync_at
            ):
                sync_connector.delay(str(connector.id))
                dispatched += 1
    finally:
        session.close()

    logger.info("poll_connectors: checked=%d dispatched=%d", checked, dispatched)
    return {"checked": checked, "dispatched": dispatched}


# ── Sync one connector ──────────────────────────────────────────────────────


@celery_app.task(
    bind=True,
    name="app.worker.tasks.connector_sync.sync_connector",
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def sync_connector(self, connector_id: str) -> dict[str, Any]:
    """Run an incremental sync for a single connector and ingest new documents."""
    from sqlalchemy import select, update

    from app.domain.connectors.factory import build_connector
    from app.domain.connectors.ingest import plan_ingest
    from app.domain.connectors.timeutil import ensure_utc
    from app.infrastructure.db.models import ConnectorConfig, Source
    from app.infrastructure.storage.paths import raw_key
    from app.infrastructure.storage.service import get_storage_service
    from app.worker.tasks.process_source import _get_sync_session, process_source

    session = _get_sync_session()
    try:
        connector = session.execute(
            select(ConnectorConfig).where(ConnectorConfig.id == uuid.UUID(connector_id))
        ).scalar_one_or_none()
        if connector is None:
            logger.warning("sync_connector: connector %s not found", connector_id)
            return {"connector_id": connector_id, "status": "not_found"}

        if connector.notebook_id is None:
            raise ValueError("Connector has no target notebook")

        since = ensure_utc(connector.last_sync_at)
        conn = build_connector(connector.connector_type, connector.config_json)
        documents = conn.sync(since=since)

        existing_checksums = (
            session.execute(
                select(Source.checksum).where(
                    Source.notebook_id == connector.notebook_id,
                    Source.checksum.is_not(None),
                )
            )
            .scalars()
            .all()
        )
        plan = plan_ingest(documents, existing_checksums)

        storage = get_storage_service()
        source_ids: list[str] = []
        for planned in plan.to_ingest:
            document = planned.document
            source_id = uuid.uuid4()
            storage_path = raw_key(str(connector.notebook_id), str(source_id), planned.filename)
            storage.upload_raw_document(
                planned.content, storage_path, content_type=planned.content_type
            )

            session.add(
                Source(
                    id=source_id,
                    notebook_id=connector.notebook_id,
                    name=document.title,
                    source_type=document.source_type,
                    source_url=document.url,
                    storage_path=storage_path,
                    storage_type=storage.provider,
                    content_type=planned.content_type,
                    checksum=planned.checksum,
                    allowed_roles=list(document.allowed_roles or []),
                    allowed_users=list(document.allowed_users or []),
                    status="PENDING",
                    metadata_={
                        "sha256": planned.checksum,
                        "connector_id": str(connector.id),
                        **(document.metadata or {}),
                    },
                )
            )
            source_ids.append(str(source_id))

        session.execute(
            update(ConnectorConfig)
            .where(ConnectorConfig.id == connector.id)
            .values(status="ACTIVE", last_sync_at=datetime.now(UTC), error_message=None)
        )
        session.commit()

        for source_id in source_ids:
            process_source.delay(source_id)

        logger.info(
            "sync_connector %s: found=%d ingested=%d skipped=%d",
            connector_id,
            len(documents),
            len(source_ids),
            plan.skipped,
        )
        return {
            "connector_id": connector_id,
            "status": "ok",
            "documents_found": len(documents),
            "documents_ingested": len(source_ids),
            "documents_skipped": plan.skipped,
        }

    except Exception as exc:
        session.rollback()
        session.execute(
            update(ConnectorConfig)
            .where(ConnectorConfig.id == uuid.UUID(connector_id))
            .values(status="ERROR", error_message=str(exc))
        )
        session.commit()
        logger.error("sync_connector %s failed: %s", connector_id, exc, exc_info=True)

        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc) from exc
        return {"connector_id": connector_id, "status": "failed", "error": str(exc)}
    finally:
        session.close()
