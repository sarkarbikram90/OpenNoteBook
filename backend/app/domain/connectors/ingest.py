"""OpenNotebook — connector ingestion planning.

Pure helpers shared by the API sync endpoint and the scheduled sync task, so the
dedup / filename / content-type rules live in one place.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from app.domain.connectors.base import ExtractedDocument


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _to_bytes(content: str | bytes) -> bytes:
    return content if isinstance(content, bytes) else content.encode("utf-8")


def content_type_for(source_type: str) -> str:
    """Return the storage content type for a source type."""
    return "text/plain" if source_type in ("txt", "md", "url") else "application/octet-stream"


def filename_for(document: ExtractedDocument) -> str:
    """Ensure the document title carries the correct extension."""
    suffix = f".{document.source_type}"
    return (
        document.title if document.title.lower().endswith(suffix) else f"{document.title}{suffix}"
    )


@dataclass
class PlannedDocument:
    """A connector document selected for ingestion."""

    document: ExtractedDocument
    content: bytes
    checksum: str
    filename: str
    content_type: str


@dataclass
class IngestPlan:
    """Result of planning a connector sync."""

    to_ingest: list[PlannedDocument] = field(default_factory=list)
    skipped: int = 0


def plan_ingest(
    documents: Iterable[ExtractedDocument],
    existing_checksums: Iterable[str],
    max_documents: int | None = None,
    hash_fn: Callable[[bytes], str] | None = None,
) -> IngestPlan:
    """Select documents to ingest, skipping duplicates already in the notebook.

    Args:
        documents: documents returned by a connector.
        existing_checksums: checksums already stored for the target notebook.
        max_documents: optional cap on how many documents to ingest.
        hash_fn: checksum function (defaults to SHA-256 hexdigest).

    Returns:
        An :class:`IngestPlan` with documents to ingest and a skipped count.
    """
    digest = hash_fn or _sha256
    seen = set(existing_checksums)
    plan = IngestPlan()

    for document in documents:
        if max_documents is not None and len(plan.to_ingest) >= max_documents:
            plan.skipped += 1
            continue

        content = _to_bytes(document.content)
        checksum = digest(content)
        if checksum in seen:
            plan.skipped += 1
            continue

        seen.add(checksum)
        plan.to_ingest.append(
            PlannedDocument(
                document=document,
                content=content,
                checksum=checksum,
                filename=filename_for(document),
                content_type=content_type_for(document.source_type),
            )
        )

    return plan
