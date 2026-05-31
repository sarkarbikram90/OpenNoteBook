"""OpenNotebook — Dead Letter Queue (DLQ) handler.

Logs failed tasks (after max retries) to the ``failed_jobs`` table and
provides retry capability via the API.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, UTC

logger = logging.getLogger(__name__)


def handle_dlq(source_id: str, error: str, traceback_str: str | None = None) -> str:
    """Record a permanently failed task in the failed_jobs table.

    Args:
        source_id: UUID of the source that failed processing.
        error: Human-readable error message.
        traceback_str: Full Python traceback string.

    Returns:
        The UUID of the created failed_job record.
    """
    from sqlalchemy import insert
    from app.infrastructure.db.models import FailedJob
    from app.worker.tasks.process_source import _get_sync_session

    job_id = str(uuid.uuid4())
    session = _get_sync_session()
    try:
        session.execute(
            insert(FailedJob).values(
                id=uuid.UUID(job_id),
                source_id=uuid.UUID(source_id),
                task_name="process_source",
                error=error,
                traceback=traceback_str,
                retried=False,
            )
        )
        session.commit()
        logger.warning(
            "Source %s moved to DLQ (job_id=%s): %s",
            source_id, job_id, error,
        )
    finally:
        session.close()

    return job_id


def retry_failed_job(job_id: str) -> str:
    """Retry a failed job by re-dispatching the source processing task.

    Args:
        job_id: UUID of the failed_job record.

    Returns:
        The source_id that was re-dispatched.

    Raises:
        ValueError: If the job is not found or was already retried.
    """
    from sqlalchemy import select, update
    from app.infrastructure.db.models import FailedJob
    from app.worker.tasks.process_source import _get_sync_session, process_source

    session = _get_sync_session()
    try:
        result = session.execute(
            select(FailedJob).where(FailedJob.id == uuid.UUID(job_id))
        )
        job = result.scalar_one_or_none()

        if job is None:
            raise ValueError(f"Failed job not found: {job_id}")
        if job.retried:
            raise ValueError(f"Failed job already retried: {job_id}")

        source_id = str(job.source_id)

        # Mark as retried
        session.execute(
            update(FailedJob)
            .where(FailedJob.id == uuid.UUID(job_id))
            .values(retried=True)
        )
        session.commit()

        # Re-dispatch the task
        process_source.delay(source_id)
        logger.info("Retried failed job %s (source=%s)", job_id, source_id)

        return source_id
    finally:
        session.close()
