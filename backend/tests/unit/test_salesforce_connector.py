"""OpenNotebook — Unit tests for the Salesforce connector (SOQL + OAuth)."""

from __future__ import annotations

from datetime import datetime

import httpx
import pytest

from app.domain.connectors.salesforce import SalesforceConnector

FAST = {"max_per_second": 1000}
INSTANCE = "https://acme.my.salesforce.com"
QUERY_PATH = "/services/data/v60.0/query"


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _rec(i: int) -> dict:
    return {
        "attributes": {"type": "Knowledge__kav"},
        "Id": f"00{i}",
        "Title": f"Title {i}",
        "Body__c": f"Body {i}",
        "LastModifiedDate": "2026-01-01T10:00:00.000Z",
        "Allowed_Users__c": '["u1"]',
        "Allowed_Roles__c": "engineering,admin",
    }


def _base_config() -> dict:
    return {
        "instance_url": INSTANCE,
        "access_token": "tok",
        "object": "Knowledge__kav",
        "fields": ["Id", "Title", "Body__c"],
        "title_field": "Title",
        "content_field": "Body__c",
        "acl_user_field": "Allowed_Users__c",
        "acl_role_field": "Allowed_Roles__c",
        **FAST,
    }


def test_requires_soql_or_object():
    with pytest.raises(ValueError):
        SalesforceConnector({"instance_url": INSTANCE, "access_token": "tok"})


def test_sync_paginates_and_maps_records():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/query"):
            return httpx.Response(
                200,
                json={
                    "done": False,
                    "nextRecordsUrl": "/services/data/v60.0/query/01g-2",
                    "records": [_rec(1), _rec(2)],
                },
            )
        return httpx.Response(200, json={"done": True, "records": [_rec(3)]})

    connector = SalesforceConnector(_base_config(), client=_client(handler))
    docs = connector.sync()

    assert [d.title for d in docs] == ["Title 1", "Title 2", "Title 3"]
    assert docs[0].content == "Body 1"
    assert docs[0].allowed_users == ["u1"]
    assert docs[0].allowed_roles == ["engineering", "admin"]
    assert docs[0].external_id == "001"
    assert docs[0].last_modified is not None
    assert docs[0].source_type == "txt"


def test_incremental_builds_lastmodified_clause():
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["q"] = request.url.params.get("q", "")
        return httpx.Response(200, json={"done": True, "records": []})

    connector = SalesforceConnector(_base_config(), client=_client(handler))
    connector.sync(since=datetime(2026, 1, 1))

    q = captured["q"]
    assert q.startswith("SELECT")
    assert "FROM Knowledge__kav" in q
    assert "LastModifiedDate >= 2026-01-01T00:00:00Z" in q
    assert "ORDER BY LastModifiedDate ASC" in q


def test_explicit_soql_is_used_and_extended_with_and():
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["q"] = request.url.params.get("q", "")
        return httpx.Response(200, json={"done": True, "records": []})

    connector = SalesforceConnector(
        {
            "instance_url": INSTANCE,
            "access_token": "tok",
            "soql": "SELECT Id FROM Account WHERE Name != null",
            **FAST,
        },
        client=_client(handler),
    )
    connector.sync(since=datetime(2026, 2, 1))

    q = captured["q"]
    assert q.startswith("SELECT Id FROM Account")
    assert " AND LastModifiedDate >=" in q


def test_client_credentials_token_exchange():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/services/oauth2/token"
        body = request.content.decode()
        seen["body"] = body
        return httpx.Response(
            200, json={"access_token": "new-tok", "instance_url": INSTANCE}
        )

    connector = SalesforceConnector(
        {"login_url": "https://login.salesforce.com", "client_id": "cid", "client_secret": "sec", "object": "Account"},
        client=_client(handler),
    )
    connector._ensure_auth()

    assert connector.access_token == "new-tok"
    assert connector.instance_url == INSTANCE
    assert "grant_type=client_credentials" in seen["body"]


def test_requires_credentials_for_token_exchange():
    connector = SalesforceConnector({"object": "Account", "instance_url": INSTANCE})
    with pytest.raises(ValueError):
        connector._ensure_auth()


def test_test_connection_ok_and_failure():
    ok = SalesforceConnector(
        _base_config(),
        client=_client(lambda r: httpx.Response(200, json={"done": True, "records": []})),
    )
    assert ok.test_connection() is True

    bad = SalesforceConnector(
        _base_config(),
        client=_client(lambda r: httpx.Response(401, json=[{"errorCode": "INVALID_SESSION_ID"}])),
    )
    with pytest.raises(ConnectionError):
        bad.test_connection()
