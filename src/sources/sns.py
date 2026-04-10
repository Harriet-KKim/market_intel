from __future__ import annotations

import logging

from src.sources.base import BaseSource, CollectedItem

logger = logging.getLogger(__name__)


class SnsSource(BaseSource):
    source_type = "sns"

    def fetch(self, company_id: str, keywords: list[str]) -> list[CollectedItem]:
        """SNS fetch requires API keys configured per platform.
        Returns empty list if no API is configured.
        Platforms: X/Twitter, Reddit, HackerNews.
        """
        # Placeholder: actual API integration depends on available keys
        # Each platform will be a method: fetch_reddit, fetch_hackernews, etc.
        return []

    def fetch_reddit(self, subreddit: str, query: str) -> list[CollectedItem]:
        """Fetch posts from Reddit matching query."""
        import httpx

        url = f"https://www.reddit.com/r/{subreddit}/search.json"
        params = {"q": query, "sort": "new", "limit": 25, "restrict_sr": "on"}
        headers = {"User-Agent": "market-intel/0.1"}

        try:
            response = httpx.get(url, params=params, headers=headers, timeout=30)
        except (httpx.HTTPError, OSError):
            logger.warning(f"Reddit fetch failed for r/{subreddit}", exc_info=True)
            return []

        if response.status_code != 200:
            return []

        items = []
        for post in response.json().get("data", {}).get("children", []):
            data = post["data"]
            items.append(
                CollectedItem(
                    title=data.get("title", ""),
                    url=f"https://reddit.com{data.get('permalink', '')}",
                    body=data.get("selftext", ""),
                    source_type=self.source_type,
                    source_name="Reddit",
                    author=data.get("author"),
                    published_at=None,
                    language="en",
                    content_type="post",
                )
            )
        return items
