"""OpenNotebook — Unit tests for enterprise data connector framework."""

from __future__ import annotations

import pytest

from app.domain.connectors.base import BaseConnector, ExtractedDocument, SyncResult
from app.domain.connectors.web import WebConnector


def test_extracted_document_dataclass():
    """Verify document normalization contract."""
    doc = ExtractedDocument(
        title="Architecture Guide",
        content="Enterprise RAG blueprint content",
        source_type="md",
        url="https://docs.enterprise.com/arch",
        metadata={"author": "Staff Architect"},
    )
    assert doc.title == "Architecture Guide"
    assert doc.source_type == "md"
    assert doc.metadata["author"] == "Staff Architect"


def test_sync_result_status():
    """Verify SyncResult success computation."""
    res_success = SyncResult(documents_found=10, documents_synced=10)
    assert res_success.is_success is True

    res_fail = SyncResult(documents_found=5, errors=["403 Forbidden"])
    assert res_fail.is_success is False


def test_web_connector_config_validation():
    """Missing base_url raises ValueError."""
    with pytest.raises(ValueError, match="base_url is required"):
        WebConnector({"max_pages": 5})


def test_web_connector_html_extraction():
    """Verify HTML cleaning, title extraction, and script removal."""
    conn = WebConnector({"base_url": "https://docs.example.com"})

    html = """
    <!DOCTYPE html>
    <html>
    <head><title>System Architecture - OpenNotebook</title></head>
    <body>
        <script>console.log('malicious or tracking');</script>
        <style>body { color: red; }</style>
        <h1>Core Infrastructure</h1>
        <p>OpenNotebook implements decoupled data ingestion and real-time serving.</p>
    </body>
    </html>
    """
    title, text = conn._extract_page_content(html)
    assert title == "System Architecture - OpenNotebook"
    assert "malicious" not in text
    assert "OpenNotebook implements decoupled data ingestion" in text


def test_web_connector_link_extraction_domain_filtering():
    """Verify links to external untrusted domains are filtered out."""
    conn = WebConnector({
        "base_url": "https://wiki.company.com/home",
        "allowed_domains": ["wiki.company.com"],
    })

    html = """
    <a href="/guide/setup">Internal Setup Guide</a>
    <a href="https://wiki.company.com/faq">Internal FAQ</a>
    <a href="https://malicious-external.com/leak">External Link</a>
    """
    links = conn._extract_links(html, "https://wiki.company.com/home")
    assert "https://wiki.company.com/guide/setup" in links
    assert "https://wiki.company.com/faq" in links
    assert not any("malicious-external.com" in l for l in links)
