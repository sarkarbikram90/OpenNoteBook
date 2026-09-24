"""OpenNotebook — Unit tests for the SharePoint connector (Microsoft Graph)."""

from __future__ import annotations

import hashlib
from datetime import datetime

import httpx
import pytest

from app.domain.connectors.sharepoint import SharePointConnector

GRAPH = "https://graph.microsoft.com/v1.0"
FAST = {"max_per_second": 1000}

FILE_PDF = {
    "id": "item-pdf",
    "name": "report.pdf",
    "file": {"mimeType": "application/pdf"},
    "lastModifiedDateTime": "2026-01-01T10:00:00Z",
    "webUrl": "https://contoso.sharepoint.com/report.pdf",
}
FILE_TXT = {
    "id": "item-txt",
    "name": "notes.txt",
    "file": {"mimeType": "text/plain"},
    "lastModifiedDateTime": "2026-05-01T10:00:00Z",
    "webUrl": "https://contoso.sharepoint.com/notes.txt",
}
FOLDER = {"id": "folder-1", "name": "Sub", "folder": {"childCount": 3}}
UNSUPPORTED = {"id": "item-csv", "name": "data.csv", "file": {"mimeType": "text/csv"}}


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _config(**overrides) -> dict:
    config = {
        "site_hostname": "contoso.sharepoint.com",
        "site_path": "/sites/Eng",
        "access_token": "tok",
        **FAST,
    }
    config.update(overrides)
    return config


def _graph_handler(requests: list[httpx.Request]):
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = request.url.path
        if request.method == "POST":
            return httpx.Response(200, json={"access_token": "tok"})
        if path.endswith("/drive"):
            return httpx.Response(200, json={"id": "drive1"})
        if path.endswith(":/sites/Eng"):
            return httpx.Response(200, json={"id": "site1"})
        if path.endswith("/root/children") or path.endswith(":/children"):
            if request.url.params.get("page") == "2":
                return httpx.Response(200, json={"value": [FILE_TXT]})
            return httpx.Response(
                200,
                json={
                    "value": [FILE_PDF, FOLDER, UNSUPPORTED],
                    "@odata.nextLink": f"{GRAPH}/drives/drive1/root/children?page=2",
                },
            )
        if path.endswith("/content"):
            if "item-pdf" in path:
                return httpx.Response(200, content=b"%PDF-1.4")
            return httpx.Response(200, content=b"hello notes")
        return httpx.Response(404, json={"error": "not found"})

    return handler


def test_requires_site_config():
    with pytest.raises(ValueError):
        SharePointConnector({"access_token": "tok"})


def test_sync_resolves_paginates_and_downloads():
    requests: list[httpx.Request] = []
    connector = SharePointConnector(_config(), client=_client(_graph_handler(requests)))
    docs = connector.sync()

    assert [d.title for d in docs] == ["report.pdf", "notes.txt"]

    pdf = docs[0]
    assert pdf.source_type == "pdf"
    assert pdf.content == b"%PDF-1.4"
    assert pdf.metadata["checksum"] == hashlib.sha256(b"%PDF-1.4").hexdigest()
    assert pdf.external_id == "item-pdf"

    txt = docs[1]
    assert txt.source_type == "txt"
    assert txt.content == b"hello notes"

    # site + drive resolved, then two children pages, then two content downloads
    assert any(r.url.path.endswith(":/sites/Eng") for r in requests)
    assert any(r.url.path.endswith("/drive") for r in requests)
    assert sum(1 for r in requests if r.url.path.endswith("/content")) == 2


def test_incremental_filters_by_last_modified():
    connector = SharePointConnector(
        _config(), client=_client(_graph_handler([]))
    )
    docs = connector.sync(since=datetime(2026, 3, 1))
    assert [d.title for d in docs] == ["notes.txt"]


def test_default_acls_stamped_on_documents():
    connector = SharePointConnector(
        _config(default_allowed_roles=["engineering"], default_allowed_users=["u-1"]),
        client=_client(_graph_handler([])),
    )
    docs = connector.sync()
    assert all(d.allowed_roles == ["engineering"] for d in docs)
    assert all(d.allowed_users == ["u-1"] for d in docs)


def test_folder_path_changes_children_url():
    requests: list[httpx.Request] = []
    connector = SharePointConnector(
        _config(folder_path="Shared Documents/Reports"),
        client=_client(_graph_handler(requests)),
    )
    connector.sync()
    assert any("/root:/Shared Documents/Reports:/children" in r.url.path for r in requests)


def test_max_files_cap():
    connector = SharePointConnector(_config(max_files=1), client=_client(_graph_handler([])))
    assert len(connector.sync()) == 1


def test_client_credentials_token_exchange():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/tenant-1/oauth2/v2.0/token"
        assert "grant_type=client_credentials" in request.content.decode()
        return httpx.Response(200, json={"access_token": "graph-tok"})

    connector = SharePointConnector(
        {"tenant_id": "tenant-1", "client_id": "cid", "client_secret": "sec", "site_id": "site1"},
        client=_client(handler),
    )
    connector._ensure_auth()
    assert connector.access_token == "graph-tok"


def test_requires_credentials_for_token_exchange():
    connector = SharePointConnector({"site_id": "site1"})
    with pytest.raises(ValueError):
        connector._ensure_auth()


def test_test_connection_ok_and_failure():
    ok = SharePointConnector(_config(), client=_client(_graph_handler([])))
    assert ok.test_connection() is True

    bad = SharePointConnector(
        _config(),
        client=_client(lambda r: httpx.Response(401, json={"error": "unauthorized"})),
    )
    with pytest.raises(ConnectionError):
        bad.test_connection()
