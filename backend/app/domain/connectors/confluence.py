"""OpenNotebook — Confluence connector (Cloud, REST API v1).

Fetches Confluence pages, extracts their text, reads page-level read
restrictions as ACLs, and supports incremental sync via CQL ``lastmodified``.

Design notes:
- The HTTP client is injectable so tests can supply ``httpx.MockTransport``.
- ``base_url`` should be the Confluence site including the ``/wiki`` context,
  e.g. ``https://your-site.atlassian.net/wiki``.
- Pages are emitted as plain text (``source_type="txt"``) so the existing
  extractor and the ``sources.source_type`` check constraint are unaffected.

Config (``config_json`` for a connector of type ``confluence``):
    base_url        : str  Confluence site root incl. /wiki (required)
    token           : str  Bearer token / PAT (or use email + api_token)
    email           : str  account email (with api_token, uses HTTP Basic)
    api_token       : str  Atlassian API token
    space_key       : str  restrict to a space (optional)
    cql             : str  explicit CQL (optional; space_key used otherwise)
    page_limit      : int  page size per request (default: 50)
    max_pages       : int  cap on documents fetched per sync (default: 1000)
    verify_ssl      : bool TLS verification (default: true)
    max_per_second  : float optional client-side rate limit (default: 5)
"""

from __future__ import annotations

import html as html_lib
import logging
import re
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from app.domain.connectors.base import BaseConnector, ExtractedDocument
from app.domain.connectors.rate_limit import RateLimiter

logger = logging.getLogger(__name__)

_SCRIPT_STYLE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_BREAK_TAG = re.compile(r"<br\s*/?>", re.IGNORECASE)
_BLOCK_END = re.compile(r"</(p|div|li|tr|h[1-6])>", re.IGNORECASE)
_ANY_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t]+")
_NEWLINE_WS = re.compile(r" *\n *")
_BLANK_LINES = re.compile(r"\n\s*\n+")

_EXPAND = (
    "body.storage,version,restrictions.read.restrictions.user,restrictions.read.restrictions.group"
)


def html_to_text(fragment: str) -> str:
    """Convert a Confluence storage-format (XHTML) fragment to plain text."""
    if not fragment:
        return ""
    text = _SCRIPT_STYLE.sub(" ", fragment)
    text = _BREAK_TAG.sub("\n", text)
    text = _BLOCK_END.sub("\n", text)
    text = _ANY_TAG.sub(" ", text)
    text = html_lib.unescape(text)
    text = _WS.sub(" ", text)
    text = _NEWLINE_WS.sub("\n", text)
    text = _BLANK_LINES.sub("\n\n", text)
    return text.strip()


class ConfluenceConnector(BaseConnector):
    """Connector for Confluence Cloud pages."""

    def __init__(self, config: dict[str, Any], client: Any | None = None) -> None:
        super().__init__(config)
        self.base_url = str(config.get("base_url") or "").rstrip("/")
        if not self.base_url:
            raise ValueError("base_url is required for ConfluenceConnector")

        parsed = urlparse(self.base_url)
        self._origin = f"{parsed.scheme}://{parsed.netloc}"

        self.token = config.get("token")
        self.email = config.get("email")
        self.api_token = config.get("api_token")
        self.space_key = config.get("space_key")
        self.cql = config.get("cql")
        self.page_limit = int(config.get("page_limit", 50))
        self.max_pages = int(config.get("max_pages", 1000))
        self.verify_ssl = bool(config.get("verify_ssl", True))
        self._client = client
        self._rate_limiter = RateLimiter(float(config.get("max_per_second", 5)))

    # ── Internal helpers ────────────────────────────────────────────────────

    def _build_client(self) -> Any:
        import httpx

        headers = {"Accept": "application/json"}
        auth: Any = None
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        elif self.email and self.api_token:
            auth = httpx.BasicAuth(self.email, self.api_token)
        else:
            raise ValueError("ConfluenceConnector requires 'token' or ('email' and 'api_token')")

        return httpx.Client(
            headers=headers,
            auth=auth,
            timeout=30.0,
            verify=self.verify_ssl,
            follow_redirects=True,
        )

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = self._build_client()
        return self._client

    def _build_cql(self, since: datetime | None) -> str | None:
        parts: list[str] = []
        if self.cql:
            parts.append(f"({self.cql})")
        elif self.space_key:
            parts.append(f'space = "{self.space_key}"')
        else:
            parts.append('type = "page"')

        if since is not None:
            parts.append(f'lastmodified >= "{since.strftime("%Y-%m-%d %H:%M")}"')

        return " and ".join(parts)

    def _parse_acl(self, page: dict[str, Any]) -> tuple[list[str], list[str]]:
        restrictions = page.get("restrictions", {}).get("read", {}).get("restrictions", {})
        users = [
            str(u.get("accountId") or u.get("username"))
            for u in restrictions.get("user", {}).get("results", [])
            if (u.get("accountId") or u.get("username"))
        ]
        groups = [
            str(g.get("name"))
            for g in restrictions.get("group", {}).get("results", [])
            if g.get("name")
        ]
        return users, groups

    @staticmethod
    def _parse_when(value: Any) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _to_document(self, page: dict[str, Any]) -> ExtractedDocument | None:
        page_id = str(page.get("id", ""))
        title = str(page.get("title") or f"Confluence page {page_id}")
        body = page.get("body", {}).get("storage", {}).get("value", "")
        content = html_to_text(body)
        if not content.strip():
            return None

        webui = page.get("_links", {}).get("webui", "")
        url = f"{self._origin}{webui}" if webui.startswith("/") else (webui or None)
        users, groups = self._parse_acl(page)

        return ExtractedDocument(
            title=title,
            content=content,
            source_type="txt",
            url=url,
            external_id=page_id,
            last_modified=self._parse_when(page.get("version", {}).get("when")),
            allowed_users=users,
            allowed_roles=groups,
            metadata={"connector": "confluence", "page_id": page_id, "space": self.space_key},
        )

    # ── BaseConnector interface ─────────────────────────────────────────────

    def test_connection(self) -> bool:
        """Verify credentials and reachability with a minimal page request."""
        client = self._get_client()
        try:
            response = client.get(f"{self.base_url}/rest/api/content", params={"limit": 1})
            response.raise_for_status()
            return True
        except Exception as exc:
            raise ConnectionError(f"Confluence connection failed: {exc}") from exc

    def sync(self, since: datetime | None = None) -> list[ExtractedDocument]:
        """Fetch pages, optionally only those modified since ``since``."""
        client = self._get_client()
        documents: list[ExtractedDocument] = []

        params: dict[str, Any] | None = {
            "cql": self._build_cql(since),
            "expand": _EXPAND,
            "limit": self.page_limit,
        }
        url: str = f"{self.base_url}/rest/api/content"

        while url and len(documents) < self.max_pages:
            self._rate_limiter.acquire()
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()

            for page in payload.get("results", []):
                if len(documents) >= self.max_pages:
                    break
                document = self._to_document(page)
                if document is not None:
                    documents.append(document)

            next_link = payload.get("_links", {}).get("next")
            if not next_link:
                break
            url = next_link if next_link.startswith("http") else f"{self._origin}{next_link}"
            params = None  # next link already carries the query string

        logger.info("ConfluenceConnector synced %d pages", len(documents))
        return documents
