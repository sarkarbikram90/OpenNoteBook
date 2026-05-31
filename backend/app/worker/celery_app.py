"""OpenNotebook — Celery application configuration.

Creates the Celery app with Redis broker and result backend.
Task autodiscovery pulls from ``app.worker.tasks``.
"""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "opennotebook",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    # Serialisation
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task behaviour
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,

    # Result expiry (24 hours)
    result_expires=86400,

    # Task routes — keep source processing on dedicated queue
    task_routes={
        "app.worker.tasks.process_source.*": {"queue": "processing"},
        "app.worker.tasks.*": {"queue": "default"},
    },

    # Default retry policy
    task_default_retry_delay=30,
    task_max_retries=3,
)

# ── Celery Instrumentation & Prometheus Signals ─────────────────────────────

import time
from celery.signals import task_failure, task_postrun, task_prerun, worker_process_init
from opentelemetry.instrumentation.celery import CeleryInstrumentor

@worker_process_init.connect
def init_celery_worker(**kwargs: Any) -> None:
    """Initialize structured logging and OpenTelemetry inside worker processes."""
    from app.core.logging import init_tracing, setup_logging
    setup_logging()
    init_tracing("worker")
    CeleryInstrumentor().instrument()

# Keep track of task execution start times
_task_start_times: dict[str, float] = {}

@task_prerun.connect
def on_task_prerun(task_id: str, task: Any, **kwargs: Any) -> None:
    """Record starting timestamp of the celery task."""
    _task_start_times[task_id] = time.perf_counter()

@task_postrun.connect
def on_task_postrun(task_id: str, task: Any, **kwargs: Any) -> None:
    """Measure task execution time and record in Prometheus histogram."""
    start_time = _task_start_times.pop(task_id, None)
    if start_time is not None:
        duration = time.perf_counter() - start_time
        from app.core.metrics import job_duration
        job_duration.labels(task=task.name).observe(duration)

@task_failure.connect
def on_task_failure(task_id: str, exception: Exception, traceback: Any, sender: Any, **kwargs: Any) -> None:
    """Record task failure event in Prometheus counter."""
    from app.core.metrics import job_failures_total
    job_failures_total.labels(task=sender.name).inc()

# Autodiscover tasks in the tasks package
celery_app.autodiscover_tasks(["app.worker.tasks"])
