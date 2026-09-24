"""OpenNotebook — SQL database connector.

Ingests rows from a relational table as text documents. Supports:
- arbitrary DSN (SQLite, PostgreSQL, MySQL via SQLAlchemy)
- composed or single-column content
- incremental sync via an ``updated_at``-style watermark column
- per-row ACLs read from configurable user/role columns
- optional client-side rate limiting

Config (``config_json`` for a connector of type ``sql``):
    dsn                 : SQLAlchemy DSN (required)
    table               : table name (required)
    id_column           : primary/key column (default: "id")
    title_column        : column used as the document title
    content_column      : single column used as document content
    text_columns        : list of columns concatenated to form content
    updated_column      : timestamp column for incremental sync
    acl_user_column     : column holding allowed users (JSON array or CSV)
    acl_role_column     : column holding allowed roles (JSON array or CSV)
    where               : optional raw SQL predicate
    max_rows            : cap on rows fetched per sync (default: 500)
    source_type         : downstream extractor type (default: "txt")
    max_per_second      : optional client-side rate limit

Rows are emitted as plain text so the existing ``txt`` extractor handles them
without schema changes to the ``sources.source_type`` check constraint.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from app.domain.connectors.base import BaseConnector, ExtractedDocument
from app.domain.connectors.rate_limit import RateLimiter

logger = logging.getLogger(__name__)


class SqlConnector(BaseConnector):
    """Connector for relational database tables."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.dsn = str(config.get("dsn") or config.get("connection_string") or "").strip()
        self.table_name = str(config.get("table") or "").strip()
        if not self.dsn:
            raise ValueError("dsn is required for SqlConnector")
        if not self.table_name:
            raise ValueError("table is required for SqlConnector")

        self.id_column = str(config.get("id_column", "id"))
        self.title_column = config.get("title_column")
        self.content_column = config.get("content_column")
        self.text_columns = list(config.get("text_columns") or [])
        self.updated_column = config.get("updated_column")
        self.acl_user_column = config.get("acl_user_column")
        self.acl_role_column = config.get("acl_role_column")
        self.where = config.get("where")
        self.max_rows = int(config.get("max_rows", 500))
        self.source_type = str(config.get("source_type", "txt"))

        max_per_second = config.get("max_per_second")
        self.rate_limiter = RateLimiter(float(max_per_second)) if max_per_second else None

    # ── Internal helpers ────────────────────────────────────────────────────

    def _engine(self) -> Any:
        from sqlalchemy import create_engine

        return create_engine(self.dsn)

    @staticmethod
    def _parse_acl(value: Any) -> list[str]:
        """Parse an ACL cell that may be a list, JSON array string, or CSV."""
        if value is None:
            return []
        if isinstance(value, (list, tuple, set)):
            return [str(v) for v in value if v]
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            if text.startswith("["):
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, list):
                        return [str(v) for v in parsed if v]
                except json.JSONDecodeError:
                    pass
            return [part.strip() for part in text.split(",") if part.strip()]
        return [str(value)]

    @staticmethod
    def _coerce_datetime(value: Any) -> datetime | None:
        return value if isinstance(value, datetime) else None

    def _compose_content(self, row: dict[str, Any]) -> str:
        if self.text_columns:
            parts = [
                str(row[col]) for col in self.text_columns if col in row and row[col] is not None
            ]
            return "\n\n".join(parts)
        if self.content_column and row.get(self.content_column) is not None:
            return str(row[self.content_column])
        excluded = {
            self.acl_user_column,
            self.acl_role_column,
            self.updated_column,
        }
        return "\n".join(
            f"{key}: {value}"
            for key, value in row.items()
            if value is not None and key not in excluded
        )

    # ── BaseConnector interface ─────────────────────────────────────────────

    def test_connection(self) -> bool:
        """Verify the DSN is reachable and the configured table exists."""
        from sqlalchemy import inspect

        engine = self._engine()
        try:
            inspector = inspect(engine)
            if not inspector.has_table(self.table_name):
                raise ConnectionError(f"Table {self.table_name!r} not found")
            return True
        except ConnectionError:
            raise
        except Exception as exc:
            raise ConnectionError(f"SQL connection failed: {exc}") from exc
        finally:
            engine.dispose()

    def sync(self, since: datetime | None = None) -> list[ExtractedDocument]:
        """Fetch rows (optionally changed since ``since``) as text documents."""
        from sqlalchemy import MetaData, Table, select, text

        engine = self._engine()
        documents: list[ExtractedDocument] = []
        try:
            metadata = MetaData()
            table = Table(self.table_name, metadata, autoload_with=engine)

            stmt = select(table)
            if since is not None and self.updated_column and self.updated_column in table.c:
                stmt = stmt.where(table.c[self.updated_column] >= since)
            if self.where:
                stmt = stmt.where(text(self.where))
            stmt = stmt.limit(self.max_rows)

            with engine.connect() as conn:
                rows = conn.execute(stmt).mappings().all()

            for raw_row in rows:
                if self.rate_limiter is not None:
                    self.rate_limiter.acquire()

                row = dict(raw_row)
                row_id = str(row.get(self.id_column, ""))
                title_value = row.get(self.title_column) if self.title_column else None
                title = (
                    str(title_value) if title_value is not None else f"{self.table_name}#{row_id}"
                )
                content = self._compose_content(row)
                if not content.strip():
                    continue

                documents.append(
                    ExtractedDocument(
                        title=title,
                        content=content,
                        source_type=self.source_type,
                        url=f"sql://{self.table_name}/{row_id}",
                        external_id=row_id,
                        last_modified=(
                            self._coerce_datetime(row.get(self.updated_column))
                            if self.updated_column
                            else None
                        ),
                        allowed_users=(
                            self._parse_acl(row.get(self.acl_user_column))
                            if self.acl_user_column
                            else []
                        ),
                        allowed_roles=(
                            self._parse_acl(row.get(self.acl_role_column))
                            if self.acl_role_column
                            else []
                        ),
                        metadata={
                            "connector": "sql",
                            "table": self.table_name,
                            "row_id": row_id,
                        },
                    )
                )

            logger.info(
                "SqlConnector synced %d rows from table %s",
                len(documents),
                self.table_name,
            )
            return documents
        finally:
            engine.dispose()
