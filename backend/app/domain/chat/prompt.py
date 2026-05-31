"""OpenNotebook — RAG prompt template and context assembly.

Provides the system prompt, context block formatter, and prompt builder
that assembles the full prompt sent to the LLM.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.domain.retrieval.retriever import RetrievedChunk

# ── System Prompt ───────────────────────────────────────────────────────────

SYSTEM_PROMPT = """<system>
You are a document research assistant for OpenNotebook.

Rules:
- Answer ONLY using the provided context.
- If the answer is not in the context, say exactly:
  "I could not find that information in this notebook's sources."
- Be concise. Cite sources inline using [Source N] notation.
- Never fabricate citations.
</system>"""


# ── Public API ──────────────────────────────────────────────────────────────


def format_context_block(index: int, chunk: RetrievedChunk) -> str:
    """Format a single retrieved chunk as a numbered context block.

    Args:
        index: 1-based source index for [Source N] citation.
        chunk: The retrieved chunk with metadata.

    Returns:
        Formatted context block string.
    """
    parts = [f"[Source {index}]"]
    parts.append(f"Document: {chunk.source_name}")
    if chunk.page is not None:
        parts.append(f"Page: {chunk.page}")
    if chunk.section:
        parts.append(f"Section: {chunk.section}")
    parts.append(f"Content: {chunk.text}")
    return "\n".join(parts)


def build_context(chunks: list[RetrievedChunk]) -> str:
    """Build the full context section from retrieved chunks.

    Args:
        chunks: Ordered list of retrieved chunks.

    Returns:
        Formatted context string with all chunks numbered.
    """
    if not chunks:
        return "No relevant context found."

    blocks = [format_context_block(i, chunk) for i, chunk in enumerate(chunks, start=1)]
    return "\n\n---\n\n".join(blocks)


def format_history(messages: list[dict[str, str]]) -> str:
    """Format conversation history for the prompt.

    Args:
        messages: List of dicts with ``role`` and ``content`` keys.

    Returns:
        Formatted history string.
    """
    if not messages:
        return "No previous conversation."

    lines = []
    for msg in messages:
        role = msg.get("role", "user").capitalize()
        content = msg.get("content", "")
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def build_prompt(
    context_blocks: str,
    history: str,
    question: str,
) -> str:
    """Assemble the full prompt from system prompt, context, history, and question.

    Args:
        context_blocks: Formatted context from ``build_context()``.
        history: Formatted conversation history from ``format_history()``.
        question: The user's current question.

    Returns:
        Complete prompt string ready for the LLM.
    """
    return f"""{SYSTEM_PROMPT}

<context>
{context_blocks}
</context>

<conversation>
{history}
</conversation>

<question>
{question}
</question>"""
