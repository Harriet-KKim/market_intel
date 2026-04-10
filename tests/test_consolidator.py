from src.gateway.base_adapter import LLMResponse


def test_consolidator_generates_report(tmp_path, sample_registry_dir):
    from src.refinery.consolidator import Consolidator
    from src.writer.vault import VaultManager
    from src.writer.raw_writer import RawWriter
    from src.writer.weekly_writer import WeeklyWriter
    from src.registry import Registry
    from src.gateway.gateway import LLMGateway
    from src.gateway.base_adapter import BaseAdapter

    # Write some raw data
    vault = VaultManager(tmp_path / "vault")
    raw_writer = RawWriter(vault)
    raw_writer.write({
        "id": "article-001",
        "title": "NVIDIA GR00T 2.0",
        "source": {"type": "news", "name": "TechCrunch", "url": "https://ex.com/1", "author": "J"},
        "collected_at": "2026-04-08T14:00:00Z",
        "published_at": "2026-04-08T12:00:00Z",
        "language": "en",
        "companies": ["[[NVIDIA]]"],
        "tags": ["humanoid-robot"],
        "reliability": 0.7,
        "content_type": "article",
        "body": "NVIDIA launched GR00T 2.0.",
    }, date="2026-04-08")

    # Mock GPT5 Pro
    class MockAdapter(BaseAdapter):
        def call(self, prompt, system=None, **kwargs):
            return LLMResponse(content="## Consolidated Report\n- NVIDIA: GR00T 2.0 launched", input_tokens=100, output_tokens=50)
        def call_with_history(self, messages, system=None, **kwargs):
            return LLMResponse(content="## Consolidated Report\n- NVIDIA: GR00T 2.0 launched", input_tokens=100, output_tokens=50)

    gateway = LLMGateway()
    gateway.register_adapter("gpt5-pro", MockAdapter())

    registry = Registry(sample_registry_dir)
    weekly_writer = WeeklyWriter(vault)

    consolidator = Consolidator(
        gateway=gateway,
        model="gpt5-pro",
        vault=vault,
        registry=registry,
        weekly_writer=weekly_writer,
    )

    session, path = consolidator.run(week="2026-W15", date_range="2026-04-06 ~ 2026-04-12")

    assert path.exists()
    assert "GR00T 2.0" in path.read_text(encoding="utf-8")
    assert session is not None  # Session returned for checkpoint


def test_consolidator_filters_raw_by_date_range(tmp_path, sample_registry_dir):
    """로컬 패치 I5: date_range 밖의 raw는 LLM 프롬프트에 포함되면 안 된다.

    원본 플랜의 `_read_raw_data`는 인자를 무시하고 raw/ 전체를 스캔해 이전 주 데이터가
    이번 주 consolidation에 섞여 들어갔습니다. 이 테스트는 프롬프트를 캡처하는 어댑터로
    "주간 경계 밖 본문이 프롬프트에 나타나지 않음"을 검증합니다.
    """
    from src.refinery.consolidator import Consolidator
    from src.writer.vault import VaultManager
    from src.writer.raw_writer import RawWriter
    from src.writer.weekly_writer import WeeklyWriter
    from src.registry import Registry
    from src.gateway.gateway import LLMGateway
    from src.gateway.base_adapter import BaseAdapter

    vault = VaultManager(tmp_path / "vault")
    raw_writer = RawWriter(vault)

    # In-range article (2026-04-08 — 2026-W15의 한가운데)
    raw_writer.write({
        "id": "article-in",
        "title": "In-range headline",
        "source": {"type": "news", "name": "TechCrunch", "url": "https://ex.com/in", "author": "A"},
        "collected_at": "2026-04-08T14:00:00Z",
        "published_at": "2026-04-08T12:00:00Z",
        "language": "en",
        "companies": ["[[NVIDIA]]"],
        "tags": ["humanoid-robot"],
        "reliability": 0.7,
        "content_type": "article",
        "body": "INRANGE_TOKEN body text",
    }, date="2026-04-08")

    # Out-of-range article (2026-03-20 — 3주 이전)
    raw_writer.write({
        "id": "article-out",
        "title": "Out-of-range headline",
        "source": {"type": "news", "name": "TechCrunch", "url": "https://ex.com/out", "author": "A"},
        "collected_at": "2026-03-20T14:00:00Z",
        "published_at": "2026-03-20T12:00:00Z",
        "language": "en",
        "companies": ["[[NVIDIA]]"],
        "tags": ["humanoid-robot"],
        "reliability": 0.7,
        "content_type": "article",
        "body": "OUTRANGE_TOKEN body text",
    }, date="2026-03-20")

    captured_prompts: list[str] = []

    class CapturingAdapter(BaseAdapter):
        def call(self, prompt, system=None, **kwargs):
            captured_prompts.append(prompt)
            return LLMResponse(content="ok", input_tokens=0, output_tokens=0)
        def call_with_history(self, messages, system=None, **kwargs):
            captured_prompts.append(messages[-1]["content"])
            return LLMResponse(content="ok", input_tokens=0, output_tokens=0)

    gateway = LLMGateway()
    gateway.register_adapter("gpt5-pro", CapturingAdapter())

    registry = Registry(sample_registry_dir)
    weekly_writer = WeeklyWriter(vault)

    consolidator = Consolidator(
        gateway=gateway,
        model="gpt5-pro",
        vault=vault,
        registry=registry,
        weekly_writer=weekly_writer,
    )

    consolidator.run(week="2026-W15", date_range="2026-04-06 ~ 2026-04-12")

    assert captured_prompts, "Consolidator did not call the gateway"
    combined = "\n".join(captured_prompts)
    assert "INRANGE_TOKEN" in combined, "범위 내 본문이 프롬프트에 포함되어야 합니다"
    assert "OUTRANGE_TOKEN" not in combined, (
        "범위 밖 본문이 프롬프트에 새어들어갔습니다. _read_raw_data의 date_range 필터 미적용."
    )
