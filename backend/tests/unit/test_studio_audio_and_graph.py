"""Unit tests for Studio Audio Overviews and Knowledge Graph / GraphRAG traversal."""

from __future__ import annotations

from app.domain.studio.audio_overview import (
    build_dialogue_prompt,
    build_fallback_script,
    parse_dialogue_script,
)
from app.domain.studio.knowledge_graph import (
    build_notebook_knowledge_graph,
    extract_phrases_from_text,
)


def test_audio_overview_prompt_and_json_parsing() -> None:
    """Verify prompt construction and fenced-JSON dialogue parsing."""
    excerpts = [
        ("architecture.pdf", "OpenNotebook accelerates PII redaction by 16.9x with Rust DFA."),
        ("storage.md", "GCS V4 Signed URLs allow direct browser uploads without proxying bytes."),
    ]
    prompt = build_dialogue_prompt(
        "Systems Research",
        excerpts,
        focus_topic="Rust performance",
        tone="debate",
    )
    assert "Systems Research" in prompt
    assert "Rust performance" in prompt
    assert "architecture.pdf" in prompt

    raw_llm_json = """```json
    {
      "title": "Rust vs Python Data Plane",
      "summary": "Alex and Sam unpack the 16.9x DFA PII speedup.",
      "turns": [
        {"speaker": "Alex", "text": "Look at architecture.pdf — 16.9x faster PII scrubbing!"},
        {"speaker": "Sam", "text": "Right, and storage.md pairs that with direct GCS signed URLs."}
      ]
    }
    ```"""
    script = parse_dialogue_script(raw_llm_json, "Systems Research", excerpts, tone="debate")
    assert script.title == "Rust vs Python Data Plane"
    assert len(script.turns) == 2
    assert script.turns[0].speaker == "Alex"
    assert script.turns[1].speaker == "Sam"
    assert script.estimated_duration_seconds >= 15


def test_audio_overview_line_parser_and_fallback() -> None:
    """Verify transcript-line fallback and deterministic extractive fallback."""
    excerpts = [("paper.pdf", "Transformers rely on self-attention. Multi-head attention scales well.")]
    transcript = "Alex: Welcome to our briefing!\nSam: Let's look at Transformers in paper.pdf."
    parsed = parse_dialogue_script(transcript, "ML Papers", excerpts)
    assert len(parsed.turns) == 2
    assert parsed.turns[0].speaker == "Alex"

    fallback = build_fallback_script("ML Papers", excerpts, focus_topic="Attention", tone="brief")
    assert "Attention" in fallback.title
    assert len(fallback.turns) >= 4


def test_knowledge_graph_construction_and_graphrag_traversal() -> None:
    """Verify entity extraction, cross-source edges, and 1-hop GraphRAG traversal."""
    sources = [
        {"id": "s1", "name": "rust-accel.pdf"},
        {"id": "s2", "name": "cloudrun-gcs.md"},
    ]
    summaries = [
        {
            "source_id": "s1",
            "entities": {
                "people": ["Bikram Sarkar"],
                "organisations": ["OpenNotebook"],
                "concepts": ["PyO3", "BM25"],
            },
        }
    ]
    chunks = [
        {
            "source_id": "s1",
            "text": "OpenNotebook uses PyO3 and Rust Core for BM25 inverted index scoring.",
        },
        {
            "source_id": "s2",
            "text": "Google Cloud Run pairs with OpenNotebook and Vertex AI Embeddings.",
        },
    ]

    phrases = extract_phrases_from_text(chunks[0]["text"])
    assert "OpenNotebook" in phrases or "Rust Core" in phrases

    graph = build_notebook_knowledge_graph(
        sources=sources,
        summaries=summaries,
        chunks=chunks,
        query="PyO3",
    )
    assert graph.stats["sources"] == 2
    assert graph.stats["entities"] >= 3
    assert graph.stats["total_edges"] >= 3

    node_ids = {n.id for n in graph.nodes}
    assert "source:s1" in node_ids
    assert "organization:opennotebook" in node_ids
    assert "concept:pyo3" in node_ids

    # GraphRAG 1-hop traversal from "PyO3" should include concept:pyo3 and its source:s1 neighbor
    assert "concept:pyo3" in graph.matched_node_ids
    assert "source:s1" in graph.matched_node_ids
