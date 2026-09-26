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
class UserSecurityContext:
    """Security credentials and clearance of the user requesting retrieval."""

    user_id: str
    workspace_id: str | None = None
    roles: list[str] = field(default_factory=lambda: ["viewer"])
    max_sensitivity: str = "internal"  # "public", "internal", "confidential", "restricted"


def is_chunk_authorized(chunk: dict[str, Any], sec_ctx: UserSecurityContext | None) -> bool:
    """Evaluate whether a chunk is authorized for retrieval under the user security context."""
    if sec_ctx is None:
        return True

    # Owners and admins have full access across the workspace/notebook
    roles_lower = {r.lower() for r in sec_ctx.roles}
    if "owner" in roles_lower or "admin" in roles_lower:
        return True

    # 1. Check Sensitivity Classification
    chunk_sens = chunk.get("sensitivity_level", "internal")
    from app.domain.governance.sensitivity import SensitivityLevel

    try:
        level = SensitivityLevel(chunk_sens.lower())
        if not level.is_accessible_by(sec_ctx.max_sensitivity):
            return False
    except ValueError:
        pass

    # 2. Check Document-level ACLs (allowed_roles, allowed_users)
    allowed_roles = chunk.get("allowed_roles") or []
    allowed_users = chunk.get("allowed_users") or []

    # If no explicit ACL restrictions exist, default to workspace/notebook membership
    if not allowed_roles and not allowed_users:
        return True

    # Direct user grant
    if sec_ctx.user_id in allowed_users:
        return True

    # Role grant
    if any(r.lower() in roles_lower for r in allowed_roles):
        return True

    return False


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
    sensitivity_level: str = "internal"


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
    security_context: UserSecurityContext | None = None,
) -> RetrievalResult:
    """Run the full three-stage hybrid retrieval pipeline with security trimming.

    Args:
        query: The user's search query.
        notebook_id: UUID of the notebook to search within.
        source_filter: Optional list of source UUIDs to restrict results to.
        security_context: Optional user security clearance & ACL roles.

    Returns:
        ``RetrievalResult`` with ranked chunks and timing metadata.
    """
    settings = get_settings()
    top_k = settings.retrieval_top_k
    rerank_top_k = settings.rerank_top_k
    rrf_k = settings.rrf_k

    total_start = time.perf_counter()
    from app.core.metrics import retrieval_duration

    # ── Stage 1a: Dense vector search (Qdrant) ──────────────────────────
    t0 = time.perf_counter()
    dense_results = _dense_search(query, notebook_id, top_k, source_filter, security_context)
    dense_latency = (time.perf_counter() - t0) * 1000
    retrieval_duration.labels(stage="dense").observe(dense_latency / 1000.0)

    # ── Stage 1b: BM25 keyword search ───────────────────────────────────
    t0 = time.perf_counter()
    bm25_results = _bm25_search(query, notebook_id, top_k, security_context)
    bm25_latency = (time.perf_counter() - t0) * 1000
    retrieval_duration.labels(stage="bm25").observe(bm25_latency / 1000.0)

    # ── Stage 2: Reciprocal Rank Fusion ─────────────────────────────────
    t0 = time.perf_counter()
    fused = _reciprocal_rank_fusion(dense_results, bm25_results, k=rrf_k, top_k=top_k)
    fusion_latency = (time.perf_counter() - t0) * 1000
    retrieval_duration.labels(stage="fusion").observe(fusion_latency / 1000.0)

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
    retrieval_duration.labels(stage="rerank").observe(rerank_latency / 1000.0)

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
            sensitivity_level=r.chunk.get("sensitivity_level", "internal"),
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
    security_context: UserSecurityContext | None = None,
) -> list[dict[str, Any]]:
    """Stage 1a: Dense vector search via Qdrant cosine similarity with security trimming."""
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    from app.domain.sources.embedder import embed_texts
    from app.infrastructure.qdrant.client import get_qdrant_client

    settings = get_settings()
    client = get_qdrant_client()

    # Embed the query with instruction prefix
    query_vectors = embed_texts([query], is_query=True)
    if not query_vectors:
        return []
    query_vector = query_vectors[0]

    # Build filter: notebook_id is mandatory, source_id is optional
    must_conditions = [FieldCondition(key="notebook_id", match=MatchValue(value=notebook_id))]
    search_filter = Filter(must=must_conditions)

    # Fetch slightly larger candidate set to allow for ACL security trimming
    candidate_limit = top_k * 2 if security_context else top_k

    results = client.search(
        collection_name=settings.qdrant_collection,
        query_vector=query_vector,
        query_filter=search_filter,
        limit=candidate_limit,
        with_payload=True,
    )

    chunks = []
    for point in results:
        payload = point.payload or {}
        if not is_chunk_authorized(payload, security_context):
            continue
        payload["_dense_score"] = point.score
        chunks.append(payload)
        if len(chunks) >= top_k:
            break

    logger.debug("Dense search returned %d authorized results", len(chunks))
    return chunks


def _bm25_search(
    query: str,
    notebook_id: str,
    top_k: int,
    security_context: UserSecurityContext | None = None,
) -> list[dict[str, Any]]:
    """Stage 1b: BM25 keyword search from the Redis-cached index with security trimming."""
    from app.domain.sources.bm25_index import _tokenise, load_bm25_index
    from app.infrastructure.qdrant.client import get_chunks_by_ids

    try:
        bm25, chunk_ids = load_bm25_index(notebook_id)
    except Exception as exc:
        # Redis unavailable (e.g. serverless without Redis) — degrade to vector-only.
        logger.warning(
            "BM25 index unavailable for notebook %s (%s); using vector-only retrieval",
            notebook_id,
            exc,
        )
        return []

    if bm25 is None or not chunk_ids:
        logger.debug("No BM25 index found for notebook %s", notebook_id)
        return []

    tokenised_query = _tokenise(query)
    scores = bm25.get_scores(tokenised_query)

    # Filter to positive scores and take top candidates
    scored_pairs = [(cid, score) for cid, score in zip(chunk_ids, scores) if score > 0]
    scored_pairs.sort(key=lambda pair: pair[1], reverse=True)
    candidate_limit = top_k * 2 if security_context else top_k
    scored_pairs = scored_pairs[:candidate_limit]

    if not scored_pairs:
        return []

    # Fetch matched chunk payloads from Qdrant
    top_chunk_ids = [cid for cid, _ in scored_pairs]
    score_map = dict(scored_pairs)
    payloads = get_chunks_by_ids(top_chunk_ids)

    results = []
    for payload in payloads:
        if not is_chunk_authorized(payload, security_context):
            continue
        cid = payload.get("chunk_id", "")
        if cid in score_map:
            p = dict(payload)
            p["_bm25_score"] = score_map[cid]
            results.append(p)
            if len(results) >= top_k:
                break

    # Sort results by bm25 score descending
    results.sort(key=lambda r: r["_bm25_score"], reverse=True)

    logger.debug("BM25 search returned %d authorized results", len(results))
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
