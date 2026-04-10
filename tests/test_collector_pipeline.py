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


def test_pipeline_does_not_mark_seen_on_write_failure(tmp_path, sample_registry_dir):
    """L7: raw_writer.write가 예외를 던지면 URL이 seen으로 마킹되지 않아야 한다.

    원래 코드는 is_seen 체크 직후 mark_seen을 호출했기 때문에, write 중 크래시가
    나면 URL은 dedup DB에만 남고 파일은 없는 영구 누락 상태가 발생했습니다.
    """
    import pytest
    from src.collector.pipeline import CollectionPipeline
    from src.writer.vault import VaultManager
    from src.registry import Registry
    from src.dedup import UrlDedup
    from src.gateway.gateway import LLMGateway
    from src.gateway.base_adapter import BaseAdapter

    class MockAdapter(BaseAdapter):
        def call(self, prompt, system=None, **kwargs):
            return LLMResponse(content='{"companies": [], "keywords": []}', input_tokens=0, output_tokens=0)
        def call_with_history(self, messages, system=None, **kwargs):
            return self.call("")

    class FailingRawWriter:
        def write(self, article, date):
            raise OSError("disk full")

    gateway = LLMGateway()
    gateway.register_adapter("gemini", MockAdapter())

    VaultManager(tmp_path / "vault")
    registry = Registry(sample_registry_dir)
    dedup = UrlDedup(tmp_path / "dedup.db")

    pipeline = CollectionPipeline(
        gateway=gateway, tagging_model="gemini",
        registry=registry, dedup=dedup, raw_writer=FailingRawWriter(),
    )

    item = make_test_item()

    with pytest.raises(OSError):
        pipeline.process_item(item)

    # URL은 seen으로 마킹되지 않아야 함 → 재시도 시 다시 처리 가능
    assert dedup.is_seen(item.url) is False


def test_pipeline_fallback_uses_truncated_body(tmp_path, sample_registry_dir):
    """L17: JSON 파싱 실패 fallback도 LLM과 동일한 2000자 truncation 사용.

    원래 코드는 fallback에서 전체 body를 registry.match_*에 넘겨 LLM 경로와
    태깅 결과가 달라질 수 있었습니다.
    """
    from src.collector.pipeline import CollectionPipeline
    from src.writer.vault import VaultManager
    from src.writer.raw_writer import RawWriter
    from src.registry import Registry
    from src.dedup import UrlDedup
    from src.gateway.gateway import LLMGateway
    from src.gateway.base_adapter import BaseAdapter

    class BrokenJsonAdapter(BaseAdapter):
        """Returns invalid JSON to force the fallback path."""
        def call(self, prompt, system=None, **kwargs):
            return LLMResponse(content="not valid json at all", input_tokens=0, output_tokens=0)
        def call_with_history(self, messages, system=None, **kwargs):
            return self.call("")

    gateway = LLMGateway()
    gateway.register_adapter("gemini", BrokenJsonAdapter())

    vault = VaultManager(tmp_path / "vault")
    registry = Registry(sample_registry_dir)
    dedup = UrlDedup(tmp_path / "dedup.db")
    raw_writer = RawWriter(vault)

    pipeline = CollectionPipeline(
        gateway=gateway, tagging_model="gemini",
        registry=registry, dedup=dedup, raw_writer=raw_writer,
    )

    # body에서 처음 2000자는 어떤 회사/키워드도 언급하지 않고,
    # 2000자 뒤에만 "NVIDIA"와 "humanoid"가 등장한다.
    padding = "x " * 1100  # 2200자 넘음, 어떤 alias와도 매칭 안 됨
    item = CollectedItem(
        title="Test article",
        url="https://example.com/truncation-test",
        body=padding + "NVIDIA humanoid breakthrough",
        source_type="news",
        source_name="TechCrunch",
        author="tester",
        published_at="2026-04-08T12:00:00Z",
        language="en",
        content_type="article",
    )

    result = pipeline.process_item(item)
    assert result is not None
    content = result.read_text(encoding="utf-8")

    # 2000자 뒤의 "NVIDIA"와 "humanoid"는 fallback이 truncated body를 쓰므로
    # 태깅되지 않아야 한다 (frontmatter의 companies/tags에 없어야 함).
    from src.writer.frontmatter import parse_document
    metadata, _ = parse_document(content)
    assert metadata.get("companies", []) == []
    assert metadata.get("tags", []) == []


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
