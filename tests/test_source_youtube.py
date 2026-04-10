def test_youtube_source_fetches_transcript(monkeypatch):
    from src.sources.youtube import YoutubeSource

    mock_transcript = "Hello everyone. Today we're announcing GR00T 2.0."

    monkeypatch.setattr(
        "src.sources.youtube.extract_transcript",
        lambda video_url: mock_transcript,
    )

    source = YoutubeSource()
    items = source.fetch_from_url("https://youtube.com/watch?v=abc123", channel="NVIDIA")

    assert len(items) == 1
    assert "GR00T 2.0" in items[0].body
    assert items[0].source_type == "video"
    assert items[0].channel == "NVIDIA"


def test_parse_vtt_extracts_cue_text():
    """로컬 패치 P2: VTT 파싱 로직을 직접 검증.
    기존 플랜은 extract_transcript 전체를 monkeypatch로 대체해서 VTT 파싱이
    실제로 동작하는지 검증하지 못했고, 구현도 --print 플래그로 메타데이터만
    출력하는 버그가 있었습니다. 새 _parse_vtt 헬퍼는 단위 테스트로 고정합니다."""
    from src.sources.youtube import _parse_vtt

    vtt = """WEBVTT
Kind: captions
Language: en

00:00:00.000 --> 00:00:03.000
Hello everyone.

00:00:03.000 --> 00:00:06.000
Today we're announcing <c>GR00T 2.0</c>.

00:00:06.000 --> 00:00:09.000
It's a humanoid platform.
"""
    result = _parse_vtt(vtt)
    assert "Hello everyone." in result
    assert "GR00T 2.0" in result
    assert "humanoid platform" in result
    # 헤더/메타데이터/타이밍/HTML 태그는 모두 제거되어야 한다
    assert "WEBVTT" not in result
    assert "Kind:" not in result
    assert "Language:" not in result
    assert "-->" not in result
    assert "<c>" not in result
    assert "</c>" not in result


def test_youtube_source_returns_empty_on_extract_error(monkeypatch):
    """L13: extract_transcript가 예외를 던져도 빈 리스트 반환, 크래시 안 함."""
    import subprocess
    from src.sources.youtube import YoutubeSource

    def raise_error(video_url):
        raise subprocess.TimeoutExpired(cmd="yt-dlp", timeout=120)

    monkeypatch.setattr("src.sources.youtube.extract_transcript", raise_error)
    source = YoutubeSource()
    items = source.fetch_from_url("https://youtube.com/watch?v=abc123")
    assert items == []


# ---------- L6: channel discovery via Atom feed ----------


def test_normalize_channel_id_to_feed_url():
    """UC로 시작하는 24자 channel_id는 Atom feed URL로 조립된다."""
    from src.sources.youtube import _normalize_channel_to_feed_url

    result = _normalize_channel_to_feed_url("UCHuFmzwsYryg1kUV0IMzEag")
    assert result == (
        "https://www.youtube.com/feeds/videos.xml?"
        "channel_id=UCHuFmzwsYryg1kUV0IMzEag"
    )


def test_normalize_full_feed_url_passthrough():
    """완전한 feeds.xml URL은 변형 없이 그대로 반환된다."""
    from src.sources.youtube import _normalize_channel_to_feed_url

    url = (
        "https://www.youtube.com/feeds/videos.xml?"
        "channel_id=UCHuFmzwsYryg1kUV0IMzEag"
    )
    assert _normalize_channel_to_feed_url(url) == url


def test_normalize_unsupported_handle_returns_none():
    """@handle 과 plain username 은 MVP 범위 밖이라 None을 반환한다."""
    from src.sources.youtube import _normalize_channel_to_feed_url

    assert _normalize_channel_to_feed_url("@NvidiaAI") is None
    assert _normalize_channel_to_feed_url("NvidiaAI") is None
    # UC로 시작하지만 길이가 틀린 경우도 None
    assert _normalize_channel_to_feed_url("UCtooShort") is None


def test_fetch_channel_videos_from_channel_id(monkeypatch):
    """UC channel_id → feedparser로 Atom 피드 파싱 → CollectedItem 리스트."""
    import feedparser
    from src.sources.youtube import YoutubeSource

    fake_feed = feedparser.FeedParserDict(
        {
            "feed": feedparser.FeedParserDict({"title": "NVIDIA Developer"}),
            "entries": [
                feedparser.FeedParserDict(
                    {
                        "title": "GR00T 2.0 Launch Demo",
                        "link": "https://www.youtube.com/watch?v=abc123",
                        "summary": "NVIDIA unveils GR00T 2.0 for humanoid robots.",
                        "author": "NVIDIA Developer",
                        "published": "2026-04-08T12:00:00+00:00",
                    }
                ),
                feedparser.FeedParserDict(
                    {
                        "title": "Isaac Sim Tutorial",
                        "link": "https://www.youtube.com/watch?v=def456",
                        "summary": "Walkthrough of the Isaac Sim workflow.",
                        "author": "NVIDIA Developer",
                        "published": "2026-04-07T09:00:00+00:00",
                    }
                ),
            ],
        }
    )

    captured_url: dict[str, str] = {}

    def fake_parse(url):
        captured_url["url"] = url
        return fake_feed

    monkeypatch.setattr("src.sources.youtube.feedparser.parse", fake_parse)

    source = YoutubeSource()
    items = source.fetch_channel_videos("UCHuFmzwsYryg1kUV0IMzEag")

    assert captured_url["url"] == (
        "https://www.youtube.com/feeds/videos.xml?"
        "channel_id=UCHuFmzwsYryg1kUV0IMzEag"
    )
    assert len(items) == 2

    first = items[0]
    assert first.title == "GR00T 2.0 Launch Demo"
    assert first.url == "https://www.youtube.com/watch?v=abc123"
    assert first.body == "NVIDIA unveils GR00T 2.0 for humanoid robots."
    assert first.source_type == "video"
    assert first.source_name == "YouTube"
    assert first.channel == "NVIDIA Developer"
    assert first.content_type == "video"
    assert first.author == "NVIDIA Developer"
    assert first.published_at == "2026-04-08T12:00:00+00:00"

    assert items[1].url == "https://www.youtube.com/watch?v=def456"


def test_fetch_channel_videos_accepts_full_feed_url(monkeypatch):
    """full feeds.xml URL은 prefix 중복 없이 그대로 feedparser에 전달된다."""
    import feedparser
    from src.sources.youtube import YoutubeSource

    empty_feed = feedparser.FeedParserDict(
        {
            "feed": feedparser.FeedParserDict({"title": ""}),
            "entries": [],
        }
    )
    captured: dict[str, str] = {}

    def fake_parse(url):
        captured["url"] = url
        return empty_feed

    monkeypatch.setattr("src.sources.youtube.feedparser.parse", fake_parse)

    full_url = (
        "https://www.youtube.com/feeds/videos.xml?"
        "channel_id=UCHuFmzwsYryg1kUV0IMzEag"
    )
    YoutubeSource().fetch_channel_videos(full_url)
    assert captured["url"] == full_url


def test_fetch_channel_videos_unsupported_handle_returns_empty(monkeypatch, caplog):
    """@handle은 feedparser 호출 없이 즉시 빈 리스트 + 경고 로그."""
    import logging
    from src.sources.youtube import YoutubeSource

    def should_not_be_called(url):
        raise AssertionError(f"feedparser.parse should not be called, got {url}")

    monkeypatch.setattr(
        "src.sources.youtube.feedparser.parse", should_not_be_called
    )

    with caplog.at_level(logging.WARNING, logger="src.sources.youtube"):
        items = YoutubeSource().fetch_channel_videos("@NvidiaAI")

    assert items == []
    matching = [
        rec
        for rec in caplog.records
        if rec.name == "src.sources.youtube" and "not supported" in rec.message
    ]
    assert len(matching) == 1
    assert matching[0].levelname == "WARNING"


def test_fetch_channel_videos_returns_empty_on_parse_error(monkeypatch):
    """L13 parity: feedparser가 예외를 던지면 빈 리스트 반환 (crash 없음)."""
    from src.sources.youtube import YoutubeSource

    def raise_error(url):
        raise OSError("network unreachable")

    monkeypatch.setattr("src.sources.youtube.feedparser.parse", raise_error)

    items = YoutubeSource().fetch_channel_videos("UCHuFmzwsYryg1kUV0IMzEag")
    assert items == []
