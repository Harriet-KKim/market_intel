from __future__ import annotations

from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import feedparser

from src.sources.base import BaseSource, CollectedItem


class RssSource(BaseSource):
    source_type = "news"

    def fetch(self, company_id: str, keywords: list[str]) -> list[CollectedItem]:
        """Not used directly — use fetch_from_url for RSS sources."""
        return []

    def fetch_from_url(self, feed_url: str) -> list[CollectedItem]:
        """Fetch and parse an RSS feed URL."""
        feed = feedparser.parse(feed_url)

        # 로컬 패치 K1 해결: source_name을 feed title로 폴백.
        # 원본 플랜은 source_name=feed_url로 저장해서 registry.get_reputation_score()
        # 가 항상 fallback(None)을 반환했습니다. feed.feed.title이 1순위,
        # 없으면 도메인(netloc), 최후 fallback은 feed_url 그대로.
        feed_meta = getattr(feed, "feed", {}) or {}
        feed_title = feed_meta.get("title") if hasattr(feed_meta, "get") else None
        source_name = feed_title or urlparse(feed_url).netloc or feed_url

        items = []

        for entry in feed.get("entries", []):
            published_at = None
            if "published" in entry:
                try:
                    dt = parsedate_to_datetime(entry["published"])
                    published_at = dt.isoformat()
                except (ValueError, TypeError):
                    published_at = entry.get("published")

            items.append(
                CollectedItem(
                    title=entry.get("title", ""),
                    url=entry.get("link", ""),
                    body=entry.get("summary", ""),
                    source_type=self.source_type,
                    source_name=source_name,
                    author=entry.get("author"),
                    published_at=published_at,
                    language=None,
                    content_type="article",
                )
            )

        return items
