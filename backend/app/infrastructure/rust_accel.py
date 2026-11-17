"""OpenNotebook — Optional Rust PyO3 native extension bridge (`opennotebook_core`).

Automatically uses the compiled Rust extension when installed (via `maturin` in
Docker or local builds) and falls back cleanly to pure Python when the native
wheel is not present.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    import opennotebook_core as _rust_core
except ImportError:
    _rust_core = None


def is_rust_available() -> bool:
    """Return True if the compiled `opennotebook_core` PyO3 extension is loaded."""
    return _rust_core is not None


def rust_scrub_pii(
    text: str, strategy: str = "redact"
) -> tuple[str, dict[str, int], int] | None:
    """Run the linear-time Rust DFA PII scrubber if available."""
    if _rust_core is None:
        return None
    cleaned, entities, total = _rust_core.scrub_pii(text, strategy)
    return str(cleaned), {str(k): int(v) for k, v in entities.items()}, int(total)


def rust_chunk_pages(
    source_id: str,
    notebook_id: str,
    embedding_model: str,
    pages: list[tuple[int | None, str, str | None]],
    target_tokens: int = 800,
    overlap_tokens: int = 100,
    min_tokens: int = 150,
) -> list[dict[str, Any]] | None:
    """Run the parallel UAX#29 Rust semantic chunker if available."""
    if _rust_core is None:
        return None
    return list(
        _rust_core.chunk_pages(
            source_id,
            notebook_id,
            embedding_model,
            pages,
            target_tokens,
            overlap_tokens,
            min_tokens,
        )
    )


def rust_build_bm25_index_json(
    chunk_ids: list[str], texts: list[str]
) -> str | None:
    """Build a serialized pre-computed BM25 inverted index in Rust if available."""
    if _rust_core is None:
        return None
    return str(_rust_core.build_bm25_index_json(chunk_ids, texts))


def rust_score_bm25_index_json(
    index_json: str, query: str, top_k: int = 20
) -> list[tuple[str, float]] | None:
    """Score a query against a serialized Rust BM25 inverted index if available."""
    if _rust_core is None:
        return None
    scored = _rust_core.score_bm25_index_json(index_json, query, top_k)
    return [(str(cid), float(score)) for cid, score in scored]
