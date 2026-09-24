"""OpenNotebook — Generic REST API connector.

Config-driven connector for bespoke enterprise REST APIs. Supports bearer /
basic / API-key auth, page/offset/cursor pagination, static query params,
incremental sync via a ``since`` query parameter, JSON field mapping, and
per-record ACLs.

The HTTP client is injectable so tests can supply ``httpx.MockTransport``.

Config (``config_json`` for a connector of type ``rest``):
    base_url        : str   required
    endpoint        : str   required path, e.g. "/v1/documents"
    method          : str   default "GET"
    headers         : dict  extra request headers
    token           : str   bearer token
    username        : str   basic auth user
    password        : str   basic auth password
    api_key         : str   API key value
    api_key_header  : str   header name for the key (default "X-API-Key")
    params          : dict  static query params
    records_path    : str   dot path to the records list (optional; autodetected)
    id_field        : str   default "id"
    title_field     : str
    content_field   : str
    text_fields     : list  columns concatenated to form content
    updated_field   : str
    acl_user_field  : str
    acl_role_field  : str
    since_param     : str   query param used for incremental sync
    pagination      : dict  {type: none|page|offset|cursor, ...}
    max_records     : int   default 1000
    verify_ssl      : bool  default true
    max_per_second  : float default 5
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from app.domain.connectors.acl import parse_acl
from app.domain.connectors.base import BaseConnector, ExtractedDocument
from app.domain.connectors.rate_limit import RateLimiter

logger = logging.getLogger(__name__)

_AUTODETECT_KEYS = ("data", "results", "items", "records", "documents")


def _dig(data: Any, path: str) -> Any:
    """Navigate a dot-path (e.g. ``data.items``) within nested dicts."""
    current = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


class RestApiConnector(BaseConnector):
    """Generic configurable REST API connector."""

    def __init__(self, config: dict[str, Any], client: Any | None = None) -> None:
        super().__init__(config)
        self.base_url = str(config.get("base_url") or "").rstrip("/")
        self.endpoint = str(config.get("endpoint") or "")
        if not self.base_url:
            raise ValueError("base_url is required for RestApiConnector")
        if not self.endpoint:
            raise ValueError("endpoint is required for RestApiConnector")

        self.method = str(config.get("method", "GET")).upper()
        self.extra_headers = dict(config.get("headers") or {})
        self.token = config.get("token")
        self.username = config.get("username")
        self.password = config.get("password")
        self.api_key = config.get("api_key")
        self.api_key_header = str(config.get("api_key_header", "X-API-Key"))
        self.static_params = dict(config.get("params") or {})

        self.records_path = config.get("records_path")
        self.id_field = str(config.get("id_field", "id"))
        self.title_field = config.get("title_field")
        self.content_field = config.get("content_field")
        self.text_fields = list(config.get("text_fields") or [])
        self.updated_field = config.get("updated_field")
        self.acl_user_field = config.get("acl_user_field")
        self.acl_role_field = config.get("acl_role_field")
        self.since_param = config.get("since_param")

        pagination = dict(config.get("pagination") or {})
        self.pagination_type = str(pagination.get("type", "none")).lower()
        self.page_param = str(pagination.get("page_param", "page"))
        self.start_page = int(pagination.get("start_page", 1))
        self.size_param = str(pagination.get("size_param", "per_page"))
        self.page_size = int(pagination.get("page_size", 100))
        self.offset_param = str(pagination.get("offset_param", "offset"))
        self.cursor_param = str(pagination.get("cursor_param", "cursor"))
        self.cursor_path = pagination.get("cursor_path")

        self.max_records = int(config.get("max_records", 1000))
        self.verify_ssl = bool(config.get("verify_ssl", True))
        self._client = client
        self._rate_limiter = RateLimiter(float(config.get("max_per_second", 5)))

    # ── HTTP client ─────────────────────────────────────────────────────────

    def _build_client(self) -> Any:
        import httpx

        headers = {"Accept": "application/json", **self.extra_headers}
        auth: Any = None
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        elif self.username is not None and self.password is not None:
            auth = httpx.BasicAuth(self.username, self.password)
        if self.api_key:
            headers[self.api_key_header] = str(self.api_key)

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

    # ── Record mapping ──────────────────────────────────────────────────────

    def _extract_records(self, payload: Any) -> list[dict[str, Any]]:
        if self.records_path:
            found = _dig(payload, str(self.records_path))
            return [r for r in found if isinstance(r, dict)] if isinstance(found, list) else []

        if isinstance(payload, list):
            return [r for r in payload if isinstance(r, dict)]
        if isinstance(payload, dict):
            for key in _AUTODETECT_KEYS:
                value = payload.get(key)
                if isinstance(value, list):
                    return [r for r in value if isinstance(r, dict)]
                if isinstance(value, dict):
                    for nested in _AUTODETECT_KEYS:
                        if isinstance(value.get(nested), list):
                            return [r for r in value[nested] if isinstance(r, dict)]
        return []

    def _record_content(self, record: dict[str, Any]) -> str:
        if self.text_fields:
            return "\n\n".join(
                str(record[f]) for f in self.text_fields if record.get(f) is not None
            )
        if self.content_field and record.get(self.content_field) is not None:
            value = record[self.content_field]
            return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        return json.dumps(record, ensure_ascii=False, default=str)

    def _to_document(self, record: dict[str, Any], index: int) -> ExtractedDocument | None:
        record_id = record.get(self.id_field)
        external_id = str(record_id) if record_id is not None else str(index)
        title_value = record.get(self.title_field) if self.title_field else None
        title = str(title_value) if title_value is not None else f"{self.endpoint}#{external_id}"

        content = self._record_content(record)
        if not content.strip():
            return None

        updated = record.get(self.updated_field) if self.updated_field else None
        allowed_users = parse_acl(record.get(self.acl_user_field)) if self.acl_user_field else []
        allowed_roles = parse_acl(record.get(self.acl_role_field)) if self.acl_role_field else []

        return ExtractedDocument(
            title=title,
            content=content,
            source_type="txt",
            url=f"{self.base_url}{self.endpoint}/{external_id}",
            external_id=external_id,
            last_modified=updated if isinstance(updated, datetime) else None,
            allowed_users=allowed_users,
            allowed_roles=allowed_roles,
            metadata={"connector": "rest", "endpoint": self.endpoint, "record_id": external_id},
        )

    # ── BaseConnector interface ─────────────────────────────────────────────

    def test_connection(self) -> bool:
        """Issue a minimal request against the endpoint to validate auth."""
        client = self._get_client()
        try:
            response = client.request(
                self.method, f"{self.base_url}{self.endpoint}", params=self.static_params
            )
            response.raise_for_status()
            return True
        except Exception as exc:
            raise ConnectionError(f"REST connection failed: {exc}") from exc

    def sync(self, since: datetime | None = None) -> list[ExtractedDocument]:
        """Fetch records across pages, optionally only those changed since ``since``."""
        client = self._get_client()
        url = f"{self.base_url}{self.endpoint}"
        documents: list[ExtractedDocument] = []

        page = self.start_page
        offset = 0
        cursor: Any = None

        while len(documents) < self.max_records:
            params: dict[str, Any] = dict(self.static_params)

            if self.pagination_type in ("page", "offset"):
                params[self.size_param] = self.page_size
            if self.pagination_type == "page":
                params[self.page_param] = page
            elif self.pagination_type == "offset":
                params[self.offset_param] = offset
            elif self.pagination_type == "cursor" and cursor is not None:
                params[self.cursor_param] = cursor
            if since is not None and self.since_param:
                params[self.since_param] = since.isoformat()

            self._rate_limiter.acquire()
            response = client.request(self.method, url, params=params)
            response.raise_for_status()
            payload = response.json()

            page_records = self._extract_records(payload)
            if not page_records:
                break

            for record in page_records:
                if len(documents) >= self.max_records:
                    break
                document = self._to_document(record, index=len(documents))
                if document is not None:
                    documents.append(document)

            if len(documents) >= self.max_records:
                break

            # Advance pagination
            if self.pagination_type == "none":
                break
            if self.pagination_type == "page":
                if len(page_records) < self.page_size:
                    break
                page += 1
            elif self.pagination_type == "offset":
                if len(page_records) < self.page_size:
                    break
                offset += self.page_size
            elif self.pagination_type == "cursor":
                cursor = _dig(payload, str(self.cursor_path)) if self.cursor_path else None
                if not cursor:
                    break
            else:
                break

        logger.info("RestApiConnector synced %d records from %s", len(documents), self.endpoint)
        return documents
