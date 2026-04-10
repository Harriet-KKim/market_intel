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
