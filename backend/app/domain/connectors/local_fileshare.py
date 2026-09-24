"""OpenNotebook — Local file-share connector.

Ingests documents from a mounted directory (SMB/NFS share or local folder):
PDF, DOCX, TXT, and Markdown. Computes a SHA-256 checksum per file so that
downstream ingestion can deduplicate and re-runs are idempotent.

Config (passed as ``config_json`` on a connector of type ``fileshare``):
    root_path : str   absolute path to the share/folder (required)
    recursive : bool  recurse into subdirectories (default: true)
    max_files : int   cap on documents fetched per sync (default: 500)
    extensions: list  override the supported extension set
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.domain.connectors.base import BaseConnector, ExtractedDocument

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".txt": "txt",
    ".md": "md",
}


class LocalFileShareConnector(BaseConnector):
    """Connector for local/mounted file shares (PDF, DOCX, TXT, MD)."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        raw_root = config.get("root_path") or config.get("path") or ""
        if not str(raw_root).strip():
            raise ValueError("root_path is required for LocalFileShareConnector")

        self.root = Path(str(raw_root)).expanduser()
        self.recursive = bool(config.get("recursive", True))
        self.max_files = int(config.get("max_files", 500))

        extensions = config.get("extensions")
        if extensions:
            self.extensions = {str(e).lower() for e in extensions}
        else:
            self.extensions = set(_SUPPORTED_EXTENSIONS)

    def test_connection(self) -> bool:
        """Verify the root path exists, is a directory, and is readable."""
        if not self.root.exists():
            raise ConnectionError(f"File share path does not exist: {self.root}")
        if not self.root.is_dir():
            raise ConnectionError(f"File share path is not a directory: {self.root}")
        try:
            next(self.root.iterdir(), None)
        except PermissionError as exc:
            raise ConnectionError(f"File share path is not readable: {self.root}") from exc
        return True

    def _iter_files(self) -> list[Path]:
        pattern = "**/*" if self.recursive else "*"
        files = [
            p
            for p in self.root.glob(pattern)
            if p.is_file() and p.suffix.lower() in self.extensions
        ]
        return sorted(files)

    def sync(self) -> list[ExtractedDocument]:
        """Walk the share and return supported documents with checksums."""
        documents: list[ExtractedDocument] = []

        for path in self._iter_files():
            if len(documents) >= self.max_files:
                logger.info(
                    "LocalFileShareConnector hit max_files=%d for %s",
                    self.max_files,
                    self.root,
                )
                break

            try:
                data = path.read_bytes()
            except OSError as exc:
                logger.warning("Skipping unreadable file %s: %s", path, exc)
                continue

            checksum = hashlib.sha256(data).hexdigest()
            source_type = _SUPPORTED_EXTENSIONS[path.suffix.lower()]
            rel = path.relative_to(self.root).as_posix()
            last_modified = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)

            documents.append(
                ExtractedDocument(
                    title=path.name,
                    content=data,
                    source_type=source_type,
                    url=f"file://{path.as_posix()}",
                    external_id=checksum,
                    last_modified=last_modified,
                    metadata={
                        "relative_path": rel,
                        "size_bytes": len(data),
                        "checksum": checksum,
                        "connector": "fileshare",
                    },
                )
            )

        logger.info(
            "LocalFileShareConnector synced %d files from %s",
            len(documents),
            self.root,
        )
        return documents
