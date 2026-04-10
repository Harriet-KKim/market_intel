def test_rss_source_parses_feed(monkeypatch):
    from src.sources.rss import RssSource
    from src.sources.base import CollectedItem

    # feedparser.parse는 FeedParserDict를 반환. `.feed` 어트리뷰트와 `.get`을
    # 둘 다 지원해야 해서 간단한 mock 클래스로 흉내냅니다.
    class MockFeedResult:
        feed = {"title": "NVIDIA Blog"}
        _entries = [
            {
                "title": "NVIDIA GR00T 2.0 Launch",
                "link": "https://blogs.nvidia.com/groot-2",
                "summary": "NVIDIA launches GR00T 2.0 for humanoid robots.",
                "author": "NVIDIA Blog",
                "published": "Wed, 08 Apr 2026 12:00:00 GMT",
            },
            {
                "title": "Unrelated Post",
                "link": "https://blogs.nvidia.com/gaming",
                "summary": "New GPU for gaming.",
                "author": "NVIDIA Blog",
                "published": "Wed, 08 Apr 2026 10:00:00 GMT",
            },
        ]
        def get(self, key, default=None):
            if key == "entries":
                return self._entries
            return default

    import feedparser
    monkeypatch.setattr(feedparser, "parse", lambda url: MockFeedResult())

    source = RssSource()
    items = source.fetch_from_url("https://blogs.nvidia.com/feed/")

    assert len(items) == 2
    assert items[0].title == "NVIDIA GR00T 2.0 Launch"
    assert items[0].source_type == "news"
    assert items[0].url == "https://blogs.nvidia.com/groot-2"
    # 로컬 패치 K1 해결: source_name이 feed title로 세팅되어야 함 (URL이 아님).
    # 이 값이 registry.get_reputation_score()로 tier 점수를 조회하는 키가 됩니다.
    assert items[0].source_name == "NVIDIA Blog"


def test_rss_source_fallback_to_domain(monkeypatch):
    """feed.title이 없으면 도메인으로 폴백해야 한다."""
    from src.sources.rss import RssSource

    class NoTitleFeed:
        feed = {}  # title 없음
        _entries = [{"title": "X", "link": "https://example.com/a", "summary": ""}]
        def get(self, key, default=None):
            return self._entries if key == "entries" else default

    import feedparser
    monkeypatch.setattr(feedparser, "parse", lambda url: NoTitleFeed())

    items = RssSource().fetch_from_url("https://example.com/feed.xml")
    assert items[0].source_name == "example.com"


def test_rss_source_returns_empty_on_network_error(monkeypatch):
    """L13: feedparser.parse가 예외를 던져도 빈 리스트 반환, 크래시 안 함."""
    from src.sources.rss import RssSource
    import feedparser

    def raise_error(url):
        raise OSError("Network unreachable")

    monkeypatch.setattr(feedparser, "parse", raise_error)
    source = RssSource()
    items = source.fetch_from_url("https://example.com/feed.xml")
    assert items == []
