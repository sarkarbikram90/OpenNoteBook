"""OpenNotebook — Enterprise Connector Base Interface.

Defines the contract for external enterprise data source connectors:
- Connectivity validation
- Incremental / batch synchronization
- Uniform document extraction and metadata mapping
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ExtractedDocument:
    """Standardized document extracted by an enterprise connector."""

    title: str
    content: str | bytes
    source_type: str  # "txt", "md", "pdf", "docx", "url"
    url: str | None = None
    external_id: str | None = None
    last_modified: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SyncResult:
    """Outcome of a connector synchronization execution."""

    documents_found: int = 0
    documents_synced: int = 0
    documents_skipped: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        """Return True if execution completed without fatal errors."""
        return len(self.errors) == 0


class BaseConnector(ABC):
    """Abstract Base Class for Enterprise Data Connectors."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    @abstractmethod
    def test_connection(self) -> bool:
        """Verify connectivity and credentials against the external service.

        Returns:
            True if connection is successful, raises Exception otherwise.
        """
        ...

    @abstractmethod
    def sync(self) -> list[ExtractedDocument]:
        """Fetch and extract documents from the external source.

        Returns:
            List of standardized ExtractedDocument instances.
        """
        ...

    def get_metadata(self) -> dict[str, Any]:
        """Return connector runtime metadata."""
        return {
            "connector_type": self.__class__.__name__,
            "configured_at": datetime.utcnow().isoformat(),
        }
