"""OpenNotebook — Jobs / DLQ management API endpoints.

Exposes failed tasks and allows manual retry.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.v1.schemas.jobs import (
    FailedJobListResponse,
    FailedJobResponse,
    RetryResponse,
)
from app.core.deps import CurrentUser, DbSession
from app.infrastructure.db.models import FailedJob, Source

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get(
    "/failed",
    response_model=FailedJobListResponse,
    summary="List failed jobs",
)
async def list_failed_jobs(
    user: CurrentUser,
    db: DbSession,
) -> FailedJobListResponse:
    """List all failed background processing jobs.

    Only shows jobs for sources belonging to the current user's notebooks.
    """
    result = await db.execute(
        select(FailedJob)
        .join(Source, FailedJob.source_id == Source.id)
        .join(Source.notebook)
        .where(Source.notebook.has(user_id=user.id))
        .order_by(FailedJob.created_at.desc())
    )
    jobs = list(result.scalars().all())
    responses = [FailedJobResponse.model_validate(j) for j in jobs]
    return FailedJobListResponse(jobs=responses, total=len(responses))


@router.post(
    "/{job_id}/retry",
    response_model=RetryResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Retry a failed job",
)
async def retry_job(
    job_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> RetryResponse:
    """Retry a failed processing job.

    Re-dispatches the original Celery task and marks the DLQ entry as retried.
    """
    # Verify the job exists and belongs to the user
    result = await db.execute(
        select(FailedJob)
        .join(Source, FailedJob.source_id == Source.id)
        .where(
            FailedJob.id == job_id,
            Source.notebook.has(user_id=user.id),
        )
    )
    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(status_code=404, detail="Failed job not found")
    if job.retried:
        raise HTTPException(status_code=409, detail="Job has already been retried")

    # Mark as retried and re-dispatch
    job.retried = True
    await db.flush()

    from app.worker.tasks.process_source import process_source
    process_source.delay(str(job.source_id))

    return RetryResponse(
        job_id=job.id,
        source_id=job.source_id,
    )
