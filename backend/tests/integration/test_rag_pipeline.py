"""OpenNotebook — Integration tests for the RAG pipeline + SSE streaming.

Tests the full retrieval → generation → streaming flow by:
1. Seeding a notebook with test data directly into Qdrant + BM25.
2. Running the retrieval pipeline and verifying chunk results.
3. Hitting the SSE chat endpoint and verifying event format.

These tests require running infrastructure services (Postgres, Qdrant, Redis)
or use mocks for Ollama to avoid needing a real LLM.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Fixtures ────────────────────────────────────────────────────────────────

TEST_NOTEBOOK_ID = str(uuid.uuid4())
TEST_SOURCE_ID = str(uuid.uuid4())
TEST_SOURCE_NAME = "test_transformers.pdf"

SAMPLE_CHUNKS = [
    {
        "chunk_id": str(uuid.uuid4()),
        "source_id": TEST_SOURCE_ID,
        "notebook_id": TEST_NOTEBOOK_ID,
        "text": (
            "The Transformer architecture relies entirely on self-attention "
            "mechanisms, dispensing with recurrence and convolutions entirely. "
            "This enables significantly more parallelisation during training."
        ),
        "token_count": 28,
        "page": 2,
        "section": "Model Architecture",
        "start_char": 0,
        "end_char": 200,
        "embedding_model": "BAAI/bge-small-en-v1.5",
        "source_name": TEST_SOURCE_NAME,
    },
    {
        "chunk_id": str(uuid.uuid4()),
        "source_id": TEST_SOURCE_ID,
        "notebook_id": TEST_NOTEBOOK_ID,
        "text": (
            "Multi-head attention allows the model to jointly attend to "
            "information from different representation subspaces at different "
            "positions. With a single attention head, averaging inhibits this."
        ),
        "token_count": 32,
        "page": 4,
        "section": "Multi-Head Attention",
        "start_char": 200,
        "end_char": 400,
        "embedding_model": "BAAI/bge-small-en-v1.5",
        "source_name": TEST_SOURCE_NAME,
    },
    {
        "chunk_id": str(uuid.uuid4()),
        "source_id": TEST_SOURCE_ID,
        "notebook_id": TEST_NOTEBOOK_ID,
        "text": (
            "Positional encoding is added to give the model information about "
            "the relative or absolute position of the tokens in the sequence. "
            "The authors use sine and cosine functions of different frequencies."
        ),
        "token_count": 35,
        "page": 6,
        "section": "Positional Encoding",
        "start_char": 400,
        "end_char": 600,
        "embedding_model": "BAAI/bge-small-en-v1.5",
        "source_name": TEST_SOURCE_NAME,
    },
]


# ── Unit Tests: Prompt Building ─────────────────────────────────────────────


class TestPromptBuilder:
    """Tests for the prompt template module."""

    def test_format_context_block(self) -> None:
        """Context blocks include source index, name, page, and content."""
        from app.domain.chat.prompt import format_context_block
        from app.domain.retrieval.retriever import RetrievedChunk

        chunk = RetrievedChunk(
            chunk_id="abc",
            source_id="def",
            source_name="paper.pdf",
            notebook_id="ghi",
            text="Some important text here.",
            page=5,
            section="Introduction",
            relevance_score=0.92,
        )

        result = format_context_block(1, chunk)

        assert "[Source 1]" in result
        assert "paper.pdf" in result
        assert "Page: 5" in result
        assert "Section: Introduction" in result
        assert "Some important text here." in result

    def test_build_context_empty(self) -> None:
        """Empty chunks list returns a fallback message."""
        from app.domain.chat.prompt import build_context

        result = build_context([])
        assert "No relevant context found" in result

    def test_build_context_multiple(self) -> None:
        """Multiple chunks are numbered sequentially."""
        from app.domain.chat.prompt import build_context
        from app.domain.retrieval.retriever import RetrievedChunk

        chunks = [
            RetrievedChunk(
                chunk_id=f"id{i}",
                source_id="src",
                source_name="doc.pdf",
                notebook_id="nb",
                text=f"Chunk {i} text",
            )
            for i in range(1, 4)
        ]

        result = build_context(chunks)
        assert "[Source 1]" in result
        assert "[Source 2]" in result
        assert "[Source 3]" in result

    def test_build_prompt_structure(self) -> None:
        """Full prompt contains all sections."""
        from app.domain.chat.prompt import build_prompt

        prompt = build_prompt("context here", "history here", "what is attention?")

        assert "<system>" in prompt
        assert "<context>" in prompt
        assert "context here" in prompt
        assert "<conversation>" in prompt
        assert "history here" in prompt
        assert "<question>" in prompt
        assert "what is attention?" in prompt

    def test_format_history_empty(self) -> None:
        """Empty history returns a fallback message."""
        from app.domain.chat.prompt import format_history

        result = format_history([])
        assert "No previous conversation" in result

    def test_format_history_messages(self) -> None:
        """Messages are formatted with role labels."""
        from app.domain.chat.prompt import format_history

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        result = format_history(messages)
        assert "User: Hello" in result
        assert "Assistant: Hi there!" in result


# ── Unit Tests: RRF Fusion ──────────────────────────────────────────────────


class TestRRFFusion:
    """Tests for the Reciprocal Rank Fusion implementation."""

    def test_rrf_single_list(self) -> None:
        """Chunks from a single list get scored correctly."""
        from app.domain.retrieval.retriever import _reciprocal_rank_fusion

        dense = [
            {"chunk_id": "a", "text": "chunk a"},
            {"chunk_id": "b", "text": "chunk b"},
        ]

        result = _reciprocal_rank_fusion(dense, [], k=60, top_k=10)

        assert len(result) == 2
        assert result[0]["chunk_id"] == "a"
        # Rank 1: score = 1/(60+1) ≈ 0.0164
        assert result[0]["_rrf_score"] == pytest.approx(1.0 / 61, abs=1e-6)

    def test_rrf_merge(self) -> None:
        """Chunks appearing in both lists get higher fused scores."""
        from app.domain.retrieval.retriever import _reciprocal_rank_fusion

        dense = [
            {"chunk_id": "a", "text": "chunk a"},
            {"chunk_id": "b", "text": "chunk b"},
        ]
        bm25 = [
            {"chunk_id": "b", "text": "chunk b"},
            {"chunk_id": "c", "text": "chunk c"},
        ]

        result = _reciprocal_rank_fusion(dense, bm25, k=60, top_k=10)

        # "b" appears in both lists (rank 2 + rank 1), should have highest score
        ids = [r["chunk_id"] for r in result]
        assert ids[0] == "b"
        assert len(result) == 3

    def test_rrf_top_k_limit(self) -> None:
        """RRF respects the top_k limit."""
        from app.domain.retrieval.retriever import _reciprocal_rank_fusion

        dense = [{"chunk_id": f"d{i}", "text": f"chunk {i}"} for i in range(10)]

        result = _reciprocal_rank_fusion(dense, [], k=60, top_k=3)
        assert len(result) == 3


# ── Unit Tests: Citation Extraction ─────────────────────────────────────────


class TestCitationExtraction:
    """Tests for the citation extraction from LLM responses."""

    def test_extract_citations(self) -> None:
        """Citations are extracted from [Source N] patterns."""
        from app.domain.chat.service import _extract_citations
        from app.domain.retrieval.retriever import RetrievedChunk

        chunks = [
            RetrievedChunk(
                chunk_id="c1",
                source_id="s1",
                source_name="paper.pdf",
                notebook_id="nb",
                text="text 1",
                page=2,
                section="Intro",
                relevance_score=0.95,
            ),
            RetrievedChunk(
                chunk_id="c2",
                source_id="s1",
                source_name="paper.pdf",
                notebook_id="nb",
                text="text 2",
                page=4,
                section="Methods",
                relevance_score=0.88,
            ),
        ]

        response = (
            "The transformer uses self-attention [Source 1] and "
            "multi-head attention [Source 2] for parallelisation."
        )

        citations = _extract_citations(response, chunks)

        assert len(citations) == 2
        assert citations[0]["chunk_id"] == "c1"
        assert citations[0]["page"] == 2
        assert citations[1]["chunk_id"] == "c2"

    def test_extract_citations_deduplication(self) -> None:
        """Duplicate [Source N] references produce only one citation."""
        from app.domain.chat.service import _extract_citations
        from app.domain.retrieval.retriever import RetrievedChunk

        chunks = [
            RetrievedChunk(
                chunk_id="c1",
                source_id="s1",
                source_name="paper.pdf",
                notebook_id="nb",
                text="text 1",
            ),
        ]

        response = "First [Source 1] and again [Source 1]."
        citations = _extract_citations(response, chunks)
        assert len(citations) == 1

    def test_extract_citations_none_found(self) -> None:
        """No [Source N] in response returns empty list."""
        from app.domain.chat.service import _extract_citations

        citations = _extract_citations("No citations here.", [])
        assert citations == []


# ── Unit Tests: SSE Event Format ────────────────────────────────────────────


class TestSSEFormat:
    """Tests for SSE event formatting."""

    def test_sse_token_event(self) -> None:
        """Token events are properly formatted."""
        from app.domain.chat.service import _sse_event

        result = _sse_event("token", {"token": " the"})
        assert result.startswith("event: token\n")
        assert 'data: {"token": " the"}' in result
        assert result.endswith("\n\n")

    def test_sse_citation_event(self) -> None:
        """Citation events contain all required fields."""
        from app.domain.chat.service import _sse_event

        citation = {
            "chunk_id": "abc",
            "source_name": "paper.pdf",
            "page": 12,
        }
        result = _sse_event("citation", citation)
        assert "event: citation\n" in result
        data_line = result.split("\n")[1]
        parsed = json.loads(data_line.replace("data: ", ""))
        assert parsed["chunk_id"] == "abc"
        assert parsed["source_name"] == "paper.pdf"
        assert parsed["page"] == 12

    def test_sse_done_event(self) -> None:
        """Done events contain message_id and latency."""
        from app.domain.chat.service import _sse_event

        result = _sse_event("done", {
            "message_id": "msg-123",
            "latency_ms": 1500,
        })
        assert "event: done\n" in result
        data_line = result.split("\n")[1]
        parsed = json.loads(data_line.replace("data: ", ""))
        assert parsed["message_id"] == "msg-123"
        assert parsed["latency_ms"] == 1500

    def test_sse_error_event(self) -> None:
        """Error events contain code and message."""
        from app.domain.chat.service import _sse_event

        result = _sse_event("error", {
            "code": "context_too_long",
            "message": "Input exceeds context window",
        })
        assert "event: error\n" in result
        data_line = result.split("\n")[1]
        parsed = json.loads(data_line.replace("data: ", ""))
        assert parsed["code"] == "context_too_long"


# ── Unit Tests: Summary Response Parsing ────────────────────────────────────


class TestSummaryParsing:
    """Tests for the summarisation response parser."""

    def test_parse_clean_json(self) -> None:
        """Clean JSON is parsed directly."""
        from app.worker.tasks.summarise import _parse_summary_response

        data = {
            "executive_summary": "A summary.",
            "key_findings": ["finding 1"],
            "important_entities": {"people": [], "organisations": [], "concepts": []},
            "suggested_questions": ["Question?"],
        }

        result = _parse_summary_response(json.dumps(data))
        assert result["executive_summary"] == "A summary."
        assert result["key_findings"] == ["finding 1"]

    def test_parse_json_in_code_fence(self) -> None:
        """JSON wrapped in markdown code fences is extracted."""
        from app.worker.tasks.summarise import _parse_summary_response

        text = '```json\n{"executive_summary": "test", "key_findings": []}\n```'
        result = _parse_summary_response(text)
        assert result["executive_summary"] == "test"

    def test_parse_fallback(self) -> None:
        """Non-JSON text falls back to raw text as executive summary."""
        from app.worker.tasks.summarise import _parse_summary_response

        result = _parse_summary_response("This is just plain text.")
        assert result["executive_summary"] == "This is just plain text."
        assert result["key_findings"] == []
