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
