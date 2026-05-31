"""OpenNotebook — BM25 index builder per notebook.

Builds a ``BM25Okapi`` index from all chunks in a notebook and serialises it
to Redis for fast retrieval.  The index is rebuilt whenever a source is
added or removed from the notebook.
"""

from __future__ import annotations

import logging
import pickle
from typing import Any

from rank_bm25 import BM25Okapi

from app.core.config import get_settings
from app.infrastructure.qdrant.client import get_all_chunks_for_notebook
from app.infrastructure.redis.client import get_sync_redis

logger = logging.getLogger(__name__)

# Redis key pattern for BM25 indices
_BM25_KEY_PREFIX = "bm25:"
# Redis key for the chunk ID mapping
_BM25_DOCS_KEY_PREFIX = "bm25_docs:"


def build_bm25_index(notebook_id: str) -> int:
    """Build (or rebuild) the BM25 index for a notebook.

    Fetches all chunk payloads from Qdrant, tokenises them, builds a
    ``BM25Okapi`` index, and serialises both the index and the chunk ID
    mapping to Redis.

    Args:
        notebook_id: UUID of the notebook to index.

    Returns:
        Number of chunks indexed.
    """
    chunks = get_all_chunks_for_notebook(notebook_id)
    if not chunks:
        logger.info("No chunks found for notebook %s, clearing BM25 index", notebook_id)
        _clear_index(notebook_id)
        return 0

    # Tokenise all chunk texts
    tokenised_corpus = [_tokenise(chunk.get("text", "")) for chunk in chunks]
    chunk_ids = [chunk.get("chunk_id", "") for chunk in chunks]

    # Build the BM25 index
    bm25 = BM25Okapi(tokenised_corpus)

    # Serialise to Redis
    redis_client = get_sync_redis()
    redis_client.set(
        f"{_BM25_KEY_PREFIX}{notebook_id}",
        pickle.dumps(bm25),
    )
    redis_client.set(
        f"{_BM25_DOCS_KEY_PREFIX}{notebook_id}",
        pickle.dumps(chunk_ids),
    )

    logger.info(
        "Built BM25 index for notebook %s: %d chunks",
        notebook_id,
        len(chunks),
    )
    return len(chunks)


def load_bm25_index(notebook_id: str) -> tuple[BM25Okapi | None, list[str]]:
    """Load a previously built BM25 index from Redis.

    Args:
        notebook_id: UUID of the notebook.

    Returns:
        Tuple of (BM25Okapi instance or None, list of chunk IDs).
    """
    redis_client = get_sync_redis()

    bm25_data = redis_client.get(f"{_BM25_KEY_PREFIX}{notebook_id}")
    docs_data = redis_client.get(f"{_BM25_DOCS_KEY_PREFIX}{notebook_id}")

    if bm25_data is None or docs_data is None:
        return None, []

    bm25 = pickle.loads(bm25_data)  # noqa: S301
    chunk_ids = pickle.loads(docs_data)  # noqa: S301

    return bm25, chunk_ids


def _clear_index(notebook_id: str) -> None:
    """Remove the BM25 index for a notebook from Redis."""
    redis_client = get_sync_redis()
    redis_client.delete(f"{_BM25_KEY_PREFIX}{notebook_id}")
    redis_client.delete(f"{_BM25_DOCS_KEY_PREFIX}{notebook_id}")


def _tokenise(text: str) -> list[str]:
    """Simple whitespace + lowercase tokenisation for BM25."""
    return text.lower().split()
