"""OpenNotebook — Unit tests for the SQL connector (SQLite-backed)."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine, text

from app.domain.connectors.sql_connector import SqlConnector


@pytest.fixture
def sqlite_dsn(tmp_path):
    dsn = f"sqlite:///{(tmp_path / 'knowledge.db').as_posix()}"
    engine = create_engine(dsn)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE docs (
                    id INTEGER PRIMARY KEY,
                    title TEXT,
                    body TEXT,
                    category TEXT,
                    allowed_users TEXT,
                    allowed_roles TEXT,
                    updated_at TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                "INSERT INTO docs VALUES "
                "(1, 'Doc One', 'First body', 'hr',  '[\"u1\",\"u2\"]', '[\"hr\"]', "
                "'2026-01-01 00:00:00')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO docs VALUES "
                "(2, 'Doc Two', 'Second body', 'fin', 'u3', 'finance,admin', "
                "'2026-06-01 00:00:00')"
            )
        )
    engine.dispose()
    return dsn


def test_missing_dsn_raises():
    with pytest.raises(ValueError):
        SqlConnector({"table": "docs"})


def test_missing_table_raises():
    with pytest.raises(ValueError):
        SqlConnector({"dsn": "sqlite://"})


def test_sync_returns_text_documents(sqlite_dsn):
    connector = SqlConnector(
        {
            "dsn": sqlite_dsn,
            "table": "docs",
            "id_column": "id",
            "title_column": "title",
            "content_column": "body",
            "acl_user_column": "allowed_users",
            "acl_role_column": "allowed_roles",
        }
    )
    docs = connector.sync()

    assert {d.title for d in docs} == {"Doc One", "Doc Two"}
    assert all(d.source_type == "txt" for d in docs)

    one = next(d for d in docs if d.title == "Doc One")
    assert one.content == "First body"
    assert one.external_id == "1"
    assert one.allowed_users == ["u1", "u2"]
    assert one.allowed_roles == ["hr"]

    two = next(d for d in docs if d.title == "Doc Two")
    assert two.allowed_users == ["u3"]
    assert two.allowed_roles == ["finance", "admin"]


def test_text_columns_are_composed(sqlite_dsn):
    connector = SqlConnector(
        {"dsn": sqlite_dsn, "table": "docs", "text_columns": ["title", "body"]}
    )
    docs = connector.sync()
    one = next(d for d in docs if d.metadata["row_id"] == "1")
    assert "Doc One" in one.content
    assert "First body" in one.content


def test_incremental_sync_filters_by_watermark(sqlite_dsn):
    connector = SqlConnector(
        {"dsn": sqlite_dsn, "table": "docs", "title_column": "title", "updated_column": "updated_at"}
    )
    docs = connector.sync(since=datetime(2026, 3, 1))
    assert [d.title for d in docs] == ["Doc Two"]


def test_where_filter(sqlite_dsn):
    connector = SqlConnector(
        {"dsn": sqlite_dsn, "table": "docs", "title_column": "title", "where": "category = 'hr'"}
    )
    docs = connector.sync()
    assert [d.title for d in docs] == ["Doc One"]


def test_max_rows_cap(sqlite_dsn):
    connector = SqlConnector({"dsn": sqlite_dsn, "table": "docs", "max_rows": 1})
    assert len(connector.sync()) == 1


def test_test_connection_ok(sqlite_dsn):
    connector = SqlConnector({"dsn": sqlite_dsn, "table": "docs"})
    assert connector.test_connection() is True


def test_test_connection_missing_table_raises(sqlite_dsn):
    connector = SqlConnector({"dsn": sqlite_dsn, "table": "does_not_exist"})
    with pytest.raises(ConnectionError):
        connector.test_connection()


def test_parse_acl_handles_json_csv_and_none():
    assert SqlConnector._parse_acl('["a","b"]') == ["a", "b"]
    assert SqlConnector._parse_acl("a, b ,c") == ["a", "b", "c"]
    assert SqlConnector._parse_acl(None) == []
    assert SqlConnector._parse_acl(["x", "y"]) == ["x", "y"]
