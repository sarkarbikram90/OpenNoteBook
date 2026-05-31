"""OpenNotebook — Semantic chunker with sliding window fallback.

Implements the spec:
- Target chunk size:   800 tokens
- Overlap:             100 tokens
- Minimum chunk size:  150 tokens
- Split on:            paragraph > sentence > token boundary

Token counting uses whitespace word count (1 word ≈ 1.3 tokens on average
for English text with BPE tokenisers).  This avoids a ``tiktoken`` dependency
since we use a local embedding model.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.domain.sources.extractor import ExtractionResult, PageContent

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────────────

TARGET_TOKENS = 800
OVERLAP_TOKENS = 100
MIN_TOKENS = 150

# Approx word-to-token ratio for English BPE tokenisers
_WORD_TO_TOKEN_RATIO = 1.33


# ── Data Structures ─────────────────────────────────────────────────────────


@dataclass
class Chunk:
    """A single text chunk with full metadata."""

    chunk_id: str
    source_id: str
    notebook_id: str
    text: str
    token_count: int
    page: int | None = None
    section: str | None = None
    start_char: int = 0
    end_char: int = 0
    embedding_model: str = ""


# ── Public API ──────────────────────────────────────────────────────────────


def chunk_document(
    extraction: ExtractionResult,
    source_id: str,
    notebook_id: str,
    embedding_model: str = "BAAI/bge-small-en-v1.5",
) -> list[Chunk]:
    """Split an extracted document into semantic chunks.

    Strategy:
    1. Split text into paragraphs.
    2. Merge paragraphs until approaching the target token count.
    3. If a single paragraph exceeds the target, split on sentences.
    4. If a single sentence exceeds the target, split on token boundaries.
    5. Apply sliding window overlap between consecutive chunks.

    Args:
        extraction: The extraction result containing full text, pages, and metadata.
        source_id: UUID of the source document.
        notebook_id: UUID of the owning notebook.
        embedding_model: Name of the embedding model (stored in chunk metadata).

    Returns:
        List of Chunk objects ready for embedding.
    """
    chunks: list[Chunk] = []

    if extraction.pages:
        # Process page by page to preserve page numbers
        for page in extraction.pages:
            page_chunks = _chunk_text(
                text=page.text,
                source_id=source_id,
                notebook_id=notebook_id,
                page=page.page_number,
                section=page.section,
                embedding_model=embedding_model,
            )
            chunks.extend(page_chunks)
    else:
        # Fallback: chunk the full text without page info
        chunks = _chunk_text(
            text=extraction.text,
            source_id=source_id,
            notebook_id=notebook_id,
            page=None,
            section=None,
            embedding_model=embedding_model,
        )

    # Apply overlap between consecutive chunks
    chunks = _apply_overlap(chunks)

    # Filter out chunks below minimum size
    chunks = [c for c in chunks if c.token_count >= MIN_TOKENS]

    logger.info(
        "Chunked document into %d chunks (source=%s)",
        len(chunks),
        source_id,
    )
    return chunks


# ── Internal Helpers ────────────────────────────────────────────────────────


def _count_tokens(text: str) -> int:
    """Estimate token count from word count."""
    words = len(text.split())
    return int(words * _WORD_TO_TOKEN_RATIO)


def _split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs on double newlines."""
    paragraphs = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paragraphs if p.strip()]


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences using a simple regex."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip()]


def _split_by_tokens(text: str, max_tokens: int) -> list[str]:
    """Split text into fixed-size token chunks as a last resort."""
    words = text.split()
    # Convert max_tokens back to approx word count
    max_words = int(max_tokens / _WORD_TO_TOKEN_RATIO)
    if max_words < 1:
        max_words = 1

    result = []
    for i in range(0, len(words), max_words):
        chunk_words = words[i : i + max_words]
        result.append(" ".join(chunk_words))
    return result


def _chunk_text(
    text: str,
    source_id: str,
    notebook_id: str,
    page: int | None,
    section: str | None,
    embedding_model: str,
) -> list[Chunk]:
    """Core chunking logic: paragraph-first split with sentence and token fallbacks."""
    if not text.strip():
        return []

    paragraphs = _split_paragraphs(text)
    chunks: list[Chunk] = []
    current_parts: list[str] = []
    current_tokens = 0
    char_offset = 0

    for para in paragraphs:
        para_tokens = _count_tokens(para)

        if para_tokens > TARGET_TOKENS:
            # Flush what we have
            if current_parts:
                chunks.append(_make_chunk(
                    parts=current_parts,
                    source_id=source_id,
                    notebook_id=notebook_id,
                    page=page,
                    section=section,
                    embedding_model=embedding_model,
                    start_char=char_offset,
                ))
                char_offset += sum(len(p) + 2 for p in current_parts)
                current_parts = []
                current_tokens = 0

            # Split this large paragraph into sentences
            sentences = _split_sentences(para)
            sent_parts: list[str] = []
            sent_tokens = 0

            for sent in sentences:
                sent_tok = _count_tokens(sent)

                if sent_tok > TARGET_TOKENS:
                    # Flush accumulated sentences
                    if sent_parts:
                        chunks.append(_make_chunk(
                            parts=sent_parts,
                            source_id=source_id,
                            notebook_id=notebook_id,
                            page=page,
                            section=section,
                            embedding_model=embedding_model,
                            start_char=char_offset,
                        ))
                        char_offset += sum(len(s) + 1 for s in sent_parts)
                        sent_parts = []
                        sent_tokens = 0

                    # Last resort: split by tokens
                    token_chunks = _split_by_tokens(sent, TARGET_TOKENS)
                    for tc in token_chunks:
                        chunks.append(_make_chunk(
                            parts=[tc],
                            source_id=source_id,
                            notebook_id=notebook_id,
                            page=page,
                            section=section,
                            embedding_model=embedding_model,
                            start_char=char_offset,
                        ))
                        char_offset += len(tc) + 1
                elif sent_tokens + sent_tok > TARGET_TOKENS:
                    # Flush sentences
                    if sent_parts:
                        chunks.append(_make_chunk(
                            parts=sent_parts,
                            source_id=source_id,
                            notebook_id=notebook_id,
                            page=page,
                            section=section,
                            embedding_model=embedding_model,
                            start_char=char_offset,
                        ))
                        char_offset += sum(len(s) + 1 for s in sent_parts)
                    sent_parts = [sent]
                    sent_tokens = sent_tok
                else:
                    sent_parts.append(sent)
                    sent_tokens += sent_tok

            # Flush remaining sentences
            if sent_parts:
                chunks.append(_make_chunk(
                    parts=sent_parts,
                    source_id=source_id,
                    notebook_id=notebook_id,
                    page=page,
                    section=section,
                    embedding_model=embedding_model,
                    start_char=char_offset,
                ))
                char_offset += sum(len(s) + 1 for s in sent_parts)

        elif current_tokens + para_tokens > TARGET_TOKENS:
            # Flush current chunk
            if current_parts:
                chunks.append(_make_chunk(
                    parts=current_parts,
                    source_id=source_id,
                    notebook_id=notebook_id,
                    page=page,
                    section=section,
                    embedding_model=embedding_model,
                    start_char=char_offset,
                ))
                char_offset += sum(len(p) + 2 for p in current_parts)
            current_parts = [para]
            current_tokens = para_tokens
        else:
            current_parts.append(para)
            current_tokens += para_tokens

    # Flush remaining
    if current_parts:
        chunks.append(_make_chunk(
            parts=current_parts,
            source_id=source_id,
            notebook_id=notebook_id,
            page=page,
            section=section,
            embedding_model=embedding_model,
            start_char=char_offset,
        ))

    return chunks


def _make_chunk(
    parts: list[str],
    source_id: str,
    notebook_id: str,
    page: int | None,
    section: str | None,
    embedding_model: str,
    start_char: int,
) -> Chunk:
    """Assemble a Chunk object from text parts."""
    text = "\n\n".join(parts)
    return Chunk(
        chunk_id=str(uuid.uuid4()),
        source_id=source_id,
        notebook_id=notebook_id,
        text=text,
        token_count=_count_tokens(text),
        page=page,
        section=section,
        start_char=start_char,
        end_char=start_char + len(text),
        embedding_model=embedding_model,
    )


def _apply_overlap(chunks: list[Chunk]) -> list[Chunk]:
    """Add overlap text from the previous chunk to each chunk.

    The overlap is taken from the *end* of the previous chunk and prepended
    to the *start* of the current chunk.  This ensures retrieval context
    spans across chunk boundaries.
    """
    if len(chunks) <= 1:
        return chunks

    overlap_words = int(OVERLAP_TOKENS / _WORD_TO_TOKEN_RATIO)
    result = [chunks[0]]

    for i in range(1, len(chunks)):
        prev_words = chunks[i - 1].text.split()
        overlap_text = " ".join(prev_words[-overlap_words:]) if len(prev_words) > overlap_words else " ".join(prev_words)

        new_text = overlap_text + "\n\n" + chunks[i].text
        result.append(Chunk(
            chunk_id=chunks[i].chunk_id,
            source_id=chunks[i].source_id,
            notebook_id=chunks[i].notebook_id,
            text=new_text,
            token_count=_count_tokens(new_text),
            page=chunks[i].page,
            section=chunks[i].section,
            start_char=chunks[i].start_char,
            end_char=chunks[i].end_char,
            embedding_model=chunks[i].embedding_model,
        ))

    return result
