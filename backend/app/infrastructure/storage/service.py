"""OpenNotebook — Central Data Lake and Object Storage service.

Provides a unified storage interface supporting:
1. Google Cloud Storage (GCS)
2. S3 / MinIO Object Storage
3. Local filesystem fallback for dev/testing
4. SHA-256 cryptographic provenance hashing
"""

from __future__ import annotations

import hashlib
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)


_minio_checked_at: float = 0.0
_minio_reachable: bool | None = None


def _probe_tcp_endpoint(endpoint: str, timeout: float = 0.3) -> bool:
    """Fast socket probe to check if a TCP service endpoint is open."""
    import socket

    try:
        clean = (
            endpoint.replace("http://", "")
            .replace("https://", "")
            .replace("redis://", "")
            .replace("rediss://", "")
            .split("/")[0]
        )
        if "@" in clean:
            clean = clean.split("@", 1)[1]
        if ":" in clean:
            host, port_str = clean.split(":", 1)
            port = int(port_str)
        else:
            host = clean
            port = 443 if "https://" in endpoint else 80
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


class StorageService:
    """Unified Data Lake Object Storage service."""

    def __init__(self, provider: str | None = None, local_path: str | None = None) -> None:
        self.settings = get_settings()
        self._provider = (provider or self.settings.storage_provider).lower()
        self.local_root = self._resolve_local_root(local_path or self.settings.local_storage_path)

    @property
    def provider(self) -> str:
        """Return the effective provider, falling back locally if MinIO/S3 is unreachable."""
        if self._provider in ("minio", "s3") and not self._is_minio_available():
            return "local"
        return self._provider

    @provider.setter
    def provider(self, val: str) -> None:
        self._provider = val.lower()

    def _is_minio_available(self) -> bool:
        """Check if MinIO/S3 endpoint is alive, caching for 60 seconds."""
        global _minio_checked_at, _minio_reachable
        import time

        now = time.monotonic()
        if _minio_reachable is not None and (now - _minio_checked_at < 60.0):
            return _minio_reachable

        _minio_reachable = _probe_tcp_endpoint(self.settings.minio_endpoint, timeout=0.3)
        _minio_checked_at = now
        if not _minio_reachable:
            logger.info(
                "MinIO endpoint %s is unreachable; auto-routing storage to local filesystem: %s",
                self.settings.minio_endpoint,
                self.local_root,
            )
        return _minio_reachable

    @staticmethod
    def _resolve_local_root(path_str: str) -> Path:
        """Return a writable local root, falling back to a temp dir if needed.

        Serverless platforms (e.g. Cloud Run) run as a non-root user with a
        read-only app dir; the configured path (often relative) may not be
        writable. Falling back keeps local-storage mode functional.
        """
        import tempfile

        primary = Path(path_str)
        try:
            primary.mkdir(parents=True, exist_ok=True)
            probe = primary / ".write_test"
            probe.write_bytes(b"")
            probe.unlink()
            return primary
        except OSError as exc:
            fallback = Path(tempfile.gettempdir()) / "opennotebook-lake"
            fallback.mkdir(parents=True, exist_ok=True)
            logger.warning(
                "Local storage path %s is not writable (%s); using %s", primary, exc, fallback
            )
            return fallback

    @staticmethod
    def calculate_file_hash(data: bytes) -> str:
        """Compute the SHA-256 checksum of raw file bytes for provenance."""
        return hashlib.sha256(data).hexdigest()

    def upload_raw_document(
        self,
        data: bytes,
        object_name: str,
        content_type: str = "application/octet-stream",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Upload raw document bytes to the data lake.

        Args:
            data: File bytes.
            object_name: Storage key/path. Build keys with
                ``app.infrastructure.storage.paths`` (raw_key / processed_key).
            content_type: MIME type.
            metadata: Optional dictionary of provenance metadata.

        Returns:
            The normalized object name where content was stored.
        """
        # Normalize key
        clean_object_name = object_name.lstrip("/")

        if self.provider == "gcs":
            # GCS is authoritative when selected: propagate failures rather than
            # silently writing to ephemeral local disk.
            from app.infrastructure.storage import gcs as gcs_storage

            return gcs_storage.upload_file(
                data,
                clean_object_name,
                content_type=content_type,
                metadata=metadata,
            )

        if self.provider in ("minio", "s3"):
            try:
                from app.infrastructure.minio import client as minio_client

                minio_client.ensure_bucket()
                return minio_client.upload_file(data, clean_object_name, content_type=content_type)
            except Exception as exc:
                global _minio_reachable
                _minio_reachable = False
                logger.warning(
                    "MinIO upload failed (%s). Falling back to local lake storage: %s",
                    exc,
                    clean_object_name,
                )
                # Fallback to local
                return self._upload_local(data, clean_object_name)

        return self._upload_local(data, clean_object_name)

    def upload_artifact(
        self,
        data: bytes,
        object_name: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Store a processed/derived artifact (same backend as raw documents)."""
        return self.upload_raw_document(data, object_name, content_type=content_type)

    def download_raw_document(self, object_name: str) -> bytes:
        """Retrieve raw file content from the data lake.

        Args:
            object_name: Storage key/path.

        Returns:
            Raw file bytes.
        """
        clean_object_name = object_name.lstrip("/")

        if self.provider == "gcs":
            from app.infrastructure.storage.gcs import download_file
            return download_file(clean_object_name)

        if self.provider in ("minio", "s3"):
            try:
                from app.infrastructure.minio.client import download_file

                return download_file(clean_object_name)
            except Exception as exc:
                global _minio_reachable
                _minio_reachable = False
                logger.warning(
                    "MinIO download failed (%s). Checking local lake storage: %s",
                    exc,
                    clean_object_name,
                )
                return self._download_local(clean_object_name)

        return self._download_local(clean_object_name)

    def delete_raw_document(self, object_name: str) -> None:
        """Delete an object from the data lake.

        Args:
            object_name: Storage key/path.
        """
        clean_object_name = object_name.lstrip("/")

        if self.provider == "gcs":
            from app.infrastructure.storage.gcs import delete_file
            delete_file(clean_object_name)
            return

        if self.provider in ("minio", "s3"):
            try:
                from app.infrastructure.minio.client import delete_file

                delete_file(clean_object_name)
                return
            except Exception as exc:
                global _minio_reachable
                _minio_reachable = False
                logger.warning(
                    "MinIO delete failed (%s). Trying local deletion: %s", exc, clean_object_name
                )

        self._delete_local(clean_object_name)

    def object_exists(self, object_name: str) -> bool:
        """Check whether an object exists in the lake."""
        clean_object_name = object_name.lstrip("/")
        if self.provider == "gcs":
            from app.infrastructure.storage.gcs import object_exists
            return object_exists(clean_object_name)

        if self.provider in ("minio", "s3"):
            try:
                from app.infrastructure.minio.client import get_minio_client

                client = get_minio_client()
                client.stat_object(self.settings.minio_bucket, clean_object_name)
                return True
            except Exception as exc:
                logger.debug(
                    "MinIO object existence check failed for %s: %s",
                    clean_object_name,
                    exc,
                )
        target_path = self.local_root / clean_object_name
        return target_path.is_file()

    def _upload_local(self, data: bytes, object_name: str) -> str:
        target_path = self.local_root / object_name
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(data)
        logger.info("Stored file locally at %s (%d bytes)", target_path, len(data))
        return object_name

    def _download_local(self, object_name: str) -> bytes:
        target_path = self.local_root / object_name
        if not target_path.is_file():
            raise FileNotFoundError(f"Local storage object not found: {target_path}")
        return target_path.read_bytes()

    def _delete_local(self, object_name: str) -> None:
        target_path = self.local_root / object_name
        if target_path.is_file():
            target_path.unlink()
            logger.info("Deleted local storage file: %s", target_path)


@lru_cache(maxsize=8)
def get_storage_service(provider: str | None = None) -> StorageService:
    """Return a cached storage service, optionally pinned to a source's provider.

    Provider pinning keeps older local/MinIO documents accessible after the
    default provider is changed for new uploads.
    """
    return StorageService(provider=provider)
