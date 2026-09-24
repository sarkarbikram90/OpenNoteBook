"""OpenNotebook — Unit tests for the Confluence connector.

Uses httpx.MockTransport to exercise real request building and response parsing
without a network or a live Confluence instance.
"""

from __future__ import annotations

from datetime import datetime

import httpx
import pytest

from app.domain.connectors.confluence import ConfluenceConnector, html_to_text

FAST = {"max_per_second": 1000}

PAGE_ONE = {
    "id": "1",
    "title": "Page One",
    "body": {"storage": {"value": "<p>Hello <strong>world</strong></p><p>Second line</p>"}},
    "version": {"when": "2026-01-01T10:00:00.000Z"},
    "_links": {"webui": "/spaces/ENG/pages/1"},
    "restrictions": {
        "read": {
            "restrictions": {
                "user": {"results": [{"accountId": "acc-1"}, {"username": "legacy"}]},
                "group": {"results": [{"name": "engineering"}]},
            }
        }
    },
}

PAGE_TWO = {
    "id": "2",
    "title": "Page Two",
    "body": {"storage": {"value": "<p>Another page</p>"}},
    "version": {"when": "2026-02-01T10:00:00.000Z"},
    "_links": {"webui": "/spaces/ENG/pages/2"},
}


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_html_to_text_strips_markup():
    assert html_to_text("<p>a</p><p>b</p>") == "a\nb"
    assert html_to_text("<script>bad()</script>ok").strip() == "ok"
    assert html_to_text("") == ""


def test_sync_paginates_and_parses_pages():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.params.get("start") == "1":
            return httpx.Response(200, json={"results": [PAGE_TWO], "_links": {}})
        return httpx.Response(
            200,
            json={
                "results": [PAGE_ONE],
                "_links": {"next": "/wiki/rest/api/content?start=1&limit=1"},
            },
        )

    connector = ConfluenceConnector(
        {"base_url": "https://site.atlassian.net/wiki", "token": "t", **FAST},
        client=_client(handler),
    )
    docs = connector.sync()

    assert [d.title for d in docs] == ["Page One", "Page Two"]

    one = docs[0]
    assert "Hello world" in one.content
    assert "Second line" in one.content
    assert "<" not in one.content
    assert one.allowed_users == ["acc-1", "legacy"]
    assert one.allowed_roles == ["engineering"]
    assert one.url == "https://site.atlassian.net/spaces/ENG/pages/1"
    assert one.last_modified is not None
    assert one.source_type == "txt"
    assert len(requests) == 2  # followed the next link


def test_incremental_sync_adds_lastmodified_cql():
    captured: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["cql"] = request.url.params.get("cql")
        return httpx.Response(200, json={"results": [], "_links": {}})

    connector = ConfluenceConnector(
        {"base_url": "https://s/wiki", "token": "t", "space_key": "ENG", **FAST},
        client=_client(handler),
    )
    connector.sync(since=datetime(2026, 3, 1))

    cql = captured["cql"] or ""
    assert 'space = "ENG"' in cql
    assert 'lastmodified >= "2026-03-01' in cql


def test_max_pages_caps_results():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [PAGE_ONE],
                "_links": {"next": "/wiki/rest/api/content?start=1&limit=1"},
            },
        )

    connector = ConfluenceConnector(
        {"base_url": "https://s/wiki", "token": "t", "max_pages": 1, **FAST},
        client=_client(handler),
    )
    assert len(connector.sync()) == 1


def test_missing_base_url_raises():
    with pytest.raises(ValueError):
        ConfluenceConnector({"token": "t"})


def test_build_client_uses_bearer_token():
    connector = ConfluenceConnector({"base_url": "https://s/wiki", "token": "tok"})
    client = connector._build_client()
    assert client.headers["Authorization"] == "Bearer tok"
    client.close()


def test_build_client_uses_basic_auth():
    connector = ConfluenceConnector(
        {"base_url": "https://s/wiki", "email": "a@b.com", "api_token": "p"}
    )
    client = connector._build_client()
    assert isinstance(client.auth, httpx.BasicAuth)
    client.close()


def test_build_client_requires_auth():
    connector = ConfluenceConnector({"base_url": "https://s/wiki"})
    with pytest.raises(ValueError):
        connector._build_client()


def test_test_connection_ok():
    connector = ConfluenceConnector(
        {"base_url": "https://s/wiki", "token": "t", **FAST},
        client=_client(lambda r: httpx.Response(200, json={"results": []})),
    )
    assert connector.test_connection() is True


def test_test_connection_raises_on_error_status():
    connector = ConfluenceConnector(
        {"base_url": "https://s/wiki", "token": "t", **FAST},
        client=_client(lambda r: httpx.Response(401, json={"message": "nope"})),
    )
    with pytest.raises(ConnectionError):
        connector.test_connection()
