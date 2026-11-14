"""OpenNotebook — Enterprise S3 / Object Store Connector.

Connects to AWS S3 or MinIO buckets to ingest enterprise files (.pdf, .docx, .txt, .md).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from minio import Minio

from app.domain.connectors.base import BaseConnector, ExtractedDocument
from app.domain.connectors.timeutil import ensure_utc

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".txt": "txt",
    ".md": "md",
}


class S3BucketConnector(BaseConnector):
    """Connector for external AWS S3 or MinIO enterprise data buckets."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.bucket_name = config.get("bucket_name", "").strip()
        if not self.bucket_name:
            raise ValueError("bucket_name is required for S3BucketConnector")

        self.endpoint = config.get("endpoint", "s3.amazonaws.com")
        self.access_key = config.get("access_key", "")
        self.secret_key = config.get("secret_key", "")
        self.prefix = config.get("prefix", "").lstrip("/")
        self.secure = bool(config.get("secure", True))
        self.max_files = int(config.get("max_files", 50))

    def _get_client(self) -> Minio:
        return Minio(
            endpoint=self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure,
        )

    def test_connection(self) -> bool:
        """Validate credentials and access to the target bucket."""
        client = self._get_client()
        try:
            exists = client.bucket_exists(self.bucket_name)
            if not exists:
                raise ValueError(
                    f"Bucket {self.bucket_name!r} does not exist or access is forbidden"
                )
            return True
        except Exception as exc:
            logger.error("S3 connectivity test failed for %s: %s", self.bucket_name, exc)
            raise ConnectionError(f"S3 Connection failed: {exc}") from exc

    def sync(self, since: datetime | None = None) -> list[ExtractedDocument]:
        """List and retrieve supported documents from the S3 bucket.

        Args:
            since: Optional watermark; when provided, only objects modified at or
                after this time are returned.
        """
        client = self._get_client()
        since = ensure_utc(since)
        documents: list[ExtractedDocument] = []

        try:
            objects = client.list_objects(self.bucket_name, prefix=self.prefix, recursive=True)
            count = 0

            for obj in objects:
                if count >= self.max_files:
                    break
                if obj.is_dir:
                    continue

                suffix = Path(obj.object_name).suffix.lower()
                if suffix not in _SUPPORTED_EXTENSIONS:
                    continue

                if since is not None and obj.last_modified is not None:
                    last_modified = obj.last_modified
                    if last_modified.tzinfo is None:
                        last_modified = last_modified.replace(tzinfo=UTC)
                    if last_modified < since:
                        continue

                source_type = _SUPPORTED_EXTENSIONS[suffix]
                filename = Path(obj.object_name).name

                # Download file bytes
                response = client.get_object(self.bucket_name, obj.object_name)
                try:
                    file_bytes = response.read()
                finally:
                    response.close()
                    response.release_conn()

                documents.append(
                    ExtractedDocument(
                        title=filename,
                        content=file_bytes,
                        source_type=source_type,
                        url=f"s3://{self.bucket_name}/{obj.object_name}",
                        external_id=obj.etag,
                        last_modified=obj.last_modified,
                        metadata={
                            "bucket": self.bucket_name,
                            "key": obj.object_name,
                            "size_bytes": obj.size,
                        },
                    )
                )
                count += 1

            logger.info(
                "S3BucketConnector synced %d files from s3://%s/%s",
                len(documents),
                self.bucket_name,
                self.prefix,
            )
            return documents

        except Exception as exc:
            logger.error("S3 sync failed for bucket %s: %s", self.bucket_name, exc)
            raise
