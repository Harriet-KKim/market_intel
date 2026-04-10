from src.sources.base import CollectedItem
from src.gateway.base_adapter import LLMResponse


def make_test_item():
    return CollectedItem(
        title="NVIDIA GR00T 2.0",
        url="https://example.com/groot",
        body="NVIDIA launched GR00T 2.0 for humanoid robot control.",
        source_type="news",
        source_name="TechCrunch",
        author="John",
        published_at="2026-04-08T12:00:00Z",
        language="en",
        content_type="article",
    )


def test_pipeline_processes_item(tmp_path, sample_registry_dir):
    from src.collector.pipeline import CollectionPipeline
    from src.writer.vault import VaultManager
    from src.writer.raw_writer import RawWriter
    from src.registry import Registry
    from src.dedup import UrlDedup
    from src.gateway.gateway import LLMGateway
    from src.gateway.base_adapter import BaseAdapter

    # Mock gateway that returns tagging results as JSON
    class MockAdapter(BaseAdapter):
        def call(self, prompt: str, system: str | None = None, **kwargs) -> LLMResponse:
            return LLMResponse(
                content='{"companies": ["nvidia"], "keywords": ["humanoid-robot"]}',
                input_tokens=10,
                output_tokens=5,
            )
        def call_with_history(self, messages, system=None, **kwargs):
            return self.call(messages[-1]["content"])

    gateway = LLMGateway()
    gateway.register_adapter("gemini", MockAdapter())

    vault = VaultManager(tmp_path / "vault")
    registry = Registry(sample_registry_dir)
    dedup = UrlDedup(tmp_path / "dedup.db")
    raw_writer = RawWriter(vault)

    pipeline = CollectionPipeline(
        gateway=gateway,
        tagging_model="gemini",
        registry=registry,
        dedup=dedup,
        raw_writer=raw_writer,
    )

    item = make_test_item()
    result = pipeline.process_item(item)

    assert result is not None
    assert result.exists()
    content = result.read_text(encoding="utf-8")
    assert "[[NVIDIA]]" in content
    assert "humanoid-robot" in content

    # 로컬 패치 P1: frontmatter뿐 아니라 본문 내부에도 [[NVIDIA]] 링크가 주입돼야
    # Obsidian Backlinks가 "어떤 raw 노트가 NVIDIA를 언급했는지" 역인덱스를 구성할 수 있다.
    from src.writer.frontmatter import parse_document
    _, body = parse_document(content)
    assert "[[NVIDIA]]" in body, (
        "body 내부에 WikiLink가 주입되지 않았습니다. inject_wikilinks 호출 누락 가능성."
    )


def test_pipeline_dedup_skips_seen(tmp_path, sample_registry_dir):
    from src.collector.pipeline import CollectionPipeline
    from src.writer.vault import VaultManager
    from src.writer.raw_writer import RawWriter
    from src.registry import Registry
    from src.dedup import UrlDedup
    from src.gateway.gateway import LLMGateway
    from src.gateway.base_adapter import BaseAdapter

    class MockAdapter(BaseAdapter):
        def call(self, prompt, system=None, **kwargs):
            return LLMResponse(content='{"companies": [], "keywords": []}', input_tokens=0, output_tokens=0)
        def call_with_history(self, messages, system=None, **kwargs):
            return self.call("")

    gateway = LLMGateway()
    gateway.register_adapter("gemini", MockAdapter())

    vault = VaultManager(tmp_path / "vault")
    registry = Registry(sample_registry_dir)
    dedup = UrlDedup(tmp_path / "dedup.db")
    raw_writer = RawWriter(vault)

    pipeline = CollectionPipeline(
        gateway=gateway, tagging_model="gemini",
        registry=registry, dedup=dedup, raw_writer=raw_writer,
    )

    item = make_test_item()
    pipeline.process_item(item)
    result2 = pipeline.process_item(item)  # Same URL

    assert result2 is None  # Skipped
