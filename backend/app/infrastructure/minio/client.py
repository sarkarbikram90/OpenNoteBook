"""OpenNotebook — MinIO object storage client.

Provides a thin wrapper around the ``minio`` SDK for file upload, download,
and deletion.  The client is created as a module-level singleton and the
bucket is lazily ensured on first use.
"""

from __future__ import annotations

import io
import logging
from functools import lru_cache

from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_minio_client() -> Minio:
    """Return a cached singleton MinIO client."""
    settings = get_settings()
    return Minio(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def ensure_bucket() -> None:
    """Create the default bucket if it does not exist."""
    settings = get_settings()
    client = get_minio_client()
    bucket = settings.minio_bucket
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        logger.info("Created MinIO bucket: %s", bucket)
    else:
        logger.debug("MinIO bucket already exists: %s", bucket)


def upload_file(data: bytes, object_name: str, content_type: str = "application/octet-stream") -> str:
    """Upload file bytes to MinIO and return the object name (storage path).

    Args:
        data: Raw file content.
        object_name: The key under which the object is stored (e.g. ``sources/{source_id}/file.pdf``).
        content_type: MIME type for the stored object.

    Returns:
        The ``object_name`` that was stored.
    """
    settings = get_settings()
    client = get_minio_client()
    client.put_object(
        bucket_name=settings.minio_bucket,
        object_name=object_name,
        data=io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    logger.info("Uploaded object: %s (%d bytes)", object_name, len(data))
    return object_name


def download_file(object_name: str) -> bytes:
    """Download a file from MinIO and return its bytes.

    Args:
        object_name: The key of the stored object.

    Returns:
        Raw file content.

    Raises:
        S3Error: If the object does not exist.
    """
    settings = get_settings()
    client = get_minio_client()
    response = client.get_object(
        bucket_name=settings.minio_bucket,
        object_name=object_name,
    )
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def delete_file(object_name: str) -> None:
    """Delete an object from MinIO.

    Args:
        object_name: The key of the stored object.
    """
    settings = get_settings()
    client = get_minio_client()
    try:
        client.remove_object(
            bucket_name=settings.minio_bucket,
            object_name=object_name,
        )
        logger.info("Deleted object: %s", object_name)
    except S3Error:
        logger.warning("Failed to delete object (may not exist): %s", object_name)
