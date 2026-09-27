"""OpenNotebook — BM25 index builder per notebook.

Builds a ``BM25Okapi`` index from all chunks in a notebook and serialises it
to Redis for fast retrieval.  The index is rebuilt whenever a source is
added or removed from the notebook.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from rank_bm25 import BM25Okapi

from app.core.config import get_settings
from app.infrastructure.qdrant.client import get_all_chunks_for_notebook
from app.infrastructure.redis.client import get_sync_redis

logger = logging.getLogger(__name__)

# Redis key pattern for BM25 corpus
_BM25_KEY_PREFIX = "bm25_corpus:"
# Redis key for the chunk ID mapping
_BM25_DOCS_KEY_PREFIX = "bm25_docs:"


def build_bm25_index(notebook_id: str) -> int:
    """Build (or rebuild) the BM25 index for a notebook.

    Fetches all chunk payloads from Qdrant, tokenises them, builds a
    ``BM25Okapi`` index, and serialises the corpus to Redis using safe JSON.

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

    # Serialise corpus and chunk_ids safely via JSON
    try:
        from app.infrastructure.redis.client import is_redis_available

        if not is_redis_available():
            logger.info("Redis not available; skipping BM25 cache for notebook %s", notebook_id)
            return len(chunks)

        redis_client = get_sync_redis()
        redis_client.set(
            f"{_BM25_KEY_PREFIX}{notebook_id}",
            json.dumps(tokenised_corpus),
        )
        redis_client.set(
            f"{_BM25_DOCS_KEY_PREFIX}{notebook_id}",
            json.dumps(chunk_ids),
        )
    except Exception as exc:
        logger.warning("Failed to store BM25 index in Redis: %s", exc)

    logger.info(
        "Built BM25 index for notebook %s: %d chunks",
        notebook_id,
        len(chunks),
    )
    return len(chunks)


def load_bm25_index(notebook_id: str) -> tuple[BM25Okapi | None, list[str]]:
    """Load a previously built BM25 index from Redis safely.

    Args:
        notebook_id: UUID of the notebook.

    Returns:
        Tuple of (BM25Okapi instance or None, list of chunk IDs).
    """
    try:
        from app.infrastructure.redis.client import is_redis_available

        if not is_redis_available():
            return None, []

        redis_client = get_sync_redis()

        corpus_data = redis_client.get(f"{_BM25_KEY_PREFIX}{notebook_id}")
        docs_data = redis_client.get(f"{_BM25_DOCS_KEY_PREFIX}{notebook_id}")

        if corpus_data is None or docs_data is None:
            return None, []

        tokenised_corpus = json.loads(corpus_data)
        chunk_ids = json.loads(docs_data)
        bm25 = BM25Okapi(tokenised_corpus)
        return bm25, chunk_ids
    except Exception as exc:
        logger.warning("Failed to decode BM25 index for notebook %s: %s", notebook_id, exc)
        return None, []


def _clear_index(notebook_id: str) -> None:
    """Remove the BM25 index for a notebook from Redis."""
    try:
        from app.infrastructure.redis.client import is_redis_available

        if not is_redis_available():
            return

        redis_client = get_sync_redis()
        redis_client.delete(f"{_BM25_KEY_PREFIX}{notebook_id}")
        redis_client.delete(f"{_BM25_DOCS_KEY_PREFIX}{notebook_id}")
    except Exception:
        pass


def _tokenise(text: str) -> list[str]:
    """Simple whitespace + lowercase tokenisation for BM25."""
    return text.lower().split()
