"""OpenNotebook — Enterprise Data Connectors module."""

from app.domain.connectors.base import BaseConnector, ExtractedDocument, SyncResult
from app.domain.connectors.local_fileshare import LocalFileShareConnector
from app.domain.connectors.s3_connector import S3BucketConnector
from app.domain.connectors.web import WebConnector

__all__ = [
    "BaseConnector",
    "ExtractedDocument",
    "LocalFileShareConnector",
    "S3BucketConnector",
    "SyncResult",
    "WebConnector",
]
