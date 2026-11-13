"""Google Cloud Storage adapter for OpenNotebook object storage.

Credentials use Application Default Credentials (ADC). The configured bucket
must be provisioned separately; this module never creates a bucket or changes
its access policy.
"""
from __future__ import annotations

import logging
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


def upload_file(data: bytes, object_name: str, content_type: str = "application/octet-stream",
                metadata: dict[str, Any] | None = None) -> str:
    """Upload an object and attach string-valued provenance metadata."""
    settings = get_settings()
    blob = _get_bucket().blob(object_name)
    if metadata:
        blob.metadata = {str(key): str(value) for key, value in metadata.items()}
    blob.upload_from_string(data, content_type=content_type, timeout=settings.gcs_timeout_seconds)
    logger.info("Uploaded GCS object gs://%s/%s (%d bytes)", settings.gcs_bucket, object_name, len(data))
    return object_name


def download_file(object_name: str) -> bytes:
    """Download an object, translating GCS NotFound into FileNotFoundError."""
    from google.api_core.exceptions import NotFound

    settings = get_settings()
    blob = _get_bucket().blob(object_name)
    try:
        return blob.download_as_bytes(timeout=settings.gcs_timeout_seconds)
    except NotFound as exc:
        raise FileNotFoundError(f"GCS object not found: gs://{settings.gcs_bucket}/{object_name}") from exc


def delete_file(object_name: str) -> None:
    """Delete an object; missing objects are treated as already deleted."""
    from google.api_core.exceptions import NotFound

    settings = get_settings()
    blob = _get_bucket().blob(object_name)
    try:
        blob.delete(timeout=settings.gcs_timeout_seconds)
        logger.info("Deleted GCS object gs://%s/%s", settings.gcs_bucket, object_name)
    except NotFound:
        logger.info("GCS object already absent: gs://%s/%s", settings.gcs_bucket, object_name)


def object_exists(object_name: str) -> bool:
    """Return whether the object currently exists in the configured bucket."""
    settings = get_settings()
    blob = _get_bucket().blob(object_name)
    return bool(blob.exists(timeout=settings.gcs_timeout_seconds))
