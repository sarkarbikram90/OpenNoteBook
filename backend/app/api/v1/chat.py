"""OpenNotebook — Chat API endpoints.

Provides streaming RAG chat, session CRUD, message listing, and export.

Endpoints:
    POST   /api/v1/notebooks/{notebook_id}/chat       → SSE streaming answer
    GET    /api/v1/notebooks/{notebook_id}/sessions    → list chat sessions
    GET    /api/v1/sessions/{session_id}               → get session detail
    GET    /api/v1/sessions/{session_id}/messages      → list messages
    POST   /api/v1/sessions/{session_id}/export        → export session
    DELETE /api/v1/sessions/{session_id}               → delete session
"""

from __future__ import annotations

import io
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse, Response
from sqlalchemy import delete, func, select

from app.api.v1.schemas.chat import (
    ChatRequest,
    ChatSessionListResponse,
    ChatSessionResponse,
    ExportRequest,
    MessageListResponse,
    MessageResponse,
)
from app.core.deps import CurrentUser, DbSession
from app.domain.chat.service import stream_answer
from app.infrastructure.db.models import ChatSession, Message, Notebook

router = APIRouter(tags=["chat"])


# ── SSE Streaming Chat ─────────────────────────────────────────────────────


@router.post(
    "/notebooks/{notebook_id}/chat",
    summary="Stream a RAG answer (SSE)",
    responses={
        200: {"description": "SSE stream of token, citation, done, and error events"},
        404: {"description": "Notebook not found"},
    },
)
async def chat(
    notebook_id: uuid.UUID,
    body: ChatRequest,
    user: CurrentUser,
    db: DbSession,
) -> StreamingResponse:
    """Send a question against a notebook's sources and receive a streamed answer.

    Returns a ``text/event-stream`` response with the following SSE events:
    - ``token``: Individual generated tokens.
    - ``citation``: Source citations referenced in the answer.
    - ``done``: Generation complete with metadata.
    - ``error``: An error occurred during generation.
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

    event_stream = stream_answer(
        notebook_id=str(notebook_id),
        question=body.question,
        db=db,
        session_id=str(body.session_id) if body.session_id else None,
        source_filter=source_filter,
    )

    return StreamingResponse(
        event_stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Session CRUD ────────────────────────────────────────────────────────────


@router.get(
    "/notebooks/{notebook_id}/sessions",
    response_model=ChatSessionListResponse,
    summary="List chat sessions for a notebook",
)
async def list_sessions(
    notebook_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> ChatSessionListResponse:
    """List all chat sessions for a notebook, ordered by most recent."""
    # Verify notebook ownership
    nb_result = await db.execute(
        select(Notebook).where(
            Notebook.id == notebook_id,
            Notebook.user_id == user.id,
        )
    )
    if nb_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notebook not found",
        )

    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.notebook_id == notebook_id)
        .order_by(ChatSession.updated_at.desc())
    )
    sessions = list(result.scalars().all())

    responses = []
    for session in sessions:
        msg_count_result = await db.execute(
            select(func.count()).where(Message.session_id == session.id)
        )
        msg_count = msg_count_result.scalar() or 0
        responses.append(
            ChatSessionResponse(
                id=session.id,
                notebook_id=session.notebook_id,
                title=session.title,
                created_at=session.created_at,
                updated_at=session.updated_at,
                message_count=msg_count,
            )
        )

    return ChatSessionListResponse(sessions=responses, total=len(responses))


@router.get(
    "/sessions/{session_id}",
    response_model=ChatSessionResponse,
    summary="Get a chat session",
)
async def get_session(
    session_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> ChatSessionResponse:
    """Get a specific chat session by ID."""
    session = await _get_user_session(session_id, user.id, db)

    msg_count_result = await db.execute(
        select(func.count()).where(Message.session_id == session.id)
    )
    msg_count = msg_count_result.scalar() or 0

    return ChatSessionResponse(
        id=session.id,
        notebook_id=session.notebook_id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=msg_count,
    )


@router.get(
    "/sessions/{session_id}/messages",
    response_model=MessageListResponse,
    summary="List messages in a chat session",
)
async def list_messages(
    session_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> MessageListResponse:
    """List all messages in a chat session, ordered chronologically."""
    await _get_user_session(session_id, user.id, db)

    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
    )
    messages = list(result.scalars().all())

    responses = [
        MessageResponse(
            id=msg.id,
            session_id=msg.session_id,
            role=msg.role,
            content=msg.content,
            citations=msg.citations,
            retrieval_meta=msg.retrieval_meta,
            created_at=msg.created_at,
        )
        for msg in messages
    ]

    return MessageListResponse(messages=responses, total=len(responses))


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a chat session",
)
async def delete_session(
    session_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> None:
    """Delete a chat session and all its messages."""
    await _get_user_session(session_id, user.id, db)
    await db.execute(delete(ChatSession).where(ChatSession.id == session_id))


# ── Export ──────────────────────────────────────────────────────────────────


@router.post(
    "/sessions/{session_id}/export",
    summary="Export a chat session",
    responses={
        200: {"description": "Exported session file"},
        404: {"description": "Session not found"},
    },
)
async def export_session(
    session_id: uuid.UUID,
    body: ExportRequest,
    user: CurrentUser,
    db: DbSession,
) -> Response:
    """Export a chat session as Markdown or PDF.

    The export includes the session title, date, all messages with
    citations, and a source list.
    """
    session = await _get_user_session(session_id, user.id, db)

    # Load messages
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
    )
    messages = list(result.scalars().all())

    if body.format == "markdown":
        return _export_markdown(session, messages)
    else:
        return _export_pdf(session, messages)


# ── Summarisation Trigger ───────────────────────────────────────────────────


@router.post(
    "/notebooks/{notebook_id}/sources/{source_id}/summary",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate a source summary (async)",
    responses={
        202: {"description": "Summarisation task queued"},
        404: {"description": "Source not found"},
    },
)
async def trigger_summary(
    notebook_id: uuid.UUID,
    source_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Trigger async summarisation of a source document.

    Returns immediately with a task ID.  The summary will be generated
    in the background and saved to the source_summaries table.
    """
    from app.infrastructure.db.models import Source

    # Verify notebook ownership
    nb_result = await db.execute(
        select(Notebook).where(
            Notebook.id == notebook_id,
            Notebook.user_id == user.id,
        )
    )
    if nb_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notebook not found",
        )

    # Verify source exists
    src_result = await db.execute(
        select(Source).where(
            Source.id == source_id,
            Source.notebook_id == notebook_id,
        )
    )
    if src_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )

    # Queue Celery task
    from app.worker.tasks.summarise import generate_summary

    task = generate_summary.delay(str(source_id))

    return {
        "task_id": task.id,
        "source_id": str(source_id),
        "status": "queued",
        "message": "Summarisation task queued",
    }


# ── Helpers ─────────────────────────────────────────────────────────────────


async def _get_user_session(
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    db: DbSession,
) -> ChatSession:
    """Fetch a session, verifying the user owns the parent notebook."""
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    # Verify ownership via notebook
    nb_result = await db.execute(
        select(Notebook).where(
            Notebook.id == session.notebook_id,
            Notebook.user_id == user_id,
        )
    )
    if nb_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    return session


def _export_markdown(session: ChatSession, messages: list[Message]) -> Response:
    """Generate a Markdown export of a chat session."""
    lines = [
        f"# {session.title}",
        f"*Exported on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}*",
        "",
        "---",
        "",
    ]

    all_citations: list[dict] = []

    for msg in messages:
        role_label = "**You**" if msg.role == "user" else "**Assistant**"
        lines.append(f"### {role_label}")
        lines.append("")
        lines.append(msg.content)
        lines.append("")

        if msg.citations:
            all_citations.extend(msg.citations)

    # Deduplicated source list
    if all_citations:
        lines.append("---")
        lines.append("")
        lines.append("**Sources used**")
        lines.append("")

        seen: set[str] = set()
        idx = 1
        for citation in all_citations:
            cid = citation.get("chunk_id", "")
            if cid in seen:
                continue
            seen.add(cid)
            name = citation.get("source_name", "Unknown")
            page = citation.get("page")
            page_str = f" — page {page}" if page else ""
            lines.append(f"{idx}. {name}{page_str}")
            idx += 1

    content = "\n".join(lines)
    filename = f"{session.title[:50].replace(' ', '_')}.md"

    return Response(
        content=content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _export_pdf(session: ChatSession, messages: list[Message]) -> Response:
    """Generate a PDF export of a chat session."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, session.title[:80], ln=True)

    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, f"Exported on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", ln=True)
    pdf.ln(5)

    all_citations: list[dict] = []

    for msg in messages:
        # Role header
        pdf.set_font("Helvetica", "B", 11)
        role_label = "You" if msg.role == "user" else "Assistant"
        pdf.cell(0, 8, role_label, ln=True)

        # Message content
        pdf.set_font("Helvetica", "", 10)
        # Handle encoding: replace non-latin1 chars
        safe_content = msg.content.encode("latin-1", errors="replace").decode("latin-1")
        pdf.multi_cell(0, 5, safe_content)
        pdf.ln(3)

        if msg.citations:
            all_citations.extend(msg.citations)

    # Sources section
    if all_citations:
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Sources used", ln=True)
        pdf.set_font("Helvetica", "", 10)

        seen: set[str] = set()
        idx = 1
        for citation in all_citations:
            cid = citation.get("chunk_id", "")
            if cid in seen:
                continue
            seen.add(cid)
            name = citation.get("source_name", "Unknown")
            page = citation.get("page")
            page_str = f" - page {page}" if page else ""
            safe_line = f"{idx}. {name}{page_str}"
            safe_line = safe_line.encode("latin-1", errors="replace").decode("latin-1")
            pdf.cell(0, 6, safe_line, ln=True)
            idx += 1

    # Output
    pdf_bytes = pdf.output()
    filename = f"{session.title[:50].replace(' ', '_')}.pdf"

    return Response(
        content=bytes(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
