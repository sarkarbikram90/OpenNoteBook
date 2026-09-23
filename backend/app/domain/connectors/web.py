"""OpenNotebook — Enterprise Web Crawler Connector.

Syncs documentation sites, wikis, and web portals with link traversal,
domain restriction, and HTML-to-text extraction.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from app.domain.connectors.base import BaseConnector, ExtractedDocument

logger = logging.getLogger(__name__)


class WebConnector(BaseConnector):
    """Crawler connector for web documentation and portals."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.base_url = config.get("base_url", "").strip()
        if not self.base_url:
            raise ValueError("base_url is required for WebConnector")

        parsed = urlparse(self.base_url)
        self.default_domain = parsed.netloc
        self.allowed_domains = set(config.get("allowed_domains") or [self.default_domain])
        self.max_pages = int(config.get("max_pages", 10))
        self.max_depth = int(config.get("max_depth", 1))

    def test_connection(self) -> bool:
        """Validate that the target base URL is reachable."""
        import urllib.request

        req = urllib.request.Request(
            self.base_url,
            headers={"User-Agent": "OpenNotebookEnterpriseCrawler/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status in (200, 301, 302)
        except Exception as exc:
            logger.error("WebConnector connectivity test failed for %s: %s", self.base_url, exc)
            raise ConnectionError(f"Could not reach {self.base_url}: {exc}") from exc

    def _extract_page_content(self, html: str) -> tuple[str, str]:
        """Extract clean page title and text content from HTML."""
        # Extract title
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else "Web Document"

        # Try trafilatura if available for high-quality extraction
        try:
            import trafilatura
            extracted = trafilatura.extract(html, include_links=False)
            if extracted and len(extracted.strip()) > 50:
                return title, extracted.strip()
        except ImportError:
            pass

        # Fallback regex-based clean extraction
        # Remove scripts and styles
        clean = re.sub(r"<(script|style)[^>]*>[\s\S]*?</\1>", " ", html, flags=re.IGNORECASE)
        # Remove html tags
        clean = re.sub(r"<[^>]+>", " ", clean)
        # Collapse whitespace
        clean = re.sub(r"\s+", " ", clean).strip()
        return title, clean

    def _extract_links(self, html: str, current_url: str) -> list[str]:
        """Extract outgoing links matching allowed domains."""
        hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, re.IGNORECASE)
        valid_links = []
        for h in hrefs:
            full = urljoin(current_url, h)
            parsed = urlparse(full)
            if parsed.scheme in ("http", "https") and parsed.netloc in self.allowed_domains:
                # Remove fragment
                clean_link = full.split("#")[0]
                valid_links.append(clean_link)
        return list(set(valid_links))

    def sync(self) -> list[ExtractedDocument]:
        """Crawl the website up to max_pages and max_depth."""
        import urllib.request

        visited: set[str] = set()
        queue: list[tuple[str, int]] = [(self.base_url, 0)]
        documents: list[ExtractedDocument] = []

        headers = {"User-Agent": "OpenNotebookEnterpriseCrawler/1.0"}

        while queue and len(documents) < self.max_pages:
            current_url, depth = queue.pop(0)
            if current_url in visited:
                continue
            visited.add(current_url)

            try:
                req = urllib.request.Request(current_url, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status != 200:
                        continue
                    charset = resp.headers.get_content_charset() or "utf-8"
                    html = resp.read().decode(charset, errors="ignore")

                title, text = self._extract_page_content(html)
                if len(text) >= 100:  # Ignore empty or shell pages
                    documents.append(
                        ExtractedDocument(
                            title=title or current_url,
                            content=text,
                            source_type="url",
                            url=current_url,
                            metadata={"crawl_depth": depth, "domain": urlparse(current_url).netloc},
                        )
                    )

                # Add outgoing links to queue if depth limit allows
                if depth < self.max_depth:
                    links = self._extract_links(html, current_url)
                    for link in links:
                        if link not in visited:
                            queue.append((link, depth + 1))

            except Exception as exc:
                logger.warning("Failed to crawl page %s: %s", current_url, exc)
                continue

        logger.info("WebConnector finished crawl for %s: %d documents extracted", self.base_url, len(documents))
        return documents
