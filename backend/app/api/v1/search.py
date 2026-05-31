"""OpenNotebook — Search API endpoint.

Provides semantic + keyword hybrid search across notebook sources
without LLM generation.

Endpoint:
    POST /api/v1/notebooks/{notebook_id}/search
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.v1.schemas.chat import (
    SearchChunkResult,
    SearchRequest,
    SearchResponse,
)
from app.core.deps import CurrentUser, DbSession
from app.domain.retrieval.retriever import retrieve
from app.infrastructure.db.models import Notebook

router = APIRouter(tags=["search"])


@router.post(
    "/notebooks/{notebook_id}/search",
    response_model=SearchResponse,
    summary="Search notebook sources",
    responses={
        404: {"description": "Notebook not found"},
    },
)
async def search_notebook(
    notebook_id: uuid.UUID,
    body: SearchRequest,
    user: CurrentUser,
    db: DbSession,
) -> SearchResponse:
    """Search across a notebook's indexed sources using hybrid retrieval.

    Runs the full three-stage pipeline (dense + BM25 + reranker)
    and returns ranked chunks without LLM generation.
    """
    # Verify notebook ownership
    result = await db.execute(
        select(Notebook).where(
            Notebook.id == notebook_id,
            Notebook.user_id == user.id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notebook not found",
        )

    source_filter = (
        [str(sid) for sid in body.source_filter]
        if body.source_filter
        else None
    )

    retrieval_result = retrieve(
        query=body.query,
        notebook_id=str(notebook_id),
        source_filter=source_filter,
    )

    # Limit to requested top_k
    chunks = retrieval_result.chunks[: body.top_k]

    results = [
        SearchChunkResult(
            chunk_id=chunk.chunk_id,
            source_id=chunk.source_id,
            source_name=chunk.source_name,
            text=chunk.text,
            page=chunk.page,
            section=chunk.section,
            relevance_score=round(chunk.relevance_score, 4),
            token_count=chunk.token_count,
        )
        for chunk in chunks
    ]

    return SearchResponse(
        results=results,
        total=len(results),
        latency_ms=round(retrieval_result.total_latency_ms, 1),
    )
