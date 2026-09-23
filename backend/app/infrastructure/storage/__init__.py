"""OpenNotebook — Storage and Data Lake service module."""

from app.infrastructure.storage.service import StorageService, get_storage_service

__all__ = ["StorageService", "get_storage_service"]
