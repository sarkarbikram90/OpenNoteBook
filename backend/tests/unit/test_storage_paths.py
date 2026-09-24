"""OpenNotebook — Unit tests for canonical data-lake key helpers."""

from __future__ import annotations

from app.infrastructure.storage.paths import (
    is_processed_key,
    is_raw_key,
    processed_document_key,
    processed_key,
    processed_metadata_key,
    raw_key,
    sanitize_filename,
)


def test_raw_key_layout():
    assert raw_key("nb-1", "src-1", "report.pdf") == "raw/nb-1/src-1/report.pdf"


def test_processed_key_layout():
    assert processed_key("src-1", "document.txt") == "processed/src-1/document.txt"
    assert processed_document_key("src-1") == "processed/src-1/document.txt"
    assert processed_metadata_key("src-1") == "processed/src-1/metadata.json"


def test_sanitize_filename_strips_paths_and_unsafe_chars():
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("folder/sub/file name (1).txt") == "file_name_1_.txt"
    assert sanitize_filename("...") == "file"


def test_prefix_predicates():
    assert is_raw_key("raw/nb/src/f.pdf") is True
    assert is_raw_key("processed/src/f.txt") is False
    assert is_processed_key("processed/src/f.txt") is True
    assert is_processed_key("raw/nb/src/f.pdf") is False
