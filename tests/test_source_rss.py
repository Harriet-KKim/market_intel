def test_rss_source_parses_feed(monkeypatch):
    from src.sources.rss import RssSource
    from src.sources.base import CollectedItem

    sample_feed = {
        "entries": [
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
    }

    import feedparser
    monkeypatch.setattr(feedparser, "parse", lambda url: sample_feed)

    source = RssSource()
    items = source.fetch_from_url("https://blogs.nvidia.com/feed/")

    assert len(items) == 2
    assert items[0].title == "NVIDIA GR00T 2.0 Launch"
    assert items[0].source_type == "news"
    assert items[0].url == "https://blogs.nvidia.com/groot-2"
