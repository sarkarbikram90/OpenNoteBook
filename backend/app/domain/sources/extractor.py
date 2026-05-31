"""OpenNotebook — Text extraction from multiple source types.

Supports PDF (PyMuPDF), DOCX (python-docx), TXT/Markdown (raw text),
URL (trafilatura), and YouTube (youtube-transcript-api).

Each extractor returns an ``ExtractionResult`` with the full text,
per-page content, and document-level metadata.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ── Data Structures ─────────────────────────────────────────────────────────


@dataclass
class PageContent:
    """Text content for a single page (or logical section)."""

    page_number: int
    text: str
    section: str | None = None


@dataclass
class ExtractionResult:
    """Complete extraction output from any source type."""

    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    pages: list[PageContent] = field(default_factory=list)


# ── Dispatcher ──────────────────────────────────────────────────────────────


def extract(source_type: str, content: bytes | str, **kwargs: Any) -> ExtractionResult:
    """Route extraction to the appropriate handler based on source type.

    Args:
        source_type: One of ``pdf``, ``docx``, ``txt``, ``md``, ``url``, ``youtube``.
        content: Raw file bytes (for pdf/docx/txt/md) or a URL string (for url/youtube).
        **kwargs: Additional arguments passed to specific extractors.

    Returns:
        ExtractionResult with full text, pages, and metadata.

    Raises:
        ValueError: If the source type is not supported.
    """
    extractors = {
        "pdf": _extract_pdf,
        "docx": _extract_docx,
        "txt": _extract_text,
        "md": _extract_text,
        "url": _extract_url,
        "youtube": _extract_youtube,
    }

    handler = extractors.get(source_type)
    if handler is None:
        raise ValueError(f"Unsupported source type: {source_type}")

    logger.info("Extracting text from source type: %s", source_type)
    return handler(content, **kwargs)


# ── PDF Extraction (PyMuPDF) ────────────────────────────────────────────────


def _extract_pdf(content: bytes | str, **kwargs: Any) -> ExtractionResult:
    """Extract text from a PDF using PyMuPDF (fitz).

    Preserves page numbers and attempts to detect section headings
    from font-size changes.
    """
    import fitz  # PyMuPDF

    if isinstance(content, str):
        content = content.encode("utf-8")

    doc = fitz.open(stream=content, filetype="pdf")
    pages: list[PageContent] = []
    full_text_parts: list[str] = []

    metadata = {
        "title": doc.metadata.get("title", ""),
        "author": doc.metadata.get("author", ""),
        "page_count": len(doc),
        "format": "pdf",
    }

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")

        # Attempt to detect the first large-font line as a section heading
        section = _detect_pdf_section(page)

        pages.append(PageContent(
            page_number=page_num + 1,
            text=text,
            section=section,
        ))
        full_text_parts.append(text)

    doc.close()

    return ExtractionResult(
        text="\n\n".join(full_text_parts),
        metadata=metadata,
        pages=pages,
    )


def _detect_pdf_section(page: Any) -> str | None:
    """Detect a section heading on a PDF page by looking for large-font text blocks."""
    try:
        blocks = page.get_text("dict", flags=11)["blocks"]
        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    # Heuristic: text with font size > 14 and short length is likely a heading
                    if span["size"] > 14 and len(span["text"].strip()) < 200:
                        heading = span["text"].strip()
                        if heading:
                            return heading
    except Exception:
        pass
    return None


# ── DOCX Extraction (python-docx) ──────────────────────────────────────────


def _extract_docx(content: bytes | str, **kwargs: Any) -> ExtractionResult:
    """Extract text from a DOCX file using python-docx.

    Detects section headings from paragraph styles (Heading 1, Heading 2, etc.).
    """
    import io

    from docx import Document

    if isinstance(content, str):
        content = content.encode("utf-8")

    doc = Document(io.BytesIO(content))

    pages: list[PageContent] = []
    full_text_parts: list[str] = []
    current_section: str | None = None
    current_page_text: list[str] = []
    page_number = 1

    metadata = {
        "title": doc.core_properties.title or "",
        "author": doc.core_properties.author or "",
        "format": "docx",
    }

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        # Detect heading styles
        if para.style and para.style.name and para.style.name.startswith("Heading"):
            # Save current page content
            if current_page_text:
                page_text = "\n".join(current_page_text)
                pages.append(PageContent(
                    page_number=page_number,
                    text=page_text,
                    section=current_section,
                ))
                full_text_parts.append(page_text)
                page_number += 1
                current_page_text = []

            current_section = text

        current_page_text.append(text)

    # Flush remaining content
    if current_page_text:
        page_text = "\n".join(current_page_text)
        pages.append(PageContent(
            page_number=page_number,
            text=page_text,
            section=current_section,
        ))
        full_text_parts.append(page_text)

    metadata["page_count"] = len(pages)

    return ExtractionResult(
        text="\n\n".join(full_text_parts),
        metadata=metadata,
        pages=pages,
    )


# ── TXT / Markdown Extraction ──────────────────────────────────────────────


def _extract_text(content: bytes | str, **kwargs: Any) -> ExtractionResult:
    """Extract text from a plain text or Markdown file.

    Detects Markdown-style headings (``# Heading``) as sections.
    """
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")

    lines = content.split("\n")
    pages: list[PageContent] = []
    current_section: str | None = None
    current_page_text: list[str] = []
    page_number = 1

    heading_re = re.compile(r"^#{1,6}\s+(.+)$")

    for line in lines:
        match = heading_re.match(line.strip())
        if match:
            # Save current section as a page
            if current_page_text:
                page_text = "\n".join(current_page_text)
                pages.append(PageContent(
                    page_number=page_number,
                    text=page_text,
                    section=current_section,
                ))
                page_number += 1
                current_page_text = []

            current_section = match.group(1).strip()

        current_page_text.append(line)

    # Flush
    if current_page_text:
        page_text = "\n".join(current_page_text)
        pages.append(PageContent(
            page_number=page_number,
            text=page_text,
            section=current_section,
        ))

    return ExtractionResult(
        text=content,
        metadata={"format": "text", "page_count": len(pages)},
        pages=pages,
    )


# ── URL Extraction (trafilatura) ────────────────────────────────────────────


def _extract_url(content: bytes | str, **kwargs: Any) -> ExtractionResult:
    """Scrape and extract text from a web page using trafilatura.

    Removes boilerplate and extracts main content as clean text.
    """
    import trafilatura

    url = content if isinstance(content, str) else content.decode("utf-8")

    downloaded = trafilatura.fetch_url(url)
    if downloaded is None:
        raise ValueError(f"Failed to fetch URL: {url}")

    text = trafilatura.extract(
        downloaded,
        include_comments=False,
        include_tables=True,
        output_format="txt",
    )
    if text is None:
        raise ValueError(f"Failed to extract text from URL: {url}")

    # Try to get metadata
    metadata_result = trafilatura.extract(
        downloaded,
        output_format="json",
        include_comments=False,
    )

    metadata: dict[str, Any] = {
        "format": "url",
        "source_url": url,
    }

    # Extract title from the HTML
    title_match = re.search(r"<title[^>]*>([^<]+)</title>", downloaded, re.IGNORECASE)
    if title_match:
        metadata["title"] = title_match.group(1).strip()

    pages = [PageContent(
        page_number=1,
        text=text,
        section=metadata.get("title"),
    )]

    return ExtractionResult(
        text=text,
        metadata=metadata,
        pages=pages,
    )


# ── YouTube Transcript Extraction ───────────────────────────────────────────


def _extract_youtube(content: bytes | str, **kwargs: Any) -> ExtractionResult:
    """Extract transcript from a YouTube video.

    Supports auto-generated and manual captions.  Preserves timestamps
    as section markers.
    """
    from youtube_transcript_api import YouTubeTranscriptApi

    url = content if isinstance(content, str) else content.decode("utf-8")
    video_id = _parse_youtube_id(url)

    if not video_id:
        raise ValueError(f"Could not parse YouTube video ID from: {url}")

    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

    # Prefer manually created transcripts, fall back to auto-generated
    transcript = None
    try:
        transcript = transcript_list.find_manually_created_transcript(["en"])
    except Exception:
        try:
            transcript = transcript_list.find_generated_transcript(["en"])
        except Exception:
            # Try any available transcript
            for t in transcript_list:
                transcript = t
                break

    if transcript is None:
        raise ValueError(f"No transcript available for video: {video_id}")

    entries = transcript.fetch()
    full_text_parts: list[str] = []
    pages: list[PageContent] = []

    # Group transcript entries into ~60-second pages
    current_page_text: list[str] = []
    page_start_time = 0.0
    page_number = 1

    for entry in entries:
        text = entry["text"].strip()
        if not text:
            continue

        current_page_text.append(text)
        elapsed = entry["start"] - page_start_time

        # Create a new "page" roughly every 60 seconds
        if elapsed >= 60.0:
            page_text = " ".join(current_page_text)
            pages.append(PageContent(
                page_number=page_number,
                text=page_text,
                section=f"Timestamp {int(page_start_time // 60)}:{int(page_start_time % 60):02d}",
            ))
            full_text_parts.append(page_text)
            page_number += 1
            current_page_text = []
            page_start_time = entry["start"]

    # Flush remaining
    if current_page_text:
        page_text = " ".join(current_page_text)
        pages.append(PageContent(
            page_number=page_number,
            text=page_text,
            section=f"Timestamp {int(page_start_time // 60)}:{int(page_start_time % 60):02d}",
        ))
        full_text_parts.append(page_text)

    return ExtractionResult(
        text=" ".join(full_text_parts),
        metadata={
            "format": "youtube",
            "source_url": url,
            "video_id": video_id,
            "page_count": len(pages),
        },
        pages=pages,
    )


def _parse_youtube_id(url: str) -> str | None:
    """Extract the video ID from various YouTube URL formats."""
    patterns = [
        r"(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"(?:embed/)([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None
