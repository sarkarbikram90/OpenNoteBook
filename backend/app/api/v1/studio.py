"""OpenNotebook — Studio API endpoints (Audio Overviews & Knowledge Graph).

Provides NotebookLM-style Audio Overviews (two-host grounded dialogue script +
pluggable TTS audio synthesis) and Interactive Knowledge Graph / GraphRAG
neighborhood exploration per notebook.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.core.audit import record_audit_event
from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession
from app.domain.studio.audio_overview import (
    build_dialogue_prompt,
    build_fallback_script,
    parse_dialogue_script,
    synthesize_openai_tts,
)
from app.domain.studio.knowledge_graph import build_notebook_knowledge_graph
from app.infrastructure.db.models import (
    AudioOverview,
    DocumentChunk,
    Notebook,
    Source,
    SourceSummary,
)
from app.infrastructure.llm import get_llm_provider
from app.infrastructure.storage.service import get_storage_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notebooks/{notebook_id}/studio", tags=["studio"])

_VALID_TONES = {"deep_dive", "brief", "debate"}


# ── Schemas ─────────────────────────────────────────────────────────────────


class DialogueTurnSchema(BaseModel):
    speaker: str
    text: str


class AudioOverviewCreateRequest(BaseModel):
    focus_topic: str | None = Field(default=None, max_length=240)
    tone: str = Field(default="deep_dive")


class AudioOverviewResponse(BaseModel):
    id: uuid.UUID
    notebook_id: uuid.UUID
    title: str
    summary: str
    focus_topic: str | None
    tone: str
    status: str
    turns: list[DialogueTurnSchema]
    duration_seconds: int
    source_count: int
    has_audio_file: bool
    audio_url: str | None
    playback_mode: str  # "server_audio" | "browser_tts"
    created_at: datetime


class GraphNodeSchema(BaseModel):
    id: str
    label: str
    kind: str
    weight: int
    source_ids: list[str]


class GraphEdgeSchema(BaseModel):
    source: str
    target: str
    relation: str
    weight: int


class KnowledgeGraphResponse(BaseModel):
    notebook_id: uuid.UUID
    nodes: list[GraphNodeSchema]
    edges: list[GraphEdgeSchema]
    matched_node_ids: list[str]
    stats: dict[str, int]


# ── Helpers ─────────────────────────────────────────────────────────────────


async def _verify_notebook_access(
    notebook_id: uuid.UUID, user_id: uuid.UUID, db: DbSession
) -> Notebook:
    res = await db.execute(
        select(Notebook).where(Notebook.id == notebook_id, Notebook.user_id == user_id)
    )
    nb = res.scalar_one_or_none()
    if nb is None:
        raise HTTPException(status_code=404, detail="Notebook not found")
    return nb


def _overview_to_response(overview: AudioOverview) -> AudioOverviewResponse:
    script = overview.script_json or {}
    raw_turns = script.get("turns") or []
    turns = [
        DialogueTurnSchema(
            speaker=str(t.get("speaker") or "Alex"),
            text=str(t.get("text") or ""),
        )
        for t in raw_turns
        if isinstance(t, dict)
    ]

    has_audio = bool(overview.audio_storage_path)
    audio_url: str | None = None
    if has_audio and overview.audio_storage_path:
        if overview.storage_type == "gcs":
            try:
                storage = get_storage_service("gcs")
                audio_url = storage.generate_signed_download_url(
                    overview.audio_storage_path, expiration_seconds=3600
                )
            except Exception:
                audio_url = f"/api/v1/notebooks/{overview.notebook_id}/studio/audio-overviews/{overview.id}/audio"
        else:
            audio_url = f"/api/v1/notebooks/{overview.notebook_id}/studio/audio-overviews/{overview.id}/audio"

    return AudioOverviewResponse(
        id=overview.id,
        notebook_id=overview.notebook_id,
        title=overview.title,
        summary=str(script.get("summary") or ""),
        focus_topic=overview.focus_topic,
        tone=overview.tone,
        status=overview.status,
        turns=turns,
        duration_seconds=overview.duration_seconds,
        source_count=overview.source_count,
        has_audio_file=has_audio,
        audio_url=audio_url,
        playback_mode="server_audio" if has_audio else "browser_tts",
        created_at=overview.created_at,
    )


# ── Audio Overview Endpoints ────────────────────────────────────────────────


@router.get(
    "/audio-overviews",
    response_model=list[AudioOverviewResponse],
    summary="List Audio Overviews for a notebook",
)
async def list_audio_overviews(
    notebook_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> list[AudioOverviewResponse]:
    """Return previously generated Audio Overviews ordered newest first."""
    await _verify_notebook_access(notebook_id, user.id, db)
    res = await db.execute(
        select(AudioOverview)
        .where(AudioOverview.notebook_id == notebook_id)
        .order_by(AudioOverview.created_at.desc())
    )
    return [_overview_to_response(o) for o in res.scalars().all()]


@router.post(
    "/audio-overviews",
    response_model=AudioOverviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a two-host podcast Audio Overview",
)
async def create_audio_overview(
    notebook_id: uuid.UUID,
    payload: AudioOverviewCreateRequest,
    user: CurrentUser,
    db: DbSession,
) -> AudioOverviewResponse:
    """Synthesize a grounded two-host Audio Overview script (and MP3 when TTS is configured)."""
    notebook = await _verify_notebook_access(notebook_id, user.id, db)

    tone = payload.tone.lower().strip()
    if tone not in _VALID_TONES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tone. Expected one of: {sorted(_VALID_TONES)}",
        )

    sources_res = await db.execute(
        select(Source)
        .where(Source.notebook_id == notebook_id)
        .order_by(Source.created_at.desc())
    )
    sources = list(sources_res.scalars().all())
    if not sources:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Add at least one source to this notebook before generating an Audio Overview.",
        )

    source_name_map = {s.id: s.name for s in sources}
    source_ids = [s.id for s in sources]

    # Collect excerpts from SourceSummary and DocumentChunk
    excerpts: list[tuple[str, str]] = []
    summaries_res = await db.execute(
        select(SourceSummary).where(SourceSummary.source_id.in_(source_ids))
    )
    for summary in summaries_res.scalars().all():
        parts = []
        if summary.executive_summary:
            parts.append(summary.executive_summary)
        if summary.key_findings:
            parts.append("Key findings: " + "; ".join(str(k) for k in summary.key_findings[:5]))
        if parts:
            excerpts.append((source_name_map.get(summary.source_id, "Source"), "\n".join(parts)))

    if len(excerpts) < 8:
        chunks_res = await db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.notebook_id == notebook_id)
            .limit(12)
        )
        for ch in chunks_res.scalars().all():
            excerpts.append((ch.source_name or source_name_map.get(ch.source_id, "Source"), ch.text))

    if not excerpts:
        excerpts = [(s.name, f"Uploaded {s.source_type} source '{s.name}'.") for s in sources[:6]]

    # Generate dialogue script via configured LLM with deterministic offline fallback
    prompt = build_dialogue_prompt(
        notebook.name,
        excerpts,
        focus_topic=payload.focus_topic,
        tone=tone,
    )
    try:
        llm = get_llm_provider()
        raw_script = await llm.generate(prompt, temperature=0.6)
        script = parse_dialogue_script(
            raw_script,
            notebook.name,
            excerpts,
            focus_topic=payload.focus_topic,
            tone=tone,
        )
    except Exception as exc:
        logger.warning("LLM audio overview generation failed (%s); using extractive fallback", exc)
        script = build_fallback_script(
            notebook.name,
            excerpts,
            focus_topic=payload.focus_topic,
            tone=tone,
        )

    # Optional server-side TTS synthesis (OpenAI TTS)
    settings = get_settings()
    overview_id = uuid.uuid4()
    audio_path: str | None = None
    storage_type = settings.storage_provider

    if settings.openai_api_key:
        mp3_bytes = await synthesize_openai_tts(
            script.turns,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        if mp3_bytes:
            object_name = f"audio/{notebook_id}/{overview_id}.mp3"
            try:
                storage = get_storage_service()
                await run_in_threadpool(
                    storage.upload_raw_document,
                    mp3_bytes,
                    object_name,
                    "audio/mpeg",
                )
                audio_path = object_name
                storage_type = storage.provider
            except Exception as upload_exc:
                logger.warning("Failed to store synthesized MP3 audio: %s", upload_exc)

    overview = AudioOverview(
        id=overview_id,
        notebook_id=notebook_id,
        user_id=user.id,
        title=script.title,
        focus_topic=payload.focus_topic,
        tone=tone,
        status="READY",
        script_json=script.to_dict(),
        audio_storage_path=audio_path,
        storage_type=storage_type,
        duration_seconds=script.estimated_duration_seconds,
        source_count=len(sources),
    )
    db.add(overview)
    await db.flush()
    await db.refresh(overview)

    await record_audit_event(
        db=db,
        action="studio.audio_overview.create",
        resource_type="audio_overview",
        resource_id=str(overview.id),
        user_id=user.id,
        details={"notebook_id": str(notebook_id), "tone": tone, "turns": len(script.turns)},
    )

    return _overview_to_response(overview)


@router.get(
    "/audio-overviews/{overview_id}/audio",
    summary="Download/stream synthesized Audio Overview MP3",
)
async def stream_audio_overview_file(
    notebook_id: uuid.UUID,
    overview_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> Response:
    """Stream synthesized MP3 audio bytes from configured storage."""
    await _verify_notebook_access(notebook_id, user.id, db)
    res = await db.execute(
        select(AudioOverview).where(
            AudioOverview.id == overview_id,
            AudioOverview.notebook_id == notebook_id,
        )
    )
    overview = res.scalar_one_or_none()
    if overview is None or not overview.audio_storage_path:
        raise HTTPException(status_code=404, detail="Audio file not available")

    storage = get_storage_service(overview.storage_type)
    data = await run_in_threadpool(storage.download_document, overview.audio_storage_path)
    return Response(content=data, media_type="audio/mpeg")


@router.delete(
    "/audio-overviews/{overview_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an Audio Overview",
)
async def delete_audio_overview(
    notebook_id: uuid.UUID,
    overview_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> None:
    """Delete an Audio Overview and clean up any stored audio blob."""
    await _verify_notebook_access(notebook_id, user.id, db)
    res = await db.execute(
        select(AudioOverview).where(
            AudioOverview.id == overview_id,
            AudioOverview.notebook_id == notebook_id,
        )
    )
    overview = res.scalar_one_or_none()
    if overview is None:
        raise HTTPException(status_code=404, detail="Audio Overview not found")

    if overview.audio_storage_path:
        try:
            storage = get_storage_service(overview.storage_type)
            await run_in_threadpool(storage.delete_document, overview.audio_storage_path)
        except Exception as exc:
            logger.warning("Could not delete audio blob %s: %s", overview.audio_storage_path, exc)

    await db.delete(overview)
    await db.flush()


# ── Knowledge Graph / GraphRAG Endpoint ─────────────────────────────────────


@router.get(
    "/knowledge-graph",
    response_model=KnowledgeGraphResponse,
    summary="Get Interactive Knowledge Graph and GraphRAG traversal for a notebook",
)
async def get_notebook_knowledge_graph(
    notebook_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    query: str | None = Query(default=None, description="Optional GraphRAG query to highlight neighborhood"),
) -> KnowledgeGraphResponse:
    """Build and return the entity-relationship Knowledge Graph for a notebook."""
    await _verify_notebook_access(notebook_id, user.id, db)

    sources_res = await db.execute(
        select(Source).where(Source.notebook_id == notebook_id)
    )
    sources = list(sources_res.scalars().all())
    source_ids = [s.id for s in sources]

    summaries_data: list[dict[str, Any]] = []
    if source_ids:
        sum_res = await db.execute(
            select(SourceSummary).where(SourceSummary.source_id.in_(source_ids))
        )
        summaries_data = [
            {"source_id": str(s.source_id), "entities": s.entities or {}}
            for s in sum_res.scalars().all()
        ]

    chunks_res = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.notebook_id == notebook_id)
        .limit(250)
    )
    chunks_data = [
        {"source_id": str(c.source_id), "text": c.text}
        for c in chunks_res.scalars().all()
    ]

    graph = build_notebook_knowledge_graph(
        sources=[{"id": str(s.id), "name": s.name} for s in sources],
        summaries=summaries_data,
        chunks=chunks_data,
        query=query,
    )

    return KnowledgeGraphResponse(
        notebook_id=notebook_id,
        nodes=[GraphNodeSchema(**n.to_dict()) for n in graph.nodes],
        edges=[GraphEdgeSchema(**e.to_dict()) for e in graph.edges],
        matched_node_ids=graph.matched_node_ids,
        stats=graph.stats,
    )
