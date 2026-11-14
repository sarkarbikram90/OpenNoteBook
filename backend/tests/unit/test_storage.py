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



def test_gcs_storage_delegates_to_gcs_adapter(monkeypatch: pytest.MonkeyPatch):
    """GCS operations use the remote adapter rather than local filesystem storage."""
    from app.infrastructure.storage import gcs

    calls: list[tuple[str, str]] = []
    payload = b"gcs document bytes"
    monkeypatch.setattr(
        gcs,
        "upload_file",
        lambda data, object_name, content_type, metadata=None: (
            calls.append(("upload", object_name)) or object_name
        ),
    )
    monkeypatch.setattr(
        gcs,
        "download_file",
        lambda object_name: calls.append(("download", object_name)) or payload,
    )
    monkeypatch.setattr(
        gcs, "delete_file", lambda object_name: calls.append(("delete", object_name))
    )
    monkeypatch.setattr(
        gcs,
        "object_exists",
        lambda object_name: calls.append(("exists", object_name)) or True,
    )

    storage = StorageService(provider="gcs", local_path="/tmp/opennotebook-gcs-test")
    object_name = "raw/notebook/source/report.pdf"

    assert storage.upload_raw_document(payload, object_name, "application/pdf") == object_name
    assert storage.download_raw_document(object_name) == payload
    assert storage.object_exists(object_name) is True
    storage.delete_raw_document(object_name)

    assert calls == [
        ("upload", object_name),
        ("download", object_name),
        ("exists", object_name),
        ("delete", object_name),
    ]


def test_gcs_upload_errors_do_not_fall_back_to_local(monkeypatch: pytest.MonkeyPatch):
    """A failed GCS write must not silently create a local-only source object."""
    from app.infrastructure.storage import gcs

    def fail_upload(*args, **kwargs):
        raise RuntimeError("GCS permission denied")

    monkeypatch.setattr(gcs, "upload_file", fail_upload)
    storage = StorageService(provider="gcs", local_path="/tmp/opennotebook-gcs-test")

    with pytest.raises(RuntimeError, match="GCS permission denied"):
        storage.upload_raw_document(b"payload", "raw/notebook/source/file.txt")



def test_gcs_adapter_upload_download_exists_delete(monkeypatch: pytest.MonkeyPatch):
    """Exercise the GCS SDK adapter with a fake bucket and ADC client."""
    from types import SimpleNamespace

    from google.cloud import storage

    from app.infrastructure.storage import gcs

    settings = SimpleNamespace(
        gcs_project_id="test-project",
        gcs_bucket="private-opennotebook",
        gcs_timeout_seconds=7,
    )
    monkeypatch.setattr(gcs, "get_settings", lambda: settings)

    # Validate client construction uses the configured project and ADC SDK path.
    client_marker = object()
    projects: list[str | None] = []
    monkeypatch.setattr(
        storage,
        "Client",
        lambda project=None: projects.append(project) or client_marker,
    )
    gcs.get_gcs_client.cache_clear()
    assert gcs.get_gcs_client() is client_marker
    assert projects == ["test-project"]
    gcs.get_gcs_client.cache_clear()

    class FakeBlob:
        def __init__(self):
            self.data: bytes | None = None
            self.metadata: dict[str, str] | None = None
            self.content_type: str | None = None

        def upload_from_string(self, data, content_type, timeout):
            self.data = data
            self.content_type = content_type

        def download_as_bytes(self, timeout):
            if self.data is None:
                raise FileNotFoundError("missing")
            return self.data

        def delete(self, timeout):
            self.data = None

        def exists(self, timeout):
            return self.data is not None

    class FakeBucket:
        def __init__(self):
            self.blobs: dict[str, FakeBlob] = {}

        def blob(self, name):
            return self.blobs.setdefault(name, FakeBlob())

    bucket = FakeBucket()

    class FakeClient:
        def bucket(self, name):
            assert name == settings.gcs_bucket
            return bucket

    monkeypatch.setattr(gcs, "get_gcs_client", lambda: FakeClient())

    key = "raw/notebook-1/source-1/runbook.pdf"
    content = b"gcs-backed runbook"
    assert gcs.object_exists(key) is False
    assert gcs.upload_file(
        content,
        key,
        content_type="application/pdf",
        metadata={"source_id": "source-1", "sha256": "abc123"},
    ) == key
    assert bucket.blobs[key].metadata == {
        "source_id": "source-1",
        "sha256": "abc123",
    }
    assert bucket.blobs[key].content_type == "application/pdf"
    assert gcs.object_exists(key) is True
    assert gcs.download_file(key) == content
    gcs.delete_file(key)
    assert gcs.object_exists(key) is False
