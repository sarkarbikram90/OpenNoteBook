"""OpenNotebook — Unit tests for the local file-share connector."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import pytest

from app.domain.connectors.local_fileshare import LocalFileShareConnector

if TYPE_CHECKING:
    from pathlib import Path


def test_missing_root_path_raises():
    with pytest.raises(ValueError):
        LocalFileShareConnector({})


def test_sync_discovers_supported_files_and_checksums(tmp_path: Path):
    (tmp_path / "a.txt").write_text("hello world", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.md").write_text("# Title\nbody", encoding="utf-8")
    (tmp_path / "ignored.csv").write_text("x,y", encoding="utf-8")

    connector = LocalFileShareConnector({"root_path": str(tmp_path)})
    docs = connector.sync()

    by_name = {d.title: d for d in docs}
    assert set(by_name) == {"a.txt", "b.md"}

    a = by_name["a.txt"]
    assert a.source_type == "txt"
    assert a.external_id == hashlib.sha256(b"hello world").hexdigest()
    assert a.metadata["checksum"] == a.external_id
    assert a.metadata["relative_path"] == "a.txt"

    b = by_name["b.md"]
    assert b.source_type == "md"
    assert b.metadata["relative_path"] == "sub/b.md"


def test_non_recursive_skips_subdirectories(tmp_path: Path):
    (tmp_path / "top.txt").write_text("top", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "nested.txt").write_text("nested", encoding="utf-8")

    connector = LocalFileShareConnector({"root_path": str(tmp_path), "recursive": False})
    titles = {d.title for d in connector.sync()}
    assert titles == {"top.txt"}


def test_max_files_cap(tmp_path: Path):
    for i in range(10):
        (tmp_path / f"f{i}.txt").write_text(f"doc {i}", encoding="utf-8")

    connector = LocalFileShareConnector({"root_path": str(tmp_path), "max_files": 3})
    assert len(connector.sync()) == 3


def test_test_connection_reports_missing_path(tmp_path: Path):
    connector = LocalFileShareConnector({"root_path": str(tmp_path / "does-not-exist")})
    with pytest.raises(ConnectionError):
        connector.test_connection()


def test_test_connection_ok(tmp_path: Path):
    connector = LocalFileShareConnector({"root_path": str(tmp_path)})
    assert connector.test_connection() is True
