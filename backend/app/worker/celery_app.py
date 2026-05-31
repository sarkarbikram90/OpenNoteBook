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

# Autodiscover tasks in the tasks package
celery_app.autodiscover_tasks(["app.worker.tasks"])
