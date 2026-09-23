"""OpenNotebook — Unit tests for RAG Agent Orchestrator."""

from __future__ import annotations

import pytest

from app.domain.chat.orchestrator import (
    GroundedPromptBuilder,
    IntentClassifier,
    QueryIntent,
    VerifiedCitation,
)
from app.domain.retrieval.retriever import RetrievedChunk


def test_intent_classifier():
    """Verify classification of query intent."""
    assert IntentClassifier.classify("Hello! How can you help me?") == QueryIntent.CONVERSATIONAL
    assert IntentClassifier.classify("Who are you?") == QueryIntent.CONVERSATIONAL

    assert IntentClassifier.classify("Compare and synthesize all security policies across all documents") == QueryIntent.WORKSPACE_SYNTHESIS
    assert IntentClassifier.classify("Give me an overview of all findings") == QueryIntent.WORKSPACE_SYNTHESIS

    assert IntentClassifier.classify("What is the maximum PTO rollover permitted?") == QueryIntent.DOCUMENT_SEARCH
    assert IntentClassifier.classify("What did the Q3 financial report state?") == QueryIntent.DOCUMENT_SEARCH


def test_verified_citation_formatting():
    """Verify formatted citation labels."""
    cit_page = VerifiedCitation(
        source_id="s1",
        source_name="Employee_Handbook.pdf",
        page=14,
        section=None,
        chunk_id="c1",
        sensitivity_level="internal",
        relevance_score=0.88,
    )
    assert cit_page.format_citation() == "[Employee_Handbook.pdf — p. 14]"

    cit_section = VerifiedCitation(
        source_id="s2",
        source_name="Security_Spec.md",
        page=None,
        section="Authentication",
        chunk_id="c2",
        sensitivity_level="confidential",
        relevance_score=0.92,
    )
    assert cit_section.format_citation() == "[Security_Spec.md — Authentication]"


def test_grounded_prompt_builder():
    """Verify prompt synthesis adheres to enterprise guardrails."""
    chunks = [
        RetrievedChunk(
            chunk_id="c1",
            source_id="s1",
            source_name="Q3_Earnings.pdf",
            notebook_id="n1",
            text="Q3 revenue reached $45M, representing 32% year-over-year growth.",
            page=3,
            relevance_score=0.95,
            sensitivity_level="confidential",
        ),
    ]

    prompt, citations = GroundedPromptBuilder.build_prompt(
        query="What was our Q3 revenue?",
        chunks=chunks,
        history_messages=[{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello!"}],
    )

    assert "MANDATORY ENTERPRISE GUARDRAILS:" in prompt
    assert "Do NOT speculate, assume, or extrapolate" in prompt
    assert "Q3_Earnings.pdf" in prompt
    assert "Page 3" in prompt
    assert "CONFIDENTIAL" in prompt
    assert len(citations) == 1
    assert citations[0].source_name == "Q3_Earnings.pdf"
