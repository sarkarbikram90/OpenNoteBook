"""OpenNotebook — Canonical data-lake key layout.

Single source of truth for object keys written to the lake (MinIO/S3 or local
fallback). Keeping this in one module prevents the drift that previously existed
between callers (e.g. ``sources/{id}/...`` vs ``sources/{notebook}/...``).

Layout:
    raw/{notebook_id}/{source_id}/{filename}     raw uploaded/fetched document
    processed/{source_id}/{artifact}             derived artifacts (text, chunks, metadata)
"""

from __future__ import annotations

import re

RAW_PREFIX = "raw"
PROCESSED_PREFIX = "processed"

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(filename: str) -> str:
    """Reduce a filename to a safe, path-separator-free object component."""
    name = filename.replace("\\", "/").split("/")[-1].strip()
    name = _UNSAFE.sub("_", name)
    name = name.lstrip(".") or "file"
    return name[:200]


def raw_key(notebook_id: str, source_id: str, filename: str) -> str:
    """Key for a raw source document: raw/{notebook_id}/{source_id}/{filename}."""
    return f"{RAW_PREFIX}/{notebook_id}/{source_id}/{sanitize_filename(filename)}"


def processed_key(source_id: str, artifact: str) -> str:
    """Key for a derived artifact: processed/{source_id}/{artifact}."""
    return f"{PROCESSED_PREFIX}/{source_id}/{sanitize_filename(artifact)}"


def processed_document_key(source_id: str) -> str:
    """Key for the redacted extracted text artifact."""
    return processed_key(source_id, "document.txt")


def processed_metadata_key(source_id: str) -> str:
    """Key for the processed-side metadata artifact."""
    return processed_key(source_id, "metadata.json")


def is_processed_key(key: str) -> bool:
    """Return True if a lake key is a processed artifact."""
    return key.startswith(f"{PROCESSED_PREFIX}/")


def is_raw_key(key: str) -> bool:
    """Return True if a lake key is a raw document."""
    return key.startswith(f"{RAW_PREFIX}/")
