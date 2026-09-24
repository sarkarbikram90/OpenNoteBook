"""OpenNotebook — Unit tests for the document chunker.

Validates semantic chunking, short-document preservation (preventing silent data loss),
small chunk consolidation, and overlap calculation.
"""

from __future__ import annotations

import pytest

from app.domain.sources.chunker import (
    MIN_TOKENS,
    TARGET_TOKENS,
    Chunk,
    _apply_overlap,
    _consolidate_small_chunks,
    _count_tokens,
    chunk_document,
)
from app.domain.sources.extractor import ExtractionResult, PageContent


class TestChunkerUnit:
    """Unit tests for semantic chunking logic."""

    def test_short_document_is_preserved_not_dropped(self) -> None:
        """Documents with fewer than MIN_TOKENS (150) MUST be preserved."""
        short_text = "Executive Summary: Q3 revenue grew by 15% year-over-year to $4.2M."
        extraction = ExtractionResult(
            text=short_text,
            metadata={"title": "Short Memo"},
            pages=[PageContent(page_number=1, text=short_text)],
        )

        chunks = chunk_document(
            extraction=extraction,
            source_id="src-123",
            notebook_id="nb-456",
        )

        assert len(chunks) == 1
        assert chunks[0].text == short_text
        assert chunks[0].source_id == "src-123"
        assert chunks[0].notebook_id == "nb-456"
        assert chunks[0].page == 1

    def test_empty_extraction_returns_empty_chunks(self) -> None:
        """Empty documents return an empty list."""
        extraction = ExtractionResult(text="", metadata={}, pages=[])
        chunks = chunk_document(extraction, source_id="src-1", notebook_id="nb-1")
        assert chunks == []

    def test_consolidate_small_chunks_merges_trailing_fragments(self) -> None:
        """Small chunks below MIN_TOKENS are merged into previous chunks."""
        c1 = Chunk(
            chunk_id="c1",
            source_id="src-1",
            notebook_id="nb-1",
            text="First substantial chunk containing plenty of words to exceed the minimum threshold." * 5,
            token_count=200,
            page=1,
            start_char=0,
            end_char=500,
        )
        c2 = Chunk(
            chunk_id="c2",
            source_id="src-1",
            notebook_id="nb-1",
            text="Short concluding remark.",
            token_count=10,
            page=1,
            start_char=501,
            end_char=525,
        )

        consolidated = _consolidate_small_chunks([c1, c2])

        assert len(consolidated) == 1
        assert "Short concluding remark." in consolidated[0].text
        # token_count is recomputed from the merged text, not summed from inputs.
        assert consolidated[0].token_count == _count_tokens(consolidated[0].text)
        assert consolidated[0].token_count > c2.token_count

    def test_token_counting_ratio(self) -> None:
        """Token count estimates approximate BPE token counts from words."""
        text = "Hello world from OpenNotebook test suite."
        tokens = _count_tokens(text)
        # 6 words * 1.33 ≈ 7-8 tokens
        assert 6 <= tokens <= 10

    def test_chunk_ids_are_deterministic(self) -> None:
        """Re-chunking the same document yields identical chunk IDs (idempotent upserts)."""
        import uuid as _uuid

        text = "Paragraph one about transformers and attention.\n\nParagraph two about embeddings."
        extraction = ExtractionResult(
            text=text,
            metadata={},
            pages=[PageContent(page_number=1, text=text)],
        )

        first = chunk_document(extraction, source_id="src-1", notebook_id="nb-1")
        second = chunk_document(extraction, source_id="src-1", notebook_id="nb-1")
        other = chunk_document(extraction, source_id="src-2", notebook_id="nb-1")

        assert [c.chunk_id for c in first] == [c.chunk_id for c in second]
        assert [c.chunk_id for c in first] != [c.chunk_id for c in other]

        # Chunk IDs must remain valid UUIDs (Qdrant point IDs).
        for chunk in first:
            _uuid.UUID(chunk.chunk_id)
