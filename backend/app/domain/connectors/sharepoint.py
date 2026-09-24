"""OpenNotebook — SharePoint connector (Microsoft Graph).

Ingests files from a SharePoint document library via Microsoft Graph:
- OAuth2 client-credentials (app registration) or a pre-obtained access token.
- Site/drive resolution by ``site_id`` or ``site_hostname`` + ``site_path``.
- Recursive listing of a drive root/folder with ``@odata.nextLink`` pagination.
- Incremental sync by ``lastModifiedDateTime``.
- Optional default ACLs stamped on every document.

The HTTP client is injectable so tests can supply ``httpx.MockTransport``; the
Graph base URL is overridable via ``graph_base_url`` for the same reason.

Config (``config_json`` for a connector of type ``sharepoint``):
    tenant_id             : str   Azure AD tenant (for token exchange)
    client_id             : str
    client_secret         : str
    access_token          : str   optional; skips token exchange
    site_id               : str   Graph site id (optional if host+path given)
    site_hostname         : str   e.g. "contoso.sharepoint.com"
    site_path             : str   e.g. "/sites/Eng"
    drive_id              : str   optional; default drive used otherwise
    folder_path           : str   optional subfolder (e.g. "Shared Documents/Reports")
    extensions            : list  default [.pdf, .docx, .txt, .md]
    max_files             : int   default 500
    default_allowed_roles : list
    default_allowed_users : list
    verify_ssl            : bool  default true
    max_per_second        : float default 5
    graph_base_url        : str   default "https://graph.microsoft.com/v1.0"
    login_url             : str   default "https://login.microsoftonline.com"
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from app.domain.connectors.base import BaseConnector, ExtractedDocument
from app.domain.connectors.rate_limit import RateLimiter
from app.domain.connectors.timeutil import ensure_utc

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".txt": "txt",
    ".md": "md",
}


class SharePointConnector(BaseConnector):
    """Connector for SharePoint document libraries via Microsoft Graph."""

    def __init__(self, config: dict[str, Any], client: Any | None = None) -> None:
        super().__init__(config)
        self.tenant_id = config.get("tenant_id")
        self.client_id = config.get("client_id")
        self.client_secret = config.get("client_secret")
        self.access_token = config.get("access_token")
        self.login_url = str(config.get("login_url", "https://login.microsoftonline.com")).rstrip(
            "/"
        )
        self.graph_base_url = str(
            config.get("graph_base_url", "https://graph.microsoft.com/v1.0")
        ).rstrip("/")

        self.site_id = config.get("site_id")
        self.site_hostname = config.get("site_hostname")
        self.site_path = config.get("site_path")
        self.drive_id = config.get("drive_id")
        self.folder_path = (config.get("folder_path") or "").strip("/")

        extensions = config.get("extensions")
        self.extensions = (
            {str(e).lower() for e in extensions} if extensions else set(_SUPPORTED_EXTENSIONS)
        )
        self.max_files = int(config.get("max_files", 500))
        self.default_allowed_roles = list(config.get("default_allowed_roles") or [])
        self.default_allowed_users = list(config.get("default_allowed_users") or [])
        self.verify_ssl = bool(config.get("verify_ssl", True))
        self._client = client
        self._rate_limiter = RateLimiter(float(config.get("max_per_second", 5)))

        if not self.site_id and not (self.site_hostname and self.site_path):
            raise ValueError(
                "SharePointConnector requires 'site_id' or 'site_hostname'+'site_path'"
            )

    # ── Auth / client ───────────────────────────────────────────────────────

    def _ensure_auth(self) -> None:
        if self.access_token:
            return
        import httpx

        if not (self.tenant_id and self.client_id and self.client_secret):
            raise ValueError(
                "SharePointConnector requires 'access_token' or "
                "'tenant_id'+'client_id'+'client_secret'"
            )

        client = self._client or httpx.Client(timeout=30.0, verify=self.verify_ssl)
        try:
            response = client.post(
                f"{self.login_url}/{self.tenant_id}/oauth2/v2.0/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": str(self.client_id),
                    "client_secret": str(self.client_secret),
                    "scope": "https://graph.microsoft.com/.default",
                },
            )
            response.raise_for_status()
            self.access_token = response.json().get("access_token")
        except Exception as exc:
            raise ConnectionError(f"SharePoint authentication failed: {exc}") from exc
        finally:
            if self._client is None:
                client.close()

    def _build_client(self) -> Any:
        import httpx

        self._ensure_auth()
        return httpx.Client(
            headers={"Authorization": f"Bearer {self.access_token}", "Accept": "application/json"},
            timeout=60.0,
            verify=self.verify_ssl,
            follow_redirects=True,
        )

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = self._build_client()
        return self._client

    # ── Resolution ──────────────────────────────────────────────────────────

    def _resolve_site_id(self) -> str:
        if self.site_id:
            return str(self.site_id)
        client = self._get_client()
        self._rate_limiter.acquire()
        response = client.get(f"{self.graph_base_url}/sites/{self.site_hostname}:{self.site_path}")
        response.raise_for_status()
        self.site_id = response.json()["id"]
        return str(self.site_id)

    def _resolve_drive_id(self) -> str:
        if self.drive_id:
            return str(self.drive_id)
        site_id = self._resolve_site_id()
        client = self._get_client()
        self._rate_limiter.acquire()
        response = client.get(f"{self.graph_base_url}/sites/{site_id}/drive")
        response.raise_for_status()
        self.drive_id = response.json()["id"]
        return str(self.drive_id)

    def _children_url(self, drive_id: str) -> str:
        if self.folder_path:
            return f"{self.graph_base_url}/drives/{drive_id}/root:/{self.folder_path}:/children"
        return f"{self.graph_base_url}/drives/{drive_id}/root/children"

    # ── Mapping ─────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_dt(value: Any) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _download_item(self, drive_id: str, item_id: str) -> bytes:
        client = self._get_client()
        self._rate_limiter.acquire()
        response = client.get(f"{self.graph_base_url}/drives/{drive_id}/items/{item_id}/content")
        response.raise_for_status()
        return response.content

    def _to_document(self, drive_id: str, item: dict[str, Any]) -> ExtractedDocument | None:
        name = str(item.get("name") or "")
        suffix = Path(name).suffix.lower()
        if suffix not in self.extensions:
            return None

        item_id = str(item.get("id") or "")
        data = self._download_item(drive_id, item_id)
        if not data:
            return None

        return ExtractedDocument(
            title=name,
            content=data,
            source_type=_SUPPORTED_EXTENSIONS[suffix],
            url=item.get("webUrl"),
            external_id=item_id,
            last_modified=self._parse_dt(item.get("lastModifiedDateTime")),
            allowed_users=list(self.default_allowed_users),
            allowed_roles=list(self.default_allowed_roles),
            metadata={
                "connector": "sharepoint",
                "drive_id": drive_id,
                "item_id": item_id,
                "size_bytes": len(data),
                "checksum": hashlib.sha256(data).hexdigest(),
            },
        )

    # ── BaseConnector interface ─────────────────────────────────────────────

    def test_connection(self) -> bool:
        """Resolve the site/drive to validate auth and configuration."""
        try:
            self._resolve_site_id()
            self._resolve_drive_id()
            return True
        except Exception as exc:
            if isinstance(exc, ConnectionError):
                raise
            raise ConnectionError(f"SharePoint connection failed: {exc}") from exc

    def sync(self, since: datetime | None = None) -> list[ExtractedDocument]:
        """List drive items (with pagination) and download supported files."""
        client = self._get_client()
        drive_id = self._resolve_drive_id()

        since = ensure_utc(since)
        documents: list[ExtractedDocument] = []
        url: str | None = self._children_url(drive_id)

        while url and len(documents) < self.max_files:
            self._rate_limiter.acquire()
            response = client.get(url)
            response.raise_for_status()
            payload = response.json()

            for item in payload.get("value", []):
                if len(documents) >= self.max_files:
                    break
                if "file" not in item:
                    continue  # skip folders / bundles
                if since is not None:
                    modified = self._parse_dt(item.get("lastModifiedDateTime"))
                    if modified is not None and modified < since:
                        continue
                document = self._to_document(drive_id, item)
                if document is not None:
                    documents.append(document)

            url = payload.get("@odata.nextLink")

        logger.info("SharePointConnector synced %d files", len(documents))
        return documents
