"""OpenNotebook — Three-stage hybrid retrieval pipeline.

Implements:
    Stage 1 — Parallel retrieval: Qdrant dense cosine + BM25 keyword
    Stage 2 — Reciprocal Rank Fusion (RRF) score merging
    Stage 3 — Cross-encoder reranking (BGE-reranker-base)
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)


# ── Data Transfer Objects ───────────────────────────────────────────────────


@dataclass
class RetrievedChunk:
    """A chunk returned by the retrieval pipeline with full metadata."""

    chunk_id: str
    source_id: str
    source_name: str
    notebook_id: str
    text: str
    page: int | None = None
    section: str | None = None
    relevance_score: float = 0.0
    token_count: int = 0
    start_char: int = 0
    end_char: int = 0


@dataclass
class RetrievalResult:
    """Full result of a retrieval pipeline run with timing metadata."""

    chunks: list[RetrievedChunk] = field(default_factory=list)
    dense_latency_ms: float = 0.0
    bm25_latency_ms: float = 0.0
    fusion_latency_ms: float = 0.0
    rerank_latency_ms: float = 0.0
    total_latency_ms: float = 0.0


# ── Public API ──────────────────────────────────────────────────────────────


def retrieve(
    query: str,
    notebook_id: str,
    source_filter: list[str] | None = None,
) -> RetrievalResult:
    """Run the full three-stage hybrid retrieval pipeline.

    Args:
        query: The user's search query.
        notebook_id: UUID of the notebook to search within.
        source_filter: Optional list of source UUIDs to restrict results to.

    Returns:
        ``RetrievalResult`` with ranked chunks and timing metadata.
    """
    settings = get_settings()
    top_k = settings.retrieval_top_k
    rerank_top_k = settings.rerank_top_k
    rrf_k = settings.rrf_k

    total_start = time.perf_counter()

    # ── Stage 1a: Dense vector search (Qdrant) ──────────────────────────
    t0 = time.perf_counter()
    dense_results = _dense_search(query, notebook_id, top_k, source_filter)
    dense_latency = (time.perf_counter() - t0) * 1000

    # ── Stage 1b: BM25 keyword search ───────────────────────────────────
    t0 = time.perf_counter()
    bm25_results = _bm25_search(query, notebook_id, top_k)
    bm25_latency = (time.perf_counter() - t0) * 1000

    # ── Stage 2: Reciprocal Rank Fusion ─────────────────────────────────
    t0 = time.perf_counter()
    fused = _reciprocal_rank_fusion(dense_results, bm25_results, k=rrf_k, top_k=top_k)
    fusion_latency = (time.perf_counter() - t0) * 1000

    # Apply source filter to BM25 results (dense already filtered by Qdrant)
    if source_filter:
        filter_set = set(source_filter)
        fused = [c for c in fused if c.get("source_id") in filter_set]

    if not fused:
        total_latency = (time.perf_counter() - total_start) * 1000
        return RetrievalResult(
            dense_latency_ms=dense_latency,
            bm25_latency_ms=bm25_latency,
            fusion_latency_ms=fusion_latency,
            total_latency_ms=total_latency,
        )

    # ── Stage 3: Cross-encoder reranking ────────────────────────────────
    from app.infrastructure.reranker.client import rerank

    t0 = time.perf_counter()
    reranked = rerank(query, fused, top_k=rerank_top_k)
    rerank_latency = (time.perf_counter() - t0) * 1000

    total_latency = (time.perf_counter() - total_start) * 1000

    # Build final result
    chunks = [
        RetrievedChunk(
            chunk_id=r.chunk.get("chunk_id", ""),
            source_id=r.chunk.get("source_id", ""),
            source_name=r.chunk.get("source_name", "Unknown"),
            notebook_id=r.chunk.get("notebook_id", ""),
            text=r.chunk.get("text", ""),
            page=r.chunk.get("page"),
            section=r.chunk.get("section"),
            relevance_score=r.score,
            token_count=r.chunk.get("token_count", 0),
            start_char=r.chunk.get("start_char", 0),
            end_char=r.chunk.get("end_char", 0),
        )
        for r in reranked
    ]

    logger.info(
        "Retrieval complete for notebook %s: dense=%.1fms bm25=%.1fms "
        "fusion=%.1fms rerank=%.1fms total=%.1fms chunks=%d",
        notebook_id,
        dense_latency,
        bm25_latency,
        fusion_latency,
        rerank_latency,
        total_latency,
        len(chunks),
    )

    return RetrievalResult(
        chunks=chunks,
        dense_latency_ms=dense_latency,
        bm25_latency_ms=bm25_latency,
        fusion_latency_ms=fusion_latency,
        rerank_latency_ms=rerank_latency,
        total_latency_ms=total_latency,
    )


# ── Internal Helpers ────────────────────────────────────────────────────────


def _dense_search(
    query: str,
    notebook_id: str,
    top_k: int,
    source_filter: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Stage 1a: Dense vector search via Qdrant cosine similarity."""
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    from app.domain.sources.embedder import embed_texts
    from app.infrastructure.qdrant.client import get_qdrant_client

    settings = get_settings()
    client = get_qdrant_client()

    # Embed the query
    query_vectors = embed_texts([query])
    if not query_vectors:
        return []
    query_vector = query_vectors[0]

    # Build filter: notebook_id is mandatory, source_id is optional
    must_conditions = [
        FieldCondition(key="notebook_id", match=MatchValue(value=notebook_id))
    ]
    if source_filter:
        # Qdrant doesn't have an "in" filter natively in older versions,
        # so we use multiple should conditions for source filtering
        pass  # We'll filter post-retrieval for simplicity

    search_filter = Filter(must=must_conditions)

    results = client.search(
        collection_name=settings.qdrant_collection,
        query_vector=query_vector,
        query_filter=search_filter,
        limit=top_k,
        with_payload=True,
    )

    chunks = []
    for point in results:
        payload = point.payload or {}
        payload["_dense_score"] = point.score
        chunks.append(payload)

    logger.debug("Dense search returned %d results", len(chunks))
    return chunks


def _bm25_search(
    query: str,
    notebook_id: str,
    top_k: int,
) -> list[dict[str, Any]]:
    """Stage 1b: BM25 keyword search from the Redis-cached index."""
    from app.domain.sources.bm25_index import _tokenise, load_bm25_index
    from app.infrastructure.qdrant.client import get_all_chunks_for_notebook

    bm25, chunk_ids = load_bm25_index(notebook_id)
    if bm25 is None or not chunk_ids:
        logger.debug("No BM25 index found for notebook %s", notebook_id)
        return []

    tokenised_query = _tokenise(query)
    scores = bm25.get_scores(tokenised_query)

    # Pair chunk IDs with scores and take top-k
    scored_pairs = sorted(
        zip(chunk_ids, scores),
        key=lambda pair: pair[1],
        reverse=True,
    )[:top_k]

    # We need the full payloads — fetch from Qdrant by chunk ID
    all_chunks = get_all_chunks_for_notebook(notebook_id)
    chunk_map = {c.get("chunk_id", ""): c for c in all_chunks}

    results = []
    for chunk_id, score in scored_pairs:
        if score <= 0:
            continue
        payload = chunk_map.get(chunk_id)
        if payload:
            payload = dict(payload)  # Don't mutate the original
            payload["_bm25_score"] = score
            results.append(payload)

    logger.debug("BM25 search returned %d results", len(results))
    return results


def _reciprocal_rank_fusion(
    dense_results: list[dict[str, Any]],
    bm25_results: list[dict[str, Any]],
    k: int = 60,
    top_k: int = 20,
) -> list[dict[str, Any]]:
    """Stage 2: Merge results from dense and BM25 using RRF.

    RRF score for document d:
        rrf_score(d) = Σ 1 / (k + rank_i(d))

    where rank_i(d) is the 1-based rank of d in result list i.
    """
    scores: dict[str, float] = defaultdict(float)
    chunk_map: dict[str, dict[str, Any]] = {}

    # Score dense results
    for rank, chunk in enumerate(dense_results, start=1):
        cid = chunk.get("chunk_id", "")
        if not cid:
            continue
        scores[cid] += 1.0 / (k + rank)
        chunk_map[cid] = chunk

    # Score BM25 results
    for rank, chunk in enumerate(bm25_results, start=1):
        cid = chunk.get("chunk_id", "")
        if not cid:
            continue
        scores[cid] += 1.0 / (k + rank)
        if cid not in chunk_map:
            chunk_map[cid] = chunk

    # Sort by RRF score descending
    sorted_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)

    results = []
    for cid in sorted_ids[:top_k]:
        chunk = chunk_map[cid]
        chunk["_rrf_score"] = scores[cid]
        results.append(chunk)

    logger.debug("RRF fusion produced %d results", len(results))
    return results
