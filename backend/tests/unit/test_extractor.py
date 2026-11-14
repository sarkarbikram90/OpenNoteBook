"""OpenNotebook — Unit tests for PDF/DOCX/TXT extraction hardening.

Builds real files in-memory (python-docx, PyMuPDF) and runs the extractor.
"""

from __future__ import annotations

import io

import pytest

from app.domain.sources.extractor import extract

pymupdf = pytest.importorskip("pymupdf")
pytest.importorskip("docx")


def _docx_with_table() -> bytes:
    from docx import Document

    doc = Document()
    doc.add_heading("Report Title", level=1)
    doc.add_paragraph("Introductory paragraph body.")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "TABLE_CELL_SECRET"
    table.cell(0, 1).text = "Header B"
    table.cell(1, 0).text = "Row2A"
    table.cell(1, 1).text = "Row2B"
    doc.add_paragraph("Trailing paragraph after the table.")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _pdf_text_and_image() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello from the PDF text layer.")
    blank = doc.new_page()
    blank.draw_rect(pymupdf.Rect(50, 50, 300, 200), color=(0, 0, 0), fill=(1, 1, 1))
    data = doc.tobytes()
    doc.close()
    return data


def _pdf_image_only() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.draw_rect(pymupdf.Rect(20, 20, 200, 200), color=(0, 0, 0), fill=(0.5, 0.5, 0.5))
    data = doc.tobytes()
    doc.close()
    return data


def test_docx_extracts_paragraphs_headings_and_tables():
    result = extract("docx", _docx_with_table())

    assert "Introductory paragraph body." in result.text
    assert "Trailing paragraph after the table." in result.text
    assert "Report Title" in result.text
    # The key regression: table content must not be dropped.
    assert "TABLE_CELL_SECRET" in result.text
    assert "Row2B" in result.text
    assert result.metadata.get("table_count") == 1


def test_pdf_extracts_text_layer_and_flags_textless_pages():
    result = extract("pdf", _pdf_text_and_image())

    assert "Hello from the PDF text layer." in result.text
    assert len(result.pages) == 2
    assert result.pages[0].text.strip() != ""
    # Second page has no text layer and no OCR available in CI -> flagged.
    assert 2 in result.metadata["textless_pages"]
    assert isinstance(result.metadata["ocr_used"], bool)


def test_image_only_pdf_yields_no_text():
    result = extract("pdf", _pdf_image_only())
    assert result.text.strip() == ""
    assert result.metadata["textless_pages"] == [1]


def test_txt_and_markdown_extraction():
    assert "plain text body" in extract("txt", b"plain text body").text
    assert "md heading" in extract("md", b"# md heading\nbody").text



def test_image_extractor_uses_ocr_and_preserves_image_metadata(
    monkeypatch: pytest.MonkeyPatch,
):
    """Raster images are converted to a one-page OCR extraction result."""
    import pytesseract
    from PIL import Image

    image_buffer = io.BytesIO()
    Image.new("RGB", (120, 80), color="white").save(image_buffer, format="PNG")
    monkeypatch.setattr(
        pytesseract,
        "image_to_string",
        lambda image, lang="eng": "Incident runbook escalation steps",
    )

    result = extract("image", image_buffer.getvalue())

    assert "Incident runbook escalation steps" in result.text
    assert result.metadata["format"] == "png"
    assert result.metadata["page_count"] == 1
    assert result.metadata["ocr_used"] is True
    assert result.pages[0].section == "Image OCR"
