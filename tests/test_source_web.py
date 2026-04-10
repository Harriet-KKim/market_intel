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


def test_web_source_returns_empty_on_network_error(monkeypatch):
    """L13: httpx.get가 예외를 던져도 빈 리스트 반환, 크래시 안 함."""
    from src.sources.web import WebSource
    import httpx

    def raise_error(url, **kwargs):
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr("httpx.get", raise_error)
    source = WebSource()
    items = source.fetch_from_url("https://example.com/page")
    assert items == []
