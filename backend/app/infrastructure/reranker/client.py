"""OpenNotebook — BGE cross-encoder reranker.

Loads ``BAAI/bge-reranker-base`` lazily as a singleton and provides a
``rerank()`` function that scores (query, passage) pairs and returns
the top-k results sorted by relevance.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ── Lazy Model Singleton ────────────────────────────────────────────────────

_reranker: Any = None


def _get_reranker() -> Any:
    """Load the cross-encoder reranker model on first use."""
    global _reranker  # noqa: PLW0603
    if _reranker is None:
        from sentence_transformers import CrossEncoder

        settings = get_settings()
        logger.info("Loading reranker model: %s", settings.reranker_model)
        _reranker = CrossEncoder(settings.reranker_model)
        logger.info("Reranker model loaded successfully")
    return _reranker


# ── Data Transfer Objects ───────────────────────────────────────────────────


@dataclass
class RerankResult:
    """A chunk with its reranker relevance score."""

    chunk: dict[str, Any]
    score: float


# ── Public API ──────────────────────────────────────────────────────────────


def rerank(
    query: str,
    chunks: list[dict[str, Any]],
    top_k: int | None = None,
) -> list[RerankResult]:
    """Rerank chunks using the BGE cross-encoder.

    Scores each (query, chunk_text) pair and returns the top-k results
    sorted by descending relevance score.

    Args:
        query: The user's search query.
        chunks: List of chunk payload dicts (must contain a ``text`` key).
        top_k: Number of top results to return.  Defaults to
            ``settings.rerank_top_k`` (10).

    Returns:
        Sorted list of ``RerankResult`` objects (highest score first).
    """
    if not chunks:
        return []

    settings = get_settings()
    if top_k is None:
        top_k = settings.rerank_top_k

    model = _get_reranker()

    # Build (query, passage) pairs for the cross-encoder
    pairs = [(query, chunk.get("text", "")) for chunk in chunks]

    logger.info("Reranking %d chunks (top_k=%d)", len(pairs), top_k)

    scores = model.predict(pairs, show_progress_bar=False)

    # Pair scores with chunks and sort descending
    scored = [
        RerankResult(chunk=chunk, score=float(score))
        for chunk, score in zip(chunks, scores)
    ]
    scored.sort(key=lambda r: r.score, reverse=True)

    results = scored[:top_k]
    logger.info(
        "Reranking complete: top score=%.4f, bottom score=%.4f",
        results[0].score if results else 0.0,
        results[-1].score if results else 0.0,
    )
    return results
