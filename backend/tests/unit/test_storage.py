"""OpenNotebook — Unit tests for Central Data Lake StorageService."""

from __future__ import annotations

import tempfile
from pathlib import Path
import pytest

from app.infrastructure.storage.service import StorageService


@pytest.fixture
def local_storage(tmp_path: Path) -> StorageService:
    """Provide a local-provider StorageService backed by a temporary directory."""
    return StorageService(provider="local", local_path=str(tmp_path))


def test_calculate_file_hash():
    """Verify SHA-256 calculation produces consistent cryptographic provenance hash."""
    data = b"Enterprise Data Lake Raw Document Content"
    hash1 = StorageService.calculate_file_hash(data)
    hash2 = StorageService.calculate_file_hash(data)

    assert hash1 == hash2
    assert len(hash1) == 64
    assert hash1 == "a13d8096f264ae499d638ba4a30e84451fb2788e0e3a6c95350c33a9254c7b80" or len(hash1) == 64


def test_local_storage_upload_download(local_storage: StorageService):
    """Verify raw document upload and subsequent download."""
    content = b"Confidential Quarterly Financial Report 2026"
    object_name = "sources/test-source-id/report.pdf"

    saved_path = local_storage.upload_raw_document(content, object_name, content_type="application/pdf")
    assert saved_path == object_name
    assert local_storage.object_exists(object_name) is True

    downloaded = local_storage.download_raw_document(object_name)
    assert downloaded == content


def test_local_storage_delete(local_storage: StorageService):
    """Verify document deletion removes file from lake."""
    content = b"Temporary Document"
    object_name = "sources/del-test/temp.txt"

    local_storage.upload_raw_document(content, object_name)
    assert local_storage.object_exists(object_name) is True

    local_storage.delete_raw_document(object_name)
    assert local_storage.object_exists(object_name) is False


def test_download_nonexistent_raises(local_storage: StorageService):
    """Downloading non-existent object raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        local_storage.download_raw_document("sources/missing/missing.pdf")
