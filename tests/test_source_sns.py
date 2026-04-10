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


def test_sns_source_fetches_reddit_posts(monkeypatch):
    """L14: 정상 Reddit 응답이 CollectedItem으로 올바르게 파싱된다.

    L13 테스트는 예외 경로만 커버한다. 실제 search.json 응답을 stub해서
    Reddit 스키마 변경이 생겼을 때 조기에 감지할 수 있는 스모크 테스트가 필요하다.
    """
    from src.sources.sns import SnsSource

    mock_json = {
        "data": {
            "children": [
                {
                    "data": {
                        "title": "NVIDIA GR00T announcement",
                        "permalink": "/r/robotics/comments/abc123/nvidia_groot/",
                        "selftext": "NVIDIA announced GR00T 2.0 for humanoid robots.",
                        "author": "robotics_fan",
                    }
                },
                {
                    "data": {
                        "title": "Tesla Optimus update",
                        "permalink": "/r/robotics/comments/def456/tesla_optimus/",
                        "selftext": "New Optimus video released.",
                        "author": "tesla_watcher",
                    }
                },
            ]
        }
    }

    class MockResponse:
        status_code = 200

        def json(self):
            return mock_json

    monkeypatch.setattr("httpx.get", lambda *args, **kwargs: MockResponse())

    source = SnsSource()
    items = source.fetch_reddit("robotics", "humanoid")

    assert len(items) == 2

    first = items[0]
    assert first.title == "NVIDIA GR00T announcement"
    assert first.url == "https://reddit.com/r/robotics/comments/abc123/nvidia_groot/"
    assert first.body == "NVIDIA announced GR00T 2.0 for humanoid robots."
    assert first.source_type == "sns"
    assert first.source_name == "Reddit"
    assert first.author == "robotics_fan"
    assert first.language == "en"
    assert first.content_type == "post"
    assert first.published_at is None

    second = items[1]
    assert second.title == "Tesla Optimus update"
    assert second.author == "tesla_watcher"


def test_sns_source_reddit_empty_response(monkeypatch):
    """L14: Reddit search가 빈 결과를 반환하면 빈 리스트."""
    from src.sources.sns import SnsSource

    class MockResponse:
        status_code = 200

        def json(self):
            return {"data": {"children": []}}

    monkeypatch.setattr("httpx.get", lambda *args, **kwargs: MockResponse())

    source = SnsSource()
    items = source.fetch_reddit("robotics", "obscure_query_xyz")
    assert items == []


def test_sns_source_reddit_non_200(monkeypatch):
    """L14: Reddit가 200이 아닌 상태 코드를 반환하면 빈 리스트."""
    from src.sources.sns import SnsSource

    class MockResponse:
        status_code = 429  # rate-limited

        def json(self):
            return {}

    monkeypatch.setattr("httpx.get", lambda *args, **kwargs: MockResponse())

    source = SnsSource()
    items = source.fetch_reddit("robotics", "test")
    assert items == []
