"""OpenNotebook — BGE-small-en-v1.5 embedding generator.

Uses ``sentence-transformers`` for local inference with configurable batch
size (default 64).  The model is loaded lazily as a module-level singleton
to avoid reloading on every task invocation.
"""

from __future__ import annotations

import logging
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


def embed_texts(texts: list[str], batch_size: int | None = None) -> list[list[float]]:
    """Generate embeddings for a list of texts using BGE-small-en-v1.5.

    BGE models recommend prepending an instruction prefix for retrieval.
    This function automatically adds the prefix.

    Args:
        texts: List of text strings to embed.
        batch_size: Number of texts to process per batch.  Defaults to the
            configured ``embedding_batch_size`` (64).

    Returns:
        List of 384-dimensional embedding vectors (one per input text).
    """
    if not texts:
        return []

    settings = get_settings()
    if batch_size is None:
        batch_size = settings.embedding_batch_size

    model = _get_model()

    # BGE instruction prefix for retrieval tasks
    prefixed = [f"Represent this sentence: {t}" for t in texts]

    logger.info("Embedding %d texts in batches of %d", len(texts), batch_size)

    embeddings = model.encode(
        prefixed,
        batch_size=batch_size,
        show_progress_bar=False,
        normalize_embeddings=True,
    )

    # Convert numpy arrays to plain lists
    result = [emb.tolist() for emb in embeddings]

    logger.info("Generated %d embeddings (dim=%d)", len(result), len(result[0]) if result else 0)
    return result
