"""Unit tests for the Rust `opennotebook_core` PyO3 bridge and Python fallback."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.domain.governance.pii import MaskingStrategy, PIIScrubber
from app.domain.sources.chunker import chunk_document
from app.domain.sources.extractor import ExtractionResult, PageContent
from app.infrastructure import rust_accel


def test_pii_scrubber_uses_rust_core_when_available(monkeypatch: pytest.MonkeyPatch):
    """When opennotebook_core is loaded, PIIScrubber delegates directly to Rust."""
    fake_core = SimpleNamespace(
        scrub_pii=lambda text, strategy: (
            f"[RUST:{strategy}]{text}",
            {"EMAIL": 2},
            2,
        )
    )
    monkeypatch.setattr(rust_accel, "_rust_core", fake_core)

    scrubber = PIIScrubber(default_strategy=MaskingStrategy.REDACT)
    res = scrubber.scrub("alice@example.com bob@example.com")
    assert res.cleaned_text.startswith("[RUST:redact]")
    assert res.entities_found == {"EMAIL": 2}
    assert res.total_redacted == 2


def test_chunker_uses_rust_core_when_available(monkeypatch: pytest.MonkeyPatch):
    """When opennotebook_core is loaded, chunk_document delegates to rust_chunk_pages."""
    fake_core = SimpleNamespace(
        chunk_pages=lambda source_id, notebook_id, embedding_model, pages, *_args: [
            {
                "chunk_id": "rust-chunk-1",
                "source_id": source_id,
                "notebook_id": notebook_id,
                "text": pages[0][1],
                "token_count": 10,
                "page": pages[0][0],
                "section": pages[0][2],
                "start_char": 0,
                "end_char": len(pages[0][1]),
                "embedding_model": embedding_model,
            }
        ]
    )
    monkeypatch.setattr(rust_accel, "_rust_core", fake_core)
    monkeypatch.setattr(
        "app.domain.sources.tokenization.encoding_name",
        lambda: "word-heuristic",
    )

    extraction = ExtractionResult(
        text="Google Cloud Storage and Rust PyO3 acceleration.",
        pages=[
            PageContent(
                page_number=1,
                text="Google Cloud Storage and Rust PyO3 acceleration.",
                section="Architecture",
            )
        ],
    )
    chunks = chunk_document(
        extraction=extraction,
        source_id="src-1",
        notebook_id="nb-1",
        embedding_model="text-embedding-004",
        allowed_roles=["admin"],
    )
    assert len(chunks) == 1
    assert chunks[0].chunk_id == "rust-chunk-1"
    assert chunks[0].allowed_roles == ["admin"]


def test_bm25_rust_bridge_build_and_score(monkeypatch: pytest.MonkeyPatch):
    """Verify rust_build_bm25_index_json and rust_score_bm25_index_json bridge calls."""
    fake_core = SimpleNamespace(
        build_bm25_index_json=lambda cids, texts: f'{{"count": {len(cids)}, "texts": {len(texts)}}}',
        score_bm25_index_json=lambda idx_json, query, top_k: [
            ("chunk-1", 4.25),
            (f"chunk-{top_k}:{len(idx_json)}:{len(query)}", 1.5),
        ],
    )
    monkeypatch.setattr(rust_accel, "_rust_core", fake_core)

    assert rust_accel.is_rust_available() is True
    idx_json = rust_accel.rust_build_bm25_index_json(["chunk-1"], ["hello rust"])
    assert idx_json == '{"count": 1, "texts": 1}'

    hits = rust_accel.rust_score_bm25_index_json(idx_json, "rust", top_k=5)
    assert hits is not None
    assert hits[0] == ("chunk-1", 4.25)
