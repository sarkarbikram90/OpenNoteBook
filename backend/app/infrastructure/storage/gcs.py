"""Google Cloud Storage adapter for OpenNotebook object storage.

Credentials use Application Default Credentials (ADC). The configured bucket
must be provisioned separately; this module never creates a bucket or changes
its access policy.
"""
from __future__ import annotations

import logging
import time
from functools import lru_cache
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_gcs_client() -> Any:
    """Return a cached GCS client using Application Default Credentials."""
    from google.cloud import storage

    project_id = get_settings().gcs_project_id.strip()
    return storage.Client(project=project_id or None)


def _get_bucket() -> Any:
    """Resolve the configured private bucket or fail with an actionable error."""
    bucket_name = get_settings().gcs_bucket.strip()
    if not bucket_name:
        raise RuntimeError("GCS_BUCKET must be configured when STORAGE_PROVIDER=gcs")
    return get_gcs_client().bucket(bucket_name)


def _record_operation(
    operation: str,
    started_at: float,
    status: str,
    byte_count: int = 0,
) -> None:
    """Record low-cardinality storage telemetry without masking the GCS result."""
    try:
        from app.core.metrics import (
            storage_bytes_total,
            storage_operation_duration,
            storage_operations_total,
        )

        storage_operations_total.labels(
            provider="gcs", operation=operation, status=status
        ).inc()
        storage_operation_duration.labels(
            provider="gcs", operation=operation
        ).observe(time.perf_counter() - started_at)
        if byte_count > 0:
            storage_bytes_total.labels(
                provider="gcs", operation=operation
            ).inc(byte_count)
    except Exception:
        logger.debug("Could not record GCS %s metrics", operation, exc_info=True)


def upload_file(
    data: bytes,
    object_name: str,
    content_type: str = "application/octet-stream",
    metadata: dict[str, Any] | None = None,
) -> str:
    """Upload an object and attach string-valued provenance metadata."""
    settings = get_settings()
    blob = _get_bucket().blob(object_name)
    if metadata:
        blob.metadata = {str(key): str(value) for key, value in metadata.items()}

    started_at = time.perf_counter()
    try:
        blob.upload_from_string(
            data,
            content_type=content_type,
            timeout=settings.gcs_timeout_seconds,
        )
    except Exception:
        _record_operation("upload", started_at, "error")
        raise

    _record_operation("upload", started_at, "success", len(data))
    logger.info(
        "Uploaded GCS object gs://%s/%s (%d bytes)",
        settings.gcs_bucket,
        object_name,
        len(data),
    )
    return object_name


def download_file(object_name: str) -> bytes:
    """Download an object, translating GCS NotFound into FileNotFoundError."""
    from google.api_core.exceptions import NotFound

    settings = get_settings()
    blob = _get_bucket().blob(object_name)
    started_at = time.perf_counter()
    try:
        data = blob.download_as_bytes(timeout=settings.gcs_timeout_seconds)
    except NotFound as exc:
        _record_operation("download", started_at, "error")
        raise FileNotFoundError(
            f"GCS object not found: gs://{settings.gcs_bucket}/{object_name}"
        ) from exc
    except Exception:
        _record_operation("download", started_at, "error")
        raise

    _record_operation("download", started_at, "success", len(data))
    return bytes(data)


def delete_file(object_name: str) -> None:
    """Delete an object; missing objects are treated as already deleted."""
    from google.api_core.exceptions import NotFound

    settings = get_settings()
    blob = _get_bucket().blob(object_name)
    started_at = time.perf_counter()
    try:
        blob.delete(timeout=settings.gcs_timeout_seconds)
    except NotFound:
        _record_operation("delete", started_at, "success")
        logger.info(
            "GCS object already absent: gs://%s/%s",
            settings.gcs_bucket,
            object_name,
        )
        return
    except Exception:
        _record_operation("delete", started_at, "error")
        raise

    _record_operation("delete", started_at, "success")
    logger.info("Deleted GCS object gs://%s/%s", settings.gcs_bucket, object_name)


def object_exists(object_name: str) -> bool:
    """Return whether the object currently exists in the configured bucket."""
    settings = get_settings()
    blob = _get_bucket().blob(object_name)
    started_at = time.perf_counter()
    try:
        exists = bool(blob.exists(timeout=settings.gcs_timeout_seconds))
    except Exception:
        _record_operation("exists", started_at, "error")
        raise

    _record_operation("exists", started_at, "success")
    return exists
