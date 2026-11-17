"""Unit tests for GCS Pub/Sub event ingestion and PostgreSQL + pgvector vector store."""

from __future__ import annotations

import base64
import json
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.domain.chat.orchestrator import GroundedPromptBuilder
from app.domain.retrieval import retriever
from app.infrastructure.db.base import Base
from app.infrastructure.pgvector import client as pgvector_client
from app.infrastructure.pubsub.gcs_events import (
    is_generation_already_processed,
    parse_pubsub_push_envelope,
    parse_raw_object_key,
    record_generation_on_metadata,
)
from app.infrastructure.qdrant.schema import ChunkPayload


def test_parse_pubsub_push_envelope_and_raw_key():
    """Verify GCS OBJECT_FINALIZE Pub/Sub envelope decoding and raw key parsing."""
    nb_id = uuid.uuid4()
    src_id = uuid.uuid4()
    raw_name = f"raw/{nb_id}/{src_id}/architecture.pdf"
    gcs_payload = {
        "bucket": "opennotebook-prod-uploads",
        "name": raw_name,
        "generation": "1731870000123456",
        "contentType": "application/pdf",
        "size": "4096",
        "md5Hash": "abc123==",
        "metadata": {"sha256": "deadbeef" * 8},
    }
    envelope = {
        "message": {
            "data": base64.b64encode(json.dumps(gcs_payload).encode("utf-8")).decode("ascii"),
            "attributes": {
                "eventType": "OBJECT_FINALIZE",
                "bucketId": "opennotebook-prod-uploads",
                "objectId": raw_name,
                "objectGeneration": "1731870000123456",
            },
            "messageId": "msg-101",
        },
        "subscription": "projects/test/subscriptions/opennotebook-gcs-events-sub",
    }

    event = parse_pubsub_push_envelope(envelope)
    assert event is not None
    assert event.bucket == "opennotebook-prod-uploads"
    assert event.object_name == raw_name
    assert event.generation == "1731870000123456"
    assert event.size_bytes == 4096
    assert event.message_id == "msg-101"

    parsed = parse_raw_object_key(event.object_name)
    assert parsed is not None
    assert parsed.notebook_id == nb_id
    assert parsed.source_id == src_id
    assert parsed.filename == "architecture.pdf"
    assert parsed.source_type == "pdf"

    # Derived processed/ artifacts must be ignored to prevent ingestion loops
    assert parse_raw_object_key(f"processed/{src_id}/document.txt") is None

    # Non-finalize events (e.g., OBJECT_DELETE) return None
    delete_env = {
        "message": {
            "attributes": {"eventType": "OBJECT_DELETE"},
            "messageId": "msg-102",
        }
    }
    assert parse_pubsub_push_envelope(delete_env) is None


def test_pubsub_object_generation_idempotency():
    """Duplicate deliveries of the same GCS object generation must be detected."""
    event = parse_pubsub_push_envelope(
        {
            "bucket": "opennotebook-prod-uploads",
            "name": f"raw/{uuid.uuid4()}/{uuid.uuid4()}/notes.md",
            "generation": "999888777",
        }
    )
    assert event is not None

    meta: dict = {}
    assert is_generation_already_processed("UPLOADED", meta, "999888777") is False

    meta = record_generation_on_metadata(meta, event)
    assert is_generation_already_processed("READY", meta, "999888777") is True
    assert is_generation_already_processed("QUEUED", meta, "999888777") is True
    # A new object generation (e.g., overwritten file) should be processed
    assert is_generation_already_processed("READY", meta, "999888778") is False
    # If the previous attempt FAILED, retry of the same generation is allowed
    assert is_generation_already_processed("FAILED", meta, "999888777") is False


def test_pgvector_store_and_grounded_retrieval_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
):
    """Verify PostgreSQL/pgvector chunk upsert, cosine search, and cited RAG prompt construction."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    monkeypatch.setattr(pgvector_client, "_get_session", lambda: SessionLocal())

    nb_id = str(uuid.uuid4())
    src_id = str(uuid.uuid4())

    chunks = [
        ChunkPayload(
            chunk_id="chunk-gcs-1",
            source_id=src_id,
            source_name="GCS-Architecture-Spec.pdf",
            notebook_id=nb_id,
            text="Google Cloud Storage triggers OBJECT_FINALIZE notifications via Pub/Sub.",
            token_count=12,
            page=4,
            section="Event Ingestion",
            embedding_model="text-embedding-004",
            vector=[1.0, 0.0, 0.0],
        ),
        ChunkPayload(
            chunk_id="chunk-pg-2",
            source_id=src_id,
            source_name="GCS-Architecture-Spec.pdf",
            notebook_id=nb_id,
            text="PostgreSQL with pgvector stores document embeddings and metadata.",
            token_count=10,
            page=7,
            section="Vector Database",
            embedding_model="text-embedding-004",
            vector=[0.0, 1.0, 0.0],
        ),
    ]

    pgvector_client.ensure_collection()
    pgvector_client.upsert_chunks(chunks)

    all_nb_chunks = pgvector_client.get_all_chunks_for_notebook(nb_id)
    assert len(all_nb_chunks) == 2

    by_ids = pgvector_client.get_chunks_by_ids(["chunk-pg-2"])
    assert len(by_ids) == 1
    assert by_ids[0]["source_name"] == "GCS-Architecture-Spec.pdf"
    assert by_ids[0]["page"] == 7

    # Wire retriever to use pgvector and a deterministic query vector matching chunk-gcs-1
    fake_settings = SimpleNamespace(
        vector_store_provider="pgvector",
        retrieval_top_k=5,
        rerank_top_k=2,
        rrf_k=60,
    )
    monkeypatch.setattr(retriever, "get_settings", lambda: fake_settings)
    monkeypatch.setattr(
        "app.domain.sources.embedder.embed_texts",
        lambda _texts, is_query=False: [[0.95, 0.05, 0.0]] if is_query else [[0.0, 0.0, 0.0]],
    )

    dense = retriever._dense_search(
        query="How does GCS trigger ingestion?",
        notebook_id=nb_id,
        top_k=2,
    )
    assert len(dense) == 2
    assert dense[0]["chunk_id"] == "chunk-gcs-1"
    assert dense[0]["source_name"] == "GCS-Architecture-Spec.pdf"
    assert dense[0]["page"] == 4

    retrieved_chunk = retriever.RetrievedChunk(
        chunk_id=dense[0]["chunk_id"],
        source_id=dense[0]["source_id"],
        source_name=dense[0]["source_name"],
        notebook_id=dense[0]["notebook_id"],
        text=dense[0]["text"],
        page=dense[0]["page"],
        section=dense[0]["section"],
        relevance_score=dense[0]["_dense_score"],
    )
    prompt, citations = GroundedPromptBuilder.build_prompt(
        query="How does GCS trigger ingestion?",
        chunks=[retrieved_chunk],
    )
    assert "GCS-Architecture-Spec.pdf" in prompt
    assert "Page 4" in prompt
    assert len(citations) == 1
    assert citations[0].format_citation() == "[GCS-Architecture-Spec.pdf — p. 4]"

    pgvector_client.delete_by_source(src_id)
    assert pgvector_client.get_all_chunks_for_notebook(nb_id) == []
    engine.dispose()

