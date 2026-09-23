"""OpenNotebook — BGE-small-en-v1.5 embedding generator.

Uses ``sentence-transformers`` for local inference with configurable batch
size (default 64).  The model is loaded lazily as a module-level singleton
to avoid reloading on every task invocation.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ── Lazy Model Singleton ────────────────────────────────────────────────────

_model: Any = None


def _get_model() -> Any:
    """Load the sentence-transformer model on first use."""
    global _model  # noqa: PLW0603
    if _model is None:
        from sentence_transformers import SentenceTransformer

        settings = get_settings()
        logger.info("Loading embedding model: %s", settings.embedding_model)
        _model = SentenceTransformer(settings.embedding_model)
        logger.info("Embedding model loaded successfully")
    return _model


# ── Public API ──────────────────────────────────────────────────────────────


def embed_texts(
    texts: list[str],
    batch_size: int | None = None,
    is_query: bool = False,
) -> list[list[float]]:
    """Generate embeddings for a list of texts using BGE-small-en-v1.5.

    BGE models recommend prepending an instruction prefix for query retrieval,
    while passage/document chunks should be embedded without instruction prefix.

    Args:
        texts: List of text strings to embed.
        batch_size: Number of texts to process per batch. Defaults to the
            configured ``embedding_batch_size`` (64).
        is_query: Whether these texts are search queries (gets instruction prefix)
            or document passages (no prefix).

    Returns:
        List of 384-dimensional embedding vectors (one per input text).
    """
    if not texts:
        return []

    settings = get_settings()
    if batch_size is None:
        batch_size = settings.embedding_batch_size

    model = _get_model()

    # Apply instruction prefix ONLY to search queries per BGE specification
    if is_query:
        input_texts = [f"Represent this sentence: {t}" for t in texts]
    else:
        input_texts = texts

    logger.info("Embedding %d texts (is_query=%s) in batches of %d", len(texts), is_query, batch_size)

    start_time = time.perf_counter()
    embeddings = model.encode(
        input_texts,
        batch_size=batch_size,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    duration = time.perf_counter() - start_time

    # Record embedding duration metric
    from app.core.metrics import embedding_duration
    embedding_duration.labels(
        batch_size=batch_size,
        model=settings.embedding_model,
    ).observe(duration)

    # Convert numpy arrays to plain lists
    result = [emb.tolist() for emb in embeddings]

    logger.info("Generated %d embeddings (dim=%d)", len(result), len(result[0]) if result else 0)
    return result
