"""OpenNotebook — Unit tests for connector ingestion planning."""

from __future__ import annotations

from app.domain.connectors.base import ExtractedDocument
from app.domain.connectors.ingest import content_type_for, filename_for, plan_ingest


def _doc(title: str, content: bytes = b"hello", source_type: str = "txt") -> ExtractedDocument:
    return ExtractedDocument(title=title, content=content, source_type=source_type)


def test_ingests_new_document():
    plan = plan_ingest([_doc("a.txt")], existing_checksums=[], hash_fn=lambda b: "H")
    assert len(plan.to_ingest) == 1
    assert plan.skipped == 0


def test_skips_documents_already_present():
    plan = plan_ingest([_doc("a.txt")], existing_checksums=["H"], hash_fn=lambda b: "H")
    assert plan.to_ingest == []
    assert plan.skipped == 1


def test_deduplicates_within_the_batch():
    docs = [_doc("a.txt", b"same"), _doc("b.txt", b"same")]
    plan = plan_ingest(docs, existing_checksums=[], hash_fn=lambda b: "H")
    assert len(plan.to_ingest) == 1
    assert plan.skipped == 1


def test_max_documents_caps_ingestion():
    docs = [_doc(f"f{i}.txt", str(i).encode()) for i in range(5)]
    plan = plan_ingest(docs, existing_checksums=[], max_documents=2, hash_fn=lambda b: b.decode())
    assert len(plan.to_ingest) == 2
    assert plan.skipped == 3


def test_filename_gets_extension():
    assert filename_for(_doc("report", source_type="pdf")) == "report.pdf"
    assert filename_for(_doc("report.pdf", source_type="pdf")) == "report.pdf"


def test_content_type_by_source_type():
    assert content_type_for("txt") == "text/plain"
    assert content_type_for("md") == "text/plain"
    assert content_type_for("pdf") == "application/octet-stream"
    assert content_type_for("docx") == "application/octet-stream"
