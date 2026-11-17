"""Google Cloud Storage OBJECT_FINALIZE -> Pub/Sub event parser and idempotent handler.

Supports:
1. Standard Google Cloud Pub/Sub HTTP push envelopes wrapping GCS JSON_API_V1
   notifications (base64 ``message.data`` + ``message.attributes``).
2. Direct GCS notification JSON payloads (for local testing and CloudEvents).
3. Idempotency via GCS object ``generation`` so duplicate Pub/Sub deliveries
   never trigger duplicate chunking or vector indexing.
"""

from __future__ import annotations

import base64
import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

from app.core.metrics import pubsub_events_total

logger = logging.getLogger(__name__)

_EXTENSION_TO_SOURCE_TYPE = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".txt": "txt",
    ".md": "md",
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".webp": "image",
    ".tif": "image",
    ".tiff": "image",
}


@dataclass
class GCSFinalizeEvent:
    """Normalized representation of a Cloud Storage OBJECT_FINALIZE notification."""

    bucket: str
    object_name: str
    generation: str
    event_type: str = "OBJECT_FINALIZE"
    content_type: str = "application/octet-stream"
    size_bytes: int = 0
    md5_hash: str | None = None
    message_id: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class ParsedRawObjectKey:
    """Structured components extracted from ``raw/{notebook_id}/{source_id}/{filename}``."""

    notebook_id: uuid.UUID
    source_id: uuid.UUID
    filename: str
    source_type: str


def parse_raw_object_key(object_name: str) -> ParsedRawObjectKey | None:
    """Parse ``raw/{notebook_id}/{source_id}/{filename}`` into UUIDs and source type.

    Returns ``None`` for derived artifacts under ``processed/`` or unrecognized keys.
    """
    clean = object_name.strip().lstrip("/")
    parts = PurePosixPath(clean).parts
    if len(parts) < 4 or parts[0] != "raw":
        return None

    try:
        notebook_id = uuid.UUID(parts[1])
        source_id = uuid.UUID(parts[2])
    except ValueError:
        return None

    filename = parts[-1]
    ext = PurePosixPath(filename).suffix.lower()
    source_type = _EXTENSION_TO_SOURCE_TYPE.get(ext)
    if source_type is None:
        return None

    return ParsedRawObjectKey(
        notebook_id=notebook_id,
        source_id=source_id,
        filename=filename,
        source_type=source_type,
    )


def parse_pubsub_push_envelope(payload: dict[str, Any]) -> GCSFinalizeEvent | None:
    """Extract a ``GCSFinalizeEvent`` from a Pub/Sub push request or direct GCS JSON.

    Args:
        payload: Parsed JSON body from the Pub/Sub push endpoint.

    Returns:
        ``GCSFinalizeEvent`` when the message represents a valid GCS notification,
        or ``None`` if it is a non-finalize event (e.g. ``OBJECT_DELETE``).

    Raises:
        ValueError: If the envelope is malformed.
    """
    if "message" in payload and isinstance(payload["message"], dict):
        msg = payload["message"]
        attributes: dict[str, Any] = msg.get("attributes") or {}
        event_type = str(attributes.get("eventType") or "OBJECT_FINALIZE")
        message_id = str(msg.get("messageId") or msg.get("message_id") or "") or None

        data_obj: dict[str, Any] = {}
        raw_data = msg.get("data")
        if isinstance(raw_data, str) and raw_data.strip():
            try:
                decoded = base64.b64decode(raw_data).decode("utf-8")
                loaded = json.loads(decoded)
                if isinstance(loaded, dict):
                    data_obj = loaded
            except Exception as exc:
                raise ValueError(f"Invalid base64 JSON in Pub/Sub message.data: {exc}") from exc
    else:
        data_obj = payload
        attributes = {}
        event_type = str(payload.get("eventType") or "OBJECT_FINALIZE")
        message_id = str(payload.get("messageId") or "") or None

    if event_type != "OBJECT_FINALIZE":
        pubsub_events_total.labels(event_type=event_type, status="ignored").inc()
        return None

    bucket = str(
        data_obj.get("bucket")
        or attributes.get("bucketId")
        or ""
    ).strip()
    object_name = str(
        data_obj.get("name")
        or attributes.get("objectId")
        or ""
    ).strip()
    generation = str(
        data_obj.get("generation")
        or attributes.get("objectGeneration")
        or "0"
    ).strip()

    if not bucket or not object_name:
        raise ValueError("GCS notification missing required bucket or object name")

    content_type = str(data_obj.get("contentType") or "application/octet-stream")
    raw_size = data_obj.get("size", 0)
    try:
        size_bytes = int(raw_size)
    except (TypeError, ValueError):
        size_bytes = 0

    raw_meta = data_obj.get("metadata")
    metadata = (
        {str(k): str(v) for k, v in raw_meta.items()}
        if isinstance(raw_meta, dict)
        else {}
    )

    return GCSFinalizeEvent(
        bucket=bucket,
        object_name=object_name,
        generation=generation,
        event_type=event_type,
        content_type=content_type,
        size_bytes=size_bytes,
        md5_hash=data_obj.get("md5Hash"),
        message_id=message_id,
        metadata=metadata,
    )


def is_generation_already_processed(
    source_status: str,
    source_metadata: dict[str, Any] | None,
    generation: str,
) -> bool:
    """Return True if this GCS object generation was already ingested or is in flight."""
    meta = source_metadata or {}
    processed = meta.get("processed_generations") or []
    active_states = ("READY", "QUEUED", "EXTRACTING", "CHUNKING", "EMBEDDING")
    if (
        isinstance(processed, list)
        and generation in [str(g) for g in processed]
        and source_status in active_states
    ):
        return True

    last_gen = str(meta.get("last_object_generation") or "")
    if last_gen and last_gen == generation and source_status in (
        "READY",
        "QUEUED",
        "EXTRACTING",
        "CHUNKING",
        "EMBEDDING",
    ):
        return True

    return False


def record_generation_on_metadata(
    source_metadata: dict[str, Any] | None,
    event: GCSFinalizeEvent,
) -> dict[str, Any]:
    """Attach GCS generation and event provenance to source metadata."""
    updated = dict(source_metadata or {})
    existing_gens = [str(g) for g in (updated.get("processed_generations") or [])]
    if event.generation not in existing_gens:
        existing_gens.append(event.generation)

    updated["processed_generations"] = existing_gens[-20:]
    updated["last_object_generation"] = event.generation
    updated["gcs_bucket"] = event.bucket
    if event.size_bytes:
        updated["size_bytes"] = event.size_bytes
    if event.md5_hash:
        updated["md5_hash"] = event.md5_hash
    if event.message_id:
        updated["last_pubsub_message_id"] = event.message_id
    return updated
