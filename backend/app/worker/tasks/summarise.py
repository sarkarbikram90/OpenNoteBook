"""OpenNotebook — Summarisation Celery task.

Generates structured summaries for source documents using Ollama.
Runs asynchronously and saves results to the ``source_summaries`` table.
"""

from __future__ import annotations

import asyncio
import json
import logging
import traceback
import uuid

from sqlalchemy import select, update

from app.core.config import get_settings
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)

# ── Summarisation Prompt ────────────────────────────────────────────────────

_SUMMARY_PROMPT = """You are a document analysis assistant. Analyse the following document text and produce a structured summary.

Return your response as a valid JSON object with these exact keys:
- "executive_summary": A 2-3 paragraph overview of the document.
- "key_findings": A list of 3-5 key findings or takeaways (strings).
- "important_entities": An object with keys "people", "organisations", "concepts" — each a list of strings.
- "suggested_questions": A list of 3 questions a reader might want to ask about this document.

Respond ONLY with the JSON object, no additional text.

Document text:
{text}"""


# ── Celery Task ─────────────────────────────────────────────────────────────


@celery_app.task(
    bind=True,
    name="app.worker.tasks.summarise.generate_summary",
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
)
def generate_summary(self, source_id: str) -> dict:
    """Generate a structured summary for a source document.

    Pipeline:
        1. Load all chunks for the source from Qdrant.
        2. Concatenate chunk texts (truncated to fit context window).
        3. Send to Ollama with the summarisation prompt.
        4. Parse the JSON response.
        5. Save to the ``source_summaries`` table.

    Args:
        source_id: UUID of the source to summarise.

    Returns:
        Dict with task result summary.
    """
    try:
        logger.info("Starting summarisation for source %s", source_id)

        # Load chunks
        from app.infrastructure.qdrant.client import get_all_chunks_for_notebook

        source_record = _get_source_record(source_id)
        notebook_id = source_record["notebook_id"]

        # Get all chunks for the notebook, filter to this source
        all_chunks = get_all_chunks_for_notebook(notebook_id)
        source_chunks = [
            c for c in all_chunks
            if c.get("source_id") == source_id
        ]

        if not source_chunks:
            logger.warning("No chunks found for source %s", source_id)
            return {"source_id": source_id, "status": "skipped", "reason": "no_chunks"}

        # Concatenate texts (limit to ~6000 tokens worth of text)
        texts = [c.get("text", "") for c in source_chunks]
        combined_text = "\n\n".join(texts)

        # Rough truncation: ~4 chars per token, limit to 6000 tokens
        max_chars = 24000
        if len(combined_text) > max_chars:
            combined_text = combined_text[:max_chars] + "\n\n[... truncated ...]"

        # Generate summary via Ollama
        prompt = _SUMMARY_PROMPT.format(text=combined_text)
        response_text = asyncio.get_event_loop().run_until_complete(
            _async_generate(prompt)
        )

        # Parse JSON response
        summary_data = _parse_summary_response(response_text)

        # Save to database
        _save_summary(source_id, summary_data)

        logger.info("Summarisation complete for source %s", source_id)
        return {
            "source_id": source_id,
            "status": "completed",
            "has_executive_summary": bool(summary_data.get("executive_summary")),
            "key_findings_count": len(summary_data.get("key_findings", [])),
        }

    except Exception as exc:
        logger.error("Summarisation failed for %s: %s", source_id, exc, exc_info=True)

        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)

        # Log to DLQ
        from app.worker.dlq import handle_dlq
        handle_dlq(source_id, str(exc), traceback.format_exc())

        return {
            "source_id": source_id,
            "status": "failed",
            "error": str(exc),
        }


# ── Internal Helpers ────────────────────────────────────────────────────────


async def _async_generate(prompt: str) -> str:
    """Run the Ollama generate call asynchronously."""
    from app.infrastructure.ollama.client import generate
    return await generate(prompt)


def _get_source_record(source_id: str) -> dict:
    """Fetch source record from the database."""
    from sqlalchemy import create_engine, select as sa_select
    from sqlalchemy.orm import sessionmaker
    from app.infrastructure.db.models import Source

    settings = get_settings()
    sync_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(sync_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        result = session.execute(
            sa_select(Source).where(Source.id == uuid.UUID(source_id))
        )
        source = result.scalar_one_or_none()
        if source is None:
            raise ValueError(f"Source not found: {source_id}")
        return {
            "id": str(source.id),
            "notebook_id": str(source.notebook_id),
            "name": source.name,
        }
    finally:
        session.close()
        engine.dispose()


def _parse_summary_response(response_text: str) -> dict:
    """Parse the LLM response as JSON, with fallback extraction.

    The model should return pure JSON, but we handle cases where it
    wraps the JSON in markdown code fences or adds preamble text.
    """
    text = response_text.strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from code fences
    import re
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try finding JSON object boundaries
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    # Fallback: return raw text as executive summary
    logger.warning("Could not parse summary JSON, using raw text as executive summary")
    return {
        "executive_summary": text,
        "key_findings": [],
        "important_entities": {"people": [], "organisations": [], "concepts": []},
        "suggested_questions": [],
    }


def _save_summary(source_id: str, summary_data: dict) -> None:
    """Save the generated summary to the database."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.infrastructure.db.models import SourceSummary

    settings = get_settings()
    sync_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(sync_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        summary = SourceSummary(
            source_id=uuid.UUID(source_id),
            executive_summary=summary_data.get("executive_summary"),
            key_findings=summary_data.get("key_findings", []),
            entities=summary_data.get("important_entities", {}),
            suggested_questions=summary_data.get("suggested_questions", []),
        )
        session.add(summary)
        session.commit()
        logger.info("Saved summary for source %s", source_id)
    finally:
        session.close()
        engine.dispose()
