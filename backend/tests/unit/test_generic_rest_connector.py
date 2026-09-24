"""OpenNotebook — Unit tests for the generic REST connector.

Uses httpx.MockTransport so request building, pagination, field mapping and ACL
parsing are exercised without a network.
"""

from __future__ import annotations

from datetime import datetime

import httpx
import pytest

from app.domain.connectors.generic_rest import RestApiConnector

FAST = {"max_per_second": 1000}


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _record(i: int) -> dict:
    return {
        "id": str(i),
        "title": f"Title {i}",
        "body": f"Body {i}",
        "allowed_users": '["u1"]',
        "allowed_roles": "engineering,admin",
    }


def test_missing_required_config_raises():
    with pytest.raises(ValueError):
        RestApiConnector({"endpoint": "/x"})
    with pytest.raises(ValueError):
        RestApiConnector({"base_url": "https://api.example.com"})


def test_sync_maps_fields_and_acls():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"items": [_record(1), _record(2)]}})

    connector = RestApiConnector(
        {
            "base_url": "https://api.example.com",
            "endpoint": "/v1/docs",
            "records_path": "data.items",
            "title_field": "title",
            "content_field": "body",
            "acl_user_field": "allowed_users",
            "acl_role_field": "allowed_roles",
            **FAST,
        },
        client=_client(handler),
    )
    docs = connector.sync()

    assert [d.title for d in docs] == ["Title 1", "Title 2"]
    assert docs[0].content == "Body 1"
    assert docs[0].allowed_users == ["u1"]
    assert docs[0].allowed_roles == ["engineering", "admin"]
    assert docs[0].external_id == "1"
    assert docs[0].source_type == "txt"


def test_autodetect_records_list():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": [_record(1)]})

    connector = RestApiConnector(
        {"base_url": "https://api.example.com", "endpoint": "/v1/docs", **FAST},
        client=_client(handler),
    )
    assert len(connector.sync()) == 1


def test_page_pagination_stops_on_short_page():
    pages_seen: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = request.url.params.get("page")
        pages_seen.append(page)
        if page == "1":
            return httpx.Response(200, json={"items": [_record(1), _record(2)]})
        return httpx.Response(200, json={"items": [_record(3)]})

    connector = RestApiConnector(
        {
            "base_url": "https://api.example.com",
            "endpoint": "/v1/docs",
            "records_path": "items",
            "pagination": {"type": "page", "page_param": "page", "size_param": "per_page", "page_size": 2},
            **FAST,
        },
        client=_client(handler),
    )
    docs = connector.sync()

    assert len(docs) == 3
    assert pages_seen == ["1", "2"]


def test_cursor_pagination():
    cursors_seen: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        cursor = request.url.params.get("cursor")
        cursors_seen.append(cursor)
        if cursor is None:
            return httpx.Response(200, json={"items": [_record(1)], "meta": {"next": "abc"}})
        return httpx.Response(200, json={"items": [_record(2)], "meta": {"next": None}})

    connector = RestApiConnector(
        {
            "base_url": "https://api.example.com",
            "endpoint": "/v1/docs",
            "records_path": "items",
            "pagination": {"type": "cursor", "cursor_param": "cursor", "cursor_path": "meta.next"},
            **FAST,
        },
        client=_client(handler),
    )
    docs = connector.sync()

    assert len(docs) == 2
    assert cursors_seen == [None, "abc"]


def test_incremental_adds_since_param():
    captured: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["since"] = request.url.params.get("updated_since")
        return httpx.Response(200, json={"items": []})

    connector = RestApiConnector(
        {
            "base_url": "https://api.example.com",
            "endpoint": "/v1/docs",
            "records_path": "items",
            "since_param": "updated_since",
            **FAST,
        },
        client=_client(handler),
    )
    connector.sync(since=datetime(2026, 1, 1, 12, 0))
    assert (captured["since"] or "").startswith("2026-01-01T12:00")


def test_max_records_cap():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": [_record(1), _record(2), _record(3)]})

    connector = RestApiConnector(
        {
            "base_url": "https://api.example.com",
            "endpoint": "/v1/docs",
            "records_path": "items",
            "max_records": 1,
            **FAST,
        },
        client=_client(handler),
    )
    assert len(connector.sync()) == 1


def test_build_client_bearer_token():
    connector = RestApiConnector(
        {"base_url": "https://api.example.com", "endpoint": "/x", "token": "tok"}
    )
    client = connector._build_client()
    assert client.headers["Authorization"] == "Bearer tok"
    client.close()


def test_build_client_api_key_header():
    connector = RestApiConnector(
        {
            "base_url": "https://api.example.com",
            "endpoint": "/x",
            "api_key": "secret",
            "api_key_header": "X-Api-Key",
        }
    )
    client = connector._build_client()
    assert client.headers["X-Api-Key"] == "secret"
    client.close()


def test_build_client_basic_auth():
    connector = RestApiConnector(
        {"base_url": "https://api.example.com", "endpoint": "/x", "username": "u", "password": "p"}
    )
    client = connector._build_client()
    assert isinstance(client.auth, httpx.BasicAuth)
    client.close()


def test_test_connection_ok_and_failure():
    ok = RestApiConnector(
        {"base_url": "https://api.example.com", "endpoint": "/x", **FAST},
        client=_client(lambda r: httpx.Response(200, json={})),
    )
    assert ok.test_connection() is True

    bad = RestApiConnector(
        {"base_url": "https://api.example.com", "endpoint": "/x", **FAST},
        client=_client(lambda r: httpx.Response(403, json={"error": "forbidden"})),
    )
    with pytest.raises(ConnectionError):
        bad.test_connection()
