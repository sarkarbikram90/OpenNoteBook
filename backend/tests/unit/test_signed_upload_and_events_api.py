"""Lifecycle tests for Signed Upload/Download URLs and GCS Pub/Sub event ingestion."""

from __future__ import annotations

import base64
import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from app.api.v1.schemas.sources import (
    SignedDownloadResponse,
    SignedUploadRequest,
    SignedUploadResponse,
)
from app.infrastructure.db.models import Notebook, Source
from app.infrastructure.pubsub.gcs_events import (
    is_generation_already_processed,
    parse_pubsub_push_envelope,
    parse_raw_object_key,
    record_generation_on_metadata,
)
from app.infrastructure.storage.service import StorageService


def test_signed_url_schemas_and_storage_service_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
):
    """Verify SignedUploadRequest/Response schemas, StorageService signed URLs, and Pub/Sub generation tracking."""
    nb_id = uuid.uuid4()
    src_id = uuid.uuid4()
    req = SignedUploadRequest(
        filename="storage-engine-study.pdf",
        content_type="application/pdf",
        size_bytes=204800,
        sha256="a" * 64,
    )
    assert req.filename == "storage-engine-study.pdf"

    from app.infrastructure.storage import gcs

    monkeypatch.setattr(
        gcs,
        "generate_signed_upload_url",
        lambda object_name, content_type="application/octet-stream", expiration_seconds=None: (
            f"https://storage.googleapis.com/private-bucket/{object_name}?method=PUT&ct={content_type}&ttl={expiration_seconds}"
        ),
    )
    monkeypatch.setattr(
        gcs,
        "generate_signed_download_url",
        lambda object_name, expiration_seconds=None: (
            f"https://storage.googleapis.com/private-bucket/{object_name}?method=GET&ttl={expiration_seconds}"
        ),
    )

    storage = StorageService(provider="gcs", local_path="/tmp/opennotebook-signed-test")
    object_name = f"raw/{nb_id}/{src_id}/{req.filename}"
    put_url = storage.generate_signed_upload_url(object_name, req.content_type, 900)
    get_url = storage.generate_signed_download_url(object_name, 900)

    signed_resp = SignedUploadResponse(
        source_id=src_id,
        object_name=object_name,
        upload_url=put_url,
        content_type=req.content_type,
        expires_in_seconds=900,
        status="UPLOADED",
    )
    assert signed_resp.status == "UPLOADED"
    assert "method=PUT" in signed_resp.upload_url

    dl_resp = SignedDownloadResponse(
        source_id=src_id,
        object_name=object_name,
        download_url=get_url,
        expires_in_seconds=900,
    )
    assert "method=GET" in dl_resp.download_url

    # Simulate GCS OBJECT_FINALIZE notification via Pub/Sub push
    gcs_notification = {
        "bucket": "private-bucket",
        "name": object_name,
        "generation": "1731950000111222",
        "contentType": "application/pdf",
        "size": "204800",
    }
    envelope = {
        "message": {
            "data": base64.b64encode(
                json.dumps(gcs_notification).encode("utf-8")
            ).decode("ascii"),
            "attributes": {
                "eventType": "OBJECT_FINALIZE",
                "bucketId": "private-bucket",
                "objectId": object_name,
                "objectGeneration": "1731950000111222",
            },
            "messageId": "pubsub-msg-1",
        }
    }
    event = parse_pubsub_push_envelope(envelope)
    assert event is not None
    parsed = parse_raw_object_key(event.object_name)
    assert parsed is not None
    assert parsed.source_id == src_id

    meta: dict[str, Any] = {}
    assert is_generation_already_processed("UPLOADED", meta, event.generation) is False
    meta = record_generation_on_metadata(meta, event)
    assert is_generation_already_processed("QUEUED", meta, event.generation) is True


class _FakeScalarResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value


class _FakeAsyncDbSession:
    """In-memory async DB session stub tracking Notebooks and Sources."""

    def __init__(self, notebook: Notebook) -> None:
        self.notebooks: dict[uuid.UUID, Notebook] = {notebook.id: notebook}
        self.sources: dict[uuid.UUID, Source] = {}

    def add(self, obj: Any) -> None:
        if isinstance(obj, Source):
            if getattr(obj, "created_at", None) is None:
                obj.created_at = datetime.now(UTC)
            if getattr(obj, "updated_at", None) is None:
                obj.updated_at = datetime.now(UTC)
            self.sources[obj.id] = obj

    async def flush(self) -> None:
        return None

    async def execute(self, stmt: Any) -> _FakeScalarResult:
        sql_str = str(stmt)
        if "FROM notebooks" in sql_str:
            for nb in self.notebooks.values():
                return _FakeScalarResult(nb)
            return _FakeScalarResult(None)
        if "FROM sources" in sql_str:
            for src in self.sources.values():
                return _FakeScalarResult(src)
            return _FakeScalarResult(None)
        return _FakeScalarResult(None)


@pytest.mark.asyncio
async def test_fastapi_signed_upload_and_pubsub_routes(
    monkeypatch: pytest.MonkeyPatch,
):
    """Exercise FastAPI route handlers when fastapi is installed in the test environment."""
    fastapi = pytest.importorskip("fastapi")
    from app.api.v1 import events as events_api
    from app.api.v1 import sources as sources_api

    user_id = uuid.uuid4()
    nb_id = uuid.uuid4()
    user = SimpleNamespace(id=user_id, email="researcher@example.com")
    notebook = Notebook(id=nb_id, user_id=user_id, name="GCS Study Notebook")
    fake_db = _FakeAsyncDbSession(notebook)

    async def _no_op_audit(**_kwargs: Any) -> None:
        return None

    async def _no_duplicate(_db: Any, _nb_id: Any, _hash: str) -> None:
        return None

    monkeypatch.setattr(sources_api, "record_audit_event", _no_op_audit)
    monkeypatch.setattr(sources_api, "find_source_by_checksum", _no_duplicate)

    fake_storage = SimpleNamespace(
        provider="gcs",
        generate_signed_upload_url=lambda obj_name, content_type, ttl: (
            f"https://storage.googleapis.com/private-bucket/{obj_name}?method=PUT&ct={content_type}&ttl={ttl}"
        ),
        generate_signed_download_url=lambda obj_name, ttl: (
            f"https://storage.googleapis.com/private-bucket/{obj_name}?method=GET&ttl={ttl}"
        ),
        object_exists=lambda _obj_name: True,
    )
    monkeypatch.setattr(
        "app.infrastructure.storage.service.get_storage_service",
        lambda _provider=None: fake_storage,
    )

    dispatched_sources: list[str] = []
    monkeypatch.setattr(
        sources_api,
        "_dispatch_source_task",
        lambda src_id, _bg=None: dispatched_sources.append(str(src_id)),
    )
    monkeypatch.setattr(
        events_api,
        "_dispatch_source_task",
        lambda src_id, _bg=None: dispatched_sources.append(str(src_id)),
    )

    req = SignedUploadRequest(
        filename="storage-engine-study.pdf",
        content_type="application/pdf",
        size_bytes=204800,
        sha256="a" * 64,
    )
    signed_resp = await sources_api.create_signed_upload_url(
        notebook_id=nb_id,
        body=req,
        user=user,  # type: ignore[arg-type]
        db=fake_db,  # type: ignore[arg-type]
    )
    assert signed_resp.status == "UPLOADED"

    gcs_notification = {
        "bucket": "private-bucket",
        "name": signed_resp.object_name,
        "generation": "1731950000111222",
        "contentType": "application/pdf",
        "size": "204800",
    }
    pubsub_envelope = {
        "message": {
            "data": base64.b64encode(
                json.dumps(gcs_notification).encode("utf-8")
            ).decode("ascii"),
            "attributes": {
                "eventType": "OBJECT_FINALIZE",
                "bucketId": "private-bucket",
                "objectId": signed_resp.object_name,
                "objectGeneration": "1731950000111222",
            },
            "messageId": "pubsub-msg-1",
        }
    }

    bg = fastapi.BackgroundTasks()
    event_resp = await events_api.handle_gcs_finalize_event(
        payload=pubsub_envelope,
        db=fake_db,  # type: ignore[arg-type]
        background_tasks=bg,
        token=None,
        authorization=None,
    )
    assert event_resp["status"] == "queued"
    assert dispatched_sources == [str(signed_resp.source_id)]

    dup_resp = await events_api.handle_gcs_finalize_event(
        payload=pubsub_envelope,
        db=fake_db,  # type: ignore[arg-type]
        background_tasks=bg,
        token=None,
        authorization=None,
    )
    assert dup_resp["status"] == "duplicate_ignored"
    assert len(dispatched_sources) == 1
