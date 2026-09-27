"""OpenNotebook — Enterprise RAG Agent Orchestrator.

Provides:
1. Intent classification (Document Search, Workspace Synthesis, Conversational)
2. Strict grounded prompt construction with anti-hallucination guardrails
3. Verifiable source attribution and citation formatting
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.domain.retrieval.retriever import RetrievedChunk

logger = logging.getLogger(__name__)


class QueryIntent(str, Enum):
    """Categorization of user message intent."""

    DOCUMENT_SEARCH = "document_search"
    WORKSPACE_SYNTHESIS = "workspace_synthesis"
    CONVERSATIONAL = "conversational"


@dataclass
class VerifiedCitation:
    """Attribution metadata for a source chunk used in generation."""

    source_id: str
    source_name: str
    page: int | None
    section: str | None
    chunk_id: str
    sensitivity_level: str
    relevance_score: float
    snippet: str = ""

    def format_citation(self) -> str:
        """Format human-readable citation label."""
        loc = f"p. {self.page}" if self.page else (self.section or "excerpt")
        return f"[{self.source_name} — {loc}]"


class IntentClassifier:
    """Fast rule-based intent router for enterprise serving."""

    CONVERSATIONAL_PATTERNS = [
        re.compile(r"^(hi|hello|hey|good morning|good afternoon|how are you|who are you|thanks|thank you)\b", re.IGNORECASE),
        re.compile(r"^(what can you do|help me|what are your capabilities)\??$", re.IGNORECASE),
    ]

    SYNTHESIS_PATTERNS = [
        re.compile(r"\b(compare|contrast|synthesize|summarize all|across all|overview of all)\b", re.IGNORECASE),
        re.compile(r"\b(all documents|entire workspace|every source)\b", re.IGNORECASE),
    ]

    @classmethod
    def classify(cls, query: str) -> QueryIntent:
        """Determine whether the query is conversational, single-doc, or cross-doc synthesis."""
        clean = query.strip()
        for pat in cls.CONVERSATIONAL_PATTERNS:
            if pat.search(clean):
                return QueryIntent.CONVERSATIONAL

        for pat in cls.SYNTHESIS_PATTERNS:
            if pat.search(clean):
                return QueryIntent.WORKSPACE_SYNTHESIS

        return QueryIntent.DOCUMENT_SEARCH


class GroundedPromptBuilder:
    """Constructs prompt templates enforcing strict source grounding and citations."""

    ENTERPRISE_SYSTEM_DIRECTIVE = (
        "You are OpenNotebook, a secure enterprise research assistant. "
        "Your task is to answer the user's inquiry strictly and accurately based on the provided context.\n\n"
        "MANDATORY ENTERPRISE GUARDRAILS:\n"
        "1. Base your answer ONLY on the provided source excerpts below.\n"
        "2. If the context does not contain sufficient facts to answer the question, state: "
        "\"I do not have sufficient information in the provided enterprise sources to answer this question.\" "
        "Do NOT speculate, assume, or extrapolate beyond the text.\n"
        "3. Provide inline citations citing the source and page whenever stating facts, e.g. [Source: Filename, Page: X].\n"
        "4. Respect confidentiality classifications indicated in brackets."
    )

    @classmethod
    def build_prompt(
        cls,
        query: str,
        chunks: list[RetrievedChunk],
        history_messages: list[dict[str, str]] | None = None,
    ) -> tuple[str, list[VerifiedCitation]]:
        """Construct grounded prompt string and extract citations.

        Args:
            query: User's query.
            chunks: Retrieved and authorized chunks.
            history_messages: Prior conversation turns.

        Returns:
            Tuple of (formatted_prompt, list_of_citations).
        """
        citations: list[VerifiedCitation] = []
        context_parts: list[str] = []

        for i, chunk in enumerate(chunks, 1):
            citation = VerifiedCitation(
                source_id=chunk.source_id,
                source_name=chunk.source_name,
                page=chunk.page,
                section=chunk.section,
                chunk_id=chunk.chunk_id,
                sensitivity_level=chunk.sensitivity_level,
                relevance_score=chunk.relevance_score,
                snippet=(chunk.text.strip()[:240] + "...") if len(chunk.text.strip()) > 240 else chunk.text.strip(),
            )
            citations.append(citation)

            loc = f"Page {chunk.page}" if chunk.page is not None else (chunk.section or "Excerpt")
            sens = f"Classification: {chunk.sensitivity_level.upper()}"
            header = f"--- [DOCUMENT {i}: {chunk.source_name} | {loc} | {sens}] ---"
            context_parts.append(f"{header}\n{chunk.text.strip()}\n")

        context_str = "\n".join(context_parts) if context_parts else "No relevant enterprise source excerpts found."

        history_str = ""
        if history_messages:
            h_lines = []
            for m in history_messages:
                h_lines.append(f"{m.get('role', 'user').title()}: {m.get('content', '')}")
            history_str = "\nConversation History:\n" + "\n".join(h_lines) + "\n"

        prompt = (
            f"{cls.ENTERPRISE_SYSTEM_DIRECTIVE}\n\n"
            f"{history_str}\n"
            f"ENTERPRISE CONTEXT:\n{context_str}\n\n"
            f"USER INQUIRY: {query}\n\n"
            f"GROUNDED ANSWER:"
        )

        return prompt, citations
