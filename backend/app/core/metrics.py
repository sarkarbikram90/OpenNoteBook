"""OpenNotebook — Prometheus Metrics Definitions.

Declares all core application and infrastructure metrics from the product spec
and registers them on the Prometheus registry.
"""

from __future__ import annotations

from prometheus_client import REGISTRY, Counter, Gauge, Histogram

# ── Metrics Declarations ─────────────────────────────────────────────────────

# API Requests Metrics
api_request_duration = Histogram(
    "opennotebook_api_request_duration_seconds",
    "Duration of API requests in seconds",
    ["endpoint", "method", "status"],
    registry=REGISTRY,
)

# AI/ML Inference Metrics
embedding_duration = Histogram(
    "opennotebook_embedding_duration_seconds",
    "Embedding generation duration in seconds",
    ["batch_size", "model"],
    registry=REGISTRY,
)

llm_tokens_total = Counter(
    "opennotebook_llm_tokens_total",
    "Total tokens consumed by type (prompt or completion)",
    ["model", "type"],
    registry=REGISTRY,
)

llm_duration = Histogram(
    "opennotebook_llm_duration_seconds",
    "Ollama LLM inference duration in seconds",
    ["model"],
    registry=REGISTRY,
)

# Retrieval Stage Metrics
retrieval_duration = Histogram(
    "opennotebook_retrieval_duration_seconds",
    "Duration of search retrieval stages (dense, bm25, fusion, rerank)",
    ["stage"],
    registry=REGISTRY,
)

# Background Task Worker Metrics
job_duration = Histogram(
    "opennotebook_job_duration_seconds",
    "Celery background task execution duration in seconds",
    ["task"],
    registry=REGISTRY,
)

job_failures_total = Counter(
    "opennotebook_job_failures_total",
    "Total number of failed Celery background jobs",
    ["task"],
    registry=REGISTRY,
)

# Product Metrics
active_sources = Gauge(
    "opennotebook_active_sources",
    "Number of active (READY) sources in a notebook",
    ["notebook_id"],
    registry=REGISTRY,
)

# Retrieval / serving quality metrics
retrieval_chunks_returned = Histogram(
    "opennotebook_retrieval_chunks_returned",
    "Number of authorized chunks returned per retrieval",
    buckets=(0, 1, 2, 3, 5, 8, 10, 15, 20, 50),
    registry=REGISTRY,
)

chat_queries_total = Counter(
    "opennotebook_chat_queries_total",
    "Chat queries served, labelled by whether any grounded context was found",
    ["has_context"],
    registry=REGISTRY,
)

# Security metrics
guardrail_blocked_total = Counter(
    "opennotebook_guardrail_blocked_total",
    "Prompts blocked by input guardrails",
    ["reason"],
    registry=REGISTRY,
)
