from __future__ import annotations

import logging

import httpx

from src.sources.base import BaseSource, CollectedItem

logger = logging.getLogger(__name__)


class WebSource(BaseSource):
    source_type = "web"

    def fetch(self, company_id: str, keywords: list[str]) -> list[CollectedItem]:
        return []

    def fetch_from_url(self, url: str) -> list[CollectedItem]:
        """Fetch raw HTML from a URL. Content extraction is handled by Agent."""
        try:
            response = httpx.get(url, follow_redirects=True, timeout=30)
        except (httpx.HTTPError, OSError):
            logger.warning(f"Web fetch failed for {url}", exc_info=True)
            return []

        if response.status_code != 200:
            return []

        return [
            CollectedItem(
                title="",  # Agent will extract
                url=url,
                body=response.text,  # Raw HTML for Agent
                source_type=self.source_type,
                source_name=url,
                author=None,
                published_at=None,
                language=None,
                content_type="raw_html",  # Marks as unprocessed
            )
        ]
