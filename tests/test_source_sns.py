def test_sns_source_placeholder():
    from src.sources.sns import SnsSource

    source = SnsSource()
    # SNS requires API keys; test the interface exists
    items = source.fetch("nvidia", ["world-model"])

    assert isinstance(items, list)


def test_sns_source_returns_empty_on_reddit_error(monkeypatch):
    """L13: httpx.get가 예외를 던져도 빈 리스트 반환, 크래시 안 함."""
    from src.sources.sns import SnsSource

    def raise_error(url, **kwargs):
        raise OSError("Connection refused")

    monkeypatch.setattr("httpx.get", raise_error)
    source = SnsSource()
    items = source.fetch_reddit("robotics", "humanoid")
    assert items == []
