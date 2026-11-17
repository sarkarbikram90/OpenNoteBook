"""Benchmark comparing Pure-Python vs. Compiled Rust (`opennotebook_core`) data-plane hot paths.

Measures p50 latency, p95 latency, throughput, and speedup factor across:
1. Enterprise PII Detection & Redaction (150-page document, ~450 KB)
2. Semantic Document Chunking with Overlap & Consolidation (150 pages)
3. Per-Query BM25 Lexical Retrieval over a 5,000-Chunk Notebook

Usage:
    python -m app.scripts.benchmark_rust_vs_python
"""

from __future__ import annotations

import json
import math
import statistics
import time
from collections import Counter
from collections.abc import Callable

import opennotebook_core

from app.domain.governance.pii import MaskingStrategy, PIIScrubber
from app.domain.sources.chunker import chunk_document
from app.domain.sources.extractor import ExtractionResult, PageContent
from app.infrastructure import rust_accel


class _PurePythonBM25Okapi:
    """Pure-Python BM25Okapi reference matching `rank_bm25.BM25Okapi`."""

    def __init__(self, corpus: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.doc_len: list[int] = []
        self.doc_freqs: list[dict[str, int]] = []
        nd: dict[str, int] = {}
        num_doc = 0
        for document in corpus:
            self.doc_len.append(len(document))
            num_doc += len(document)
            frequencies = dict(Counter(document))
            self.doc_freqs.append(frequencies)
            for word in frequencies:
                nd[word] = nd.get(word, 0) + 1
        self.avgdl = num_doc / self.corpus_size if self.corpus_size else 0.0
        self.idf = {
            word: math.log((self.corpus_size - freq + 0.5) / (freq + 0.5) + 1.0)
            for word, freq in nd.items()
        }

    def get_scores(self, query: list[str]) -> list[float]:
        scores = [0.0] * self.corpus_size
        for q in query:
            q_idf = self.idf.get(q, 0.0)
            if q_idf <= 0.0:
                continue
            for i, doc_freq in enumerate(self.doc_freqs):
                tf = doc_freq.get(q, 0)
                if tf > 0:
                    dl = self.doc_len[i]
                    denom = tf + self.k1 * (1.0 - self.b + self.b * (dl / self.avgdl))
                    scores[i] += q_idf * (tf * (self.k1 + 1.0)) / denom
        return scores


def _percentile(values_ms: list[float], pct: float) -> float:
    if not values_ms:
        return 0.0
    sorted_vals = sorted(values_ms)
    idx = min(len(sorted_vals) - 1, max(0, round((pct / 100.0) * (len(sorted_vals) - 1))))
    return sorted_vals[idx]


def _time_iterations(fn: Callable[[], object], iterations: int, warmup: int = 2) -> list[float]:
    for _ in range(warmup):
        fn()
    timings_ms: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        fn()
        timings_ms.append((time.perf_counter() - t0) * 1000.0)
    return timings_ms


def _build_synthetic_pages(num_pages: int = 150) -> list[PageContent]:
    paragraph_template = (
        "Google Cloud Storage (GCS) serves as the authoritative unstructured object "
        "repository for OpenNoteBook. When a PDF or raster image is uploaded to "
        "gs://opennotebook-prod-uploads/raw/nb-1/src-1/architecture.pdf, Cloud Storage "
        "emits an OBJECT_FINALIZE notification to Google Cloud Pub/Sub. For incident "
        "escalation, contact sre-oncall@enterprise.io or call +1 (415) 890-2341. "
        "Sample customer record SSN 123-45-6789 and billing test card 4532-0151-1283-0366 "
        "with temporary AWS key AKIAIOSFODNN7EXAMPLE must be redacted prior to embedding."
    )
    pages: list[PageContent] = []
    for i in range(1, num_pages + 1):
        page_text = "\n\n".join(f"[Section {i}.{j}] {paragraph_template}" for j in range(1, 7))
        pages.append(
            PageContent(
                page_number=i,
                text=page_text,
                section=f"Architecture Section {i}",
            )
        )
    return pages


def run_benchmark() -> None:
    pages = _build_synthetic_pages(150)
    full_doc_text = "\n\n".join(p.text for p in pages)
    doc_kb = len(full_doc_text.encode("utf-8")) / 1024.0
    extraction = ExtractionResult(text=full_doc_text, pages=pages)

    scrubber = PIIScrubber(default_strategy=MaskingStrategy.REDACT)

    # ── 1. PII Scrubbing Benchmark ─────────────────────────────────────────
    rust_accel._rust_core = None
    py_pii_ms = _time_iterations(lambda: scrubber.scrub(full_doc_text), iterations=12)

    rust_accel._rust_core = opennotebook_core
    rs_pii_ms = _time_iterations(lambda: scrubber.scrub(full_doc_text), iterations=12)

    # ── 2. Semantic Chunking Benchmark (150 pages) ─────────────────────────
    rust_accel._rust_core = None
    py_chunk_ms = _time_iterations(
        lambda: chunk_document(
            extraction=extraction,
            source_id="00000000-0000-0000-0000-000000000001",
            notebook_id="00000000-0000-0000-0000-000000000002",
            embedding_model="text-embedding-004",
        ),
        iterations=12,
    )

    rust_accel._rust_core = opennotebook_core
    rs_chunk_ms = _time_iterations(
        lambda: chunk_document(
            extraction=extraction,
            source_id="00000000-0000-0000-0000-000000000001",
            notebook_id="00000000-0000-0000-0000-000000000002",
            embedding_model="text-embedding-004",
        ),
        iterations=12,
    )

    # ── 3. BM25 Query Scoring Benchmark (5,000 chunks) ─────────────────────
    num_chunks = 5000
    chunk_ids = [f"chunk-{i}" for i in range(num_chunks)]
    chunk_texts = [
        (
            f"Document chunk {i} describing distributed cloud storage latency, "
            f"PostgreSQL pgvector HNSW indexing, Vertex AI text-embedding-004, "
            f"and Pub/Sub OBJECT_FINALIZE idempotency for generation {i}."
        )
        for i in range(num_chunks)
    ]
    tokenised_corpus = [t.lower().split() for t in chunk_texts]
    corpus_json = json.dumps(tokenised_corpus)
    rust_inv_json = opennotebook_core.build_bm25_index_json(chunk_ids, chunk_texts)
    query = "Pub/Sub OBJECT_FINALIZE idempotency and pgvector HNSW latency"

    def _python_bm25_query() -> list[tuple[str, float]]:
        loaded_corpus = json.loads(corpus_json)
        bm25 = _PurePythonBM25Okapi(loaded_corpus)
        scores = bm25.get_scores(query.lower().split())
        pairs = [(cid, sc) for cid, sc in zip(chunk_ids, scores) if sc > 0]
        pairs.sort(key=lambda p: p[1], reverse=True)
        return pairs[:20]

    def _rust_bm25_query() -> list[tuple[str, float]]:
        return opennotebook_core.score_bm25_index_json(rust_inv_json, query, 20)

    py_bm25_ms = _time_iterations(_python_bm25_query, iterations=12)
    rs_bm25_ms = _time_iterations(_rust_bm25_query, iterations=12)

    rows = [
        (
            f"PII Scrubbing ({doc_kb:.0f} KB / 150 pages)",
            statistics.median(py_pii_ms),
            _percentile(py_pii_ms, 95),
            statistics.median(rs_pii_ms),
            _percentile(rs_pii_ms, 95),
        ),
        (
            "Semantic Chunking (150 pages -> chunks)",
            statistics.median(py_chunk_ms),
            _percentile(py_chunk_ms, 95),
            statistics.median(rs_chunk_ms),
            _percentile(rs_chunk_ms, 95),
        ),
        (
            "BM25 Query Scoring (5,000 chunks/notebook)",
            statistics.median(py_bm25_ms),
            _percentile(py_bm25_ms, 95),
            statistics.median(rs_bm25_ms),
            _percentile(rs_bm25_ms, 95),
        ),
    ]

    print("\n### OpenNoteBook Data-Plane Benchmark: Pure Python vs. Rust (`opennotebook_core`)\n")
    print(
        "| Workload | Python p50 (ms) | Python p95 (ms) | Rust p50 (ms) | Rust p95 (ms) | Speedup (p50) |"
    )
    print("| :--- | ---: | ---: | ---: | ---: | ---: |")
    for name, py50, py95, rs50, rs95 in rows:
        speedup = py50 / rs50 if rs50 > 0 else 0.0
        print(
            f"| {name} | {py50:.2f} | {py95:.2f} | {rs50:.2f} | {rs95:.2f} | **{speedup:.1f}x** |"
        )


if __name__ == "__main__":
    run_benchmark()
