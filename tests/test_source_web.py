def test_web_source_fetches_html(monkeypatch):
    from src.sources.web import WebSource

    class MockResponse:
        status_code = 200
        text = "<html><body><h1>Press Release</h1><p>Figure AI raises $500M.</p></body></html>"

    monkeypatch.setattr("httpx.get", lambda url, **kwargs: MockResponse())

    source = WebSource()
    items = source.fetch_from_url("https://figure.ai/news/series-b")

    assert len(items) == 1
    assert "<html>" in items[0].body  # Raw HTML, Agent will extract
    assert items[0].source_type == "web"
    assert items[0].content_type == "raw_html"
