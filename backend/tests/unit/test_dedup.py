"""OpenNotebook — Unit tests for checksum-based deduplication helpers."""

from __future__ import annotations

from app.domain.sources.dedup import checksum_exists


def test_checksum_exists_true_when_present():
    existing = ["aaa", "bbb", "ccc"]
    assert checksum_exists(existing, "bbb") is True


def test_checksum_exists_false_when_absent():
    assert checksum_exists(["aaa", "bbb"], "zzz") is False


def test_checksum_exists_empty_set():
    assert checksum_exists([], "aaa") is False
