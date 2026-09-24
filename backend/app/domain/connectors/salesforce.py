"""OpenNotebook — Salesforce connector (REST + SOQL).

Fetches records from Salesforce objects via the REST query API with SOQL,
follows ``nextRecordsUrl`` pagination, supports incremental sync on
``LastModifiedDate``, and maps configured fields + ACLs to documents.

Auth (in order of preference):
    access_token + instance_url        pre-obtained session token
    client_id + client_secret          OAuth2 client-credentials grant
    + username + password              OAuth2 password grant
    (login_url defaults to https://login.salesforce.com)

The HTTP client is injectable so tests can supply ``httpx.MockTransport``.

Config (``config_json`` for a connector of type ``salesforce``):
    instance_url    : str   e.g. "https://acme.my.salesforce.com"
    access_token    : str   session token (or obtained via OAuth)
    client_id       : str
    client_secret   : str
    username        : str   (password grant)
    password        : str
    login_url       : str   default "https://login.salesforce.com"
    api_version     : str   default "60.0"
    soql            : str   explicit SOQL (overrides object/fields)
    object          : str   sObject name (e.g. "Knowledge__kav", "Account")
    fields          : list  fields to select
    where           : str   extra SOQL WHERE predicate
    id_field        : str   default "Id"
    title_field     : str
    content_field   : str
    text_fields     : list
    updated_field   : str   default "LastModifiedDate"
    acl_user_field  : str
    acl_role_field  : str
    max_records     : int   default 2000
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


class SalesforceConnector(BaseConnector):
    """Connector for Salesforce objects via SOQL."""

    def __init__(self, config: dict[str, Any], client: Any | None = None) -> None:
        super().__init__(config)
        self.instance_url = (config.get("instance_url") or "").rstrip("/") or None
        self.access_token = config.get("access_token")
        self.client_id = config.get("client_id")
        self.client_secret = config.get("client_secret")
        self.username = config.get("username")
        self.password = config.get("password")
        self.login_url = str(config.get("login_url", "https://login.salesforce.com")).rstrip("/")
        self.api_version = str(config.get("api_version", "60.0"))

        self.soql = config.get("soql")
        self.sobject = config.get("object") or config.get("sobject")
        self.fields = list(config.get("fields") or [])
        self.where = config.get("where")

        self.id_field = str(config.get("id_field", "Id"))
        self.title_field = config.get("title_field")
        self.content_field = config.get("content_field")
        self.text_fields = list(config.get("text_fields") or [])
        self.updated_field = config.get("updated_field", "LastModifiedDate")
        self.acl_user_field = config.get("acl_user_field")
        self.acl_role_field = config.get("acl_role_field")

        self.max_records = int(config.get("max_records", 2000))
        self.verify_ssl = bool(config.get("verify_ssl", True))
        self._client = client
        self._rate_limiter = RateLimiter(float(config.get("max_per_second", 5)))

        if not self.soql and not self.sobject:
            raise ValueError("SalesforceConnector requires 'soql' or 'object'")

    # ── Auth ────────────────────────────────────────────────────────────────

    def _ensure_auth(self) -> None:
        """Obtain an access token + instance URL when not supplied directly."""
        if self.access_token and self.instance_url:
            return

        import httpx

        if not (self.client_id and self.client_secret):
            raise ValueError(
                "SalesforceConnector requires 'access_token'+'instance_url' or "
                "'client_id'+'client_secret'"
            )

        data: dict[str, str] = {
            "client_id": str(self.client_id),
            "client_secret": str(self.client_secret),
        }
        if self.username and self.password:
            data.update(
                {
                    "grant_type": "password",
                    "username": str(self.username),
                    "password": str(self.password),
                }
            )
        else:
            data["grant_type"] = "client_credentials"

        client = self._client or httpx.Client(timeout=30.0, verify=self.verify_ssl)
        try:
            response = client.post(f"{self.login_url}/services/oauth2/token", data=data)
            response.raise_for_status()
            payload = response.json()
            self.access_token = payload.get("access_token")
            self.instance_url = (payload.get("instance_url") or self.instance_url or "").rstrip(
                "/"
            ) or None
        except Exception as exc:
            raise ConnectionError(f"Salesforce authentication failed: {exc}") from exc
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

    # ── SOQL / mapping ──────────────────────────────────────────────────────

    def _required_fields(self) -> list[str]:
        required = [self.id_field]
        for value in (self.title_field, self.content_field, self.updated_field):
            if value:
                required.append(str(value))
        required.extend(self.text_fields)
        for value in (self.acl_user_field, self.acl_role_field):
            if value:
                required.append(str(value))
        return list(dict.fromkeys(required))

    def _build_soql(self, since: datetime | None) -> str:
        if self.soql:
            base = str(self.soql)
            if since is not None and self.updated_field:
                timestamp = since.strftime("%Y-%m-%dT%H:%M:%SZ")
                connector = "AND" if " where " in base.lower() else "WHERE"
                base = f"{base} {connector} {self.updated_field} >= {timestamp}"
            return base

        fields = list(dict.fromkeys([*self.fields, *self._required_fields()]))
        query = f"SELECT {', '.join(fields)} FROM {self.sobject}"  # noqa: S608 (config-supplied, not user input)

        clauses: list[str] = []
        if self.where:
            clauses.append(str(self.where))
        if since is not None and self.updated_field:
            clauses.append(f"{self.updated_field} >= {since.strftime('%Y-%m-%dT%H:%M:%SZ')}")
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        if self.updated_field:
            query += f" ORDER BY {self.updated_field} ASC"
        return query

    @staticmethod
    def _parse_dt(value: Any) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _record_content(self, record: dict[str, Any]) -> str:
        if self.text_fields:
            return "\n\n".join(
                str(record[f]) for f in self.text_fields if record.get(f) is not None
            )
        if self.content_field and record.get(self.content_field) is not None:
            value = record[self.content_field]
            return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        return json.dumps(
            {k: v for k, v in record.items() if k != "attributes"},
            ensure_ascii=False,
            default=str,
        )

    def _to_document(self, record: dict[str, Any], index: int) -> ExtractedDocument | None:
        record_id = record.get(self.id_field) or record.get("Id")
        external_id = str(record_id) if record_id is not None else str(index)
        title_value = record.get(self.title_field) if self.title_field else None
        title = str(title_value) if title_value is not None else f"{self.sobject}#{external_id}"

        content = self._record_content(record)
        if not content.strip():
            return None

        return ExtractedDocument(
            title=title,
            content=content,
            source_type="txt",
            url=f"{self.instance_url}/{external_id}",
            external_id=external_id,
            last_modified=self._parse_dt(record.get(self.updated_field))
            if self.updated_field
            else None,
            allowed_users=parse_acl(record.get(self.acl_user_field)) if self.acl_user_field else [],
            allowed_roles=parse_acl(record.get(self.acl_role_field)) if self.acl_role_field else [],
            metadata={"connector": "salesforce", "sobject": self.sobject, "record_id": external_id},
        )

    # ── BaseConnector interface ─────────────────────────────────────────────

    def test_connection(self) -> bool:
        """Validate auth by issuing a minimal query or metadata request."""
        client = self._get_client()
        base = f"{self.instance_url}/services/data/v{self.api_version}"
        try:
            if self.sobject:
                response = client.get(
                    f"{base}/query",
                    params={"q": f"SELECT Id FROM {self.sobject} LIMIT 1"},  # noqa: S608
                )
            else:
                response = client.get(f"{base}/sobjects")
            response.raise_for_status()
            return True
        except Exception as exc:
            raise ConnectionError(f"Salesforce connection failed: {exc}") from exc

    def sync(self, since: datetime | None = None) -> list[ExtractedDocument]:
        """Run the SOQL query and page through records."""
        client = self._get_client()
        query = self._build_soql(since)
        url = f"{self.instance_url}/services/data/v{self.api_version}/query"
        params: dict[str, Any] | None = {"q": query}

        documents: list[ExtractedDocument] = []
        while url and len(documents) < self.max_records:
            self._rate_limiter.acquire()
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()

            for record in payload.get("records", []):
                if len(documents) >= self.max_records:
                    break
                document = self._to_document(record, index=len(documents))
                if document is not None:
                    documents.append(document)

            if payload.get("done"):
                break
            next_url = payload.get("nextRecordsUrl")
            if not next_url:
                break
            url = f"{self.instance_url}{next_url}"
            params = None

        logger.info("SalesforceConnector synced %d records", len(documents))
        return documents
