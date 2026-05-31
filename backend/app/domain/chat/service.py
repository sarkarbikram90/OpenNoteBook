"""OpenNotebook — RAG chat service (core orchestration).

Provides the ``stream_answer`` async generator that:
1. Retrieves relevant chunks via the three-stage pipeline.
2. Builds the prompt with context + conversation history.
3. Streams tokens from Ollama via SSE events.
4. Emits citation events for each source used.
5. Persists user + assistant messages with citations and retrieval metadata.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.domain.chat.prompt import build_context, build_prompt, format_history
from app.infrastructure.db.models import ChatSession, Message, Source

if TYPE_CHECKING:
    from app.domain.retrieval.retriever import RetrievedChunk

logger = logging.getLogger(__name__)


# ── Public API ──────────────────────────────────────────────────────────────


async def stream_answer(
    notebook_id: str,
    question: str,
    db: AsyncSession,
    session_id: str | None = None,
    source_filter: list[str] | None = None,
) -> AsyncGenerator[str, None]:
    """Stream an RAG answer as SSE-formatted event strings.

    Yields SSE event strings in the format:
        ``event: <type>\\ndata: <json>\\n\\n``

    Event types:
        - ``token``: A generated token.
        - ``citation``: A source citation.
        - ``done``: Generation complete.
        - ``error``: An error occurred.

    Args:
        notebook_id: UUID of the notebook to query.
        question: The user's question.
        db: Async database session.
        session_id: Optional existing chat session ID.
        source_filter: Optional list of source UUIDs to restrict retrieval.

    Yields:
        SSE-formatted event strings.
    """
    settings = get_settings()
    start_time = time.perf_counter()

    # Deferred imports to avoid loading heavy ML libs at module level
    from app.domain.retrieval.retriever import retrieve
    from app.infrastructure.ollama.client import stream_generate

    try:
        # ── 1. Get or create chat session ───────────────────────────────
        session = await _get_or_create_session(db, notebook_id, session_id, question)
        actual_session_id = str(session.id)

        # ── 2. Save user message ────────────────────────────────────────
        user_msg = Message(
            session_id=session.id,
            role="user",
            content=question,
        )
        db.add(user_msg)
        await db.flush()

        # ── 3. Retrieve relevant chunks ─────────────────────────────────
        retrieval_result = retrieve(
            query=question,
            notebook_id=notebook_id,
            source_filter=source_filter,
        )
        chunks = retrieval_result.chunks

        # Resolve source names from DB for chunks that lack them
        await _enrich_source_names(db, chunks)

        # ── 4. Load conversation history ────────────────────────────────
        history_messages = await _load_history(
            db, session.id, settings.max_history_messages
        )
        history_str = format_history(history_messages)

        # ── 5. Build prompt ─────────────────────────────────────────────
        context_str = build_context(chunks)
        prompt = build_prompt(context_str, history_str, question)

        # ── 6. Stream tokens from Ollama ────────────────────────────────
        full_response = []
        async for token in stream_generate(prompt):
            full_response.append(token)
            yield _sse_event("token", {"token": token})

        response_text = "".join(full_response)

        # ── 7. Emit citation events ─────────────────────────────────────
        citations = _extract_citations(response_text, chunks)
        for citation in citations:
            yield _sse_event("citation", citation)

        # ── 8. Save assistant message ───────────────────────────────────
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        retrieval_meta = {
            "dense_latency_ms": retrieval_result.dense_latency_ms,
            "bm25_latency_ms": retrieval_result.bm25_latency_ms,
            "fusion_latency_ms": retrieval_result.fusion_latency_ms,
            "rerank_latency_ms": retrieval_result.rerank_latency_ms,
            "retrieval_total_ms": retrieval_result.total_latency_ms,
            "model": settings.ollama_model,
            "total_latency_ms": latency_ms,
        }

        assistant_msg = Message(
            session_id=session.id,
            role="assistant",
            content=response_text,
            citations=citations,
            retrieval_meta=retrieval_meta,
        )
        db.add(assistant_msg)
        await db.flush()

        # ── 9. Emit done event ──────────────────────────────────────────
        yield _sse_event("done", {
            "message_id": str(assistant_msg.id),
            "session_id": actual_session_id,
            "latency_ms": latency_ms,
        })

        logger.info(
            "Chat complete: notebook=%s session=%s latency=%dms tokens=%d",
            notebook_id, actual_session_id, latency_ms, len(full_response),
        )

    except Exception as exc:
        logger.error("Chat stream error: %s", exc, exc_info=True)
        yield _sse_event("error", {
            "code": "generation_error",
            "message": str(exc),
        })


# ── Session Management ──────────────────────────────────────────────────────


async def _get_or_create_session(
    db: AsyncSession,
    notebook_id: str,
    session_id: str | None,
    question: str,
) -> ChatSession:
    """Get an existing session or create a new one.

    If ``session_id`` is provided, loads and returns it.
    Otherwise, creates a new session with a title derived from the question.
    """
    if session_id:
        result = await db.execute(
            select(ChatSession).where(ChatSession.id == uuid.UUID(session_id))
        )
        session = result.scalar_one_or_none()
        if session is not None:
            return session

    # Create new session with truncated question as title
    title = question[:100] + ("…" if len(question) > 100 else "")
    session = ChatSession(
        notebook_id=uuid.UUID(notebook_id),
        title=title,
    )
    db.add(session)
    await db.flush()
    return session


# ── History Loading ─────────────────────────────────────────────────────────


async def _load_history(
    db: AsyncSession,
    session_id: uuid.UUID,
    max_messages: int,
) -> list[dict[str, str]]:
    """Load the last N messages from a session for context.

    Returns a list of dicts with ``role`` and ``content`` keys,
    ordered chronologically (oldest first).
    """
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.desc())
        .limit(max_messages)
    )
    messages = list(result.scalars().all())
    messages.reverse()  # Chronological order

    return [
        {"role": msg.role, "content": msg.content}
        for msg in messages
        # Exclude the user message we just saved (it's in the question)
        if msg.content.strip()
    ]


# ── Citation Extraction ─────────────────────────────────────────────────────


def _extract_citations(
    response_text: str,
    chunks: list[RetrievedChunk],
) -> list[dict[str, Any]]:
    """Extract cited sources from the response text.

    Looks for [Source N] patterns in the response and maps them back
    to the retrieved chunks.

    Returns:
        List of citation dicts with chunk metadata.
    """
    # Find all [Source N] references in the response
    pattern = r"\[Source\s+(\d+)\]"
    matches = re.findall(pattern, response_text)

    seen: set[str] = set()
    citations: list[dict[str, Any]] = []

    for match in matches:
        index = int(match) - 1  # Convert to 0-based
        if 0 <= index < len(chunks):
            chunk = chunks[index]
            if chunk.chunk_id in seen:
                continue
            seen.add(chunk.chunk_id)
            citations.append({
                "chunk_id": chunk.chunk_id,
                "source_name": chunk.source_name,
                "source_id": chunk.source_id,
                "page": chunk.page,
                "section": chunk.section,
                "relevance_score": round(chunk.relevance_score, 4),
            })

    return citations


# ── Source Name Enrichment ──────────────────────────────────────────────────


async def _enrich_source_names(
    db: AsyncSession,
    chunks: list[RetrievedChunk],
) -> None:
    """Fill in source_name on chunks by looking up Source records."""
    source_ids = {c.source_id for c in chunks if c.source_name in ("", "Unknown")}
    if not source_ids:
        return

    result = await db.execute(
        select(Source).where(Source.id.in_([uuid.UUID(sid) for sid in source_ids]))
    )
    source_map = {str(s.id): s.name for s in result.scalars().all()}

    for chunk in chunks:
        if chunk.source_id in source_map:
            chunk.source_name = source_map[chunk.source_id]


# ── SSE Formatting ──────────────────────────────────────────────────────────


def _sse_event(event_type: str, data: dict[str, Any]) -> str:
    """Format an SSE event string.

    Returns a string in the format:
        event: <type>
        data: <json>

        (blank line to terminate event)
    """
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
