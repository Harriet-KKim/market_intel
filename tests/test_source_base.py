import pytest


def test_source_module_interface():
    from src.sources.base import BaseSource, CollectedItem

    class TestSource(BaseSource):
        source_type = "test"

        def fetch(self, company_id: str, keywords: list[str]) -> list[CollectedItem]:
            return [
                CollectedItem(
                    title="Test Article",
                    url="https://example.com/1",
                    body="Body text",
                    source_type=self.source_type,
                    source_name="TestSource",
                    author="Author",
                    published_at="2026-04-08T12:00:00Z",
                    language="en",
                    content_type="article",
                )
            ]

    source = TestSource()
    items = source.fetch("nvidia", ["world-model"])

    assert len(items) == 1
    assert items[0].title == "Test Article"
    assert items[0].source_type == "test"


def test_cannot_instantiate_base_source():
    from src.sources.base import BaseSource

    with pytest.raises(TypeError):
        BaseSource()
