def test_sns_source_placeholder():
    from src.sources.sns import SnsSource

    source = SnsSource()
    # SNS requires API keys; test the interface exists
    items = source.fetch("nvidia", ["world-model"])

    assert isinstance(items, list)
