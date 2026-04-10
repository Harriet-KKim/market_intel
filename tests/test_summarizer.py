from src.gateway.base_adapter import LLMResponse


def test_summarizer_generates_snapshot_and_updates(tmp_path, sample_registry_dir):
    from src.refinery.summarizer import Summarizer
    from src.writer.vault import VaultManager
    from src.writer.weekly_writer import WeeklyWriter
    from src.writer.profile_writer import ProfileWriter
    from src.registry import Registry
    from src.gateway.gateway import LLMGateway
    from src.gateway.base_adapter import BaseAdapter

    vault = VaultManager(tmp_path / "vault")
    registry = Registry(sample_registry_dir)
    profile_writer = ProfileWriter(vault)
    weekly_writer = WeeklyWriter(vault)

    # Create initial company profile
    profile_writer.create_company("NVIDIA", ["엔비디아"])

    # Write a consolidated file
    consolidated_path = weekly_writer.write_consolidated(
        week="2026-W15",
        date_range="2026-04-06 ~ 2026-04-12",
        content="## NVIDIA\n- GR00T 2.0 launched for humanoid robots",
    )

    class MockAdapter(BaseAdapter):
        def call(self, prompt, system=None, **kwargs):
            if "주간 스냅샷" in prompt or "snapshot" in prompt.lower():
                return LLMResponse(
                    content='{"snapshot": "## 주요 하이라이트\\n- NVIDIA GR00T 2.0 발표", "company_updates": {"NVIDIA": "## 회사 개요\\nGPU 기업\\n\\n## 최근 동향\\n- GR00T 2.0 발표\\n\\n## 기술 스택\\n\\n## 파트너십 / 생태계\\n\\n## 전망 / 시사점\\n\\n---\\n\\n## 기타 노트"}, "topic_updates": {}}',
                    input_tokens=200, output_tokens=100,
                )
            return LLMResponse(content="default", input_tokens=0, output_tokens=0)
        def call_with_history(self, messages, system=None, **kwargs):
            return self.call(messages[-1]["content"])

    gateway = LLMGateway()
    gateway.register_adapter("claude-opus", MockAdapter())

    summarizer = Summarizer(
        gateway=gateway,
        model="claude-opus",
        vault=vault,
        registry=registry,
        profile_writer=profile_writer,
        weekly_writer=weekly_writer,
    )

    snapshot_path = summarizer.run(week="2026-W15", date_range="2026-04-06 ~ 2026-04-12")

    assert snapshot_path.exists()
    assert "주요 하이라이트" in snapshot_path.read_text(encoding="utf-8")
