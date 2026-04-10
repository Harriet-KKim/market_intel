from src.gateway.base_adapter import LLMResponse


def test_reviewer_adds_comment(tmp_path):
    from src.refinery.reviewer import Reviewer
    from src.writer.vault import VaultManager
    from src.writer.weekly_writer import WeeklyWriter
    from src.gateway.gateway import LLMGateway
    from src.gateway.session import Checkpoint
    from src.gateway.base_adapter import BaseAdapter

    vault = VaultManager(tmp_path / "vault")
    weekly_writer = WeeklyWriter(vault)

    # Write a snapshot
    weekly_writer.write_snapshot(
        week="2026-W15",
        date_range="2026-04-06 ~ 2026-04-12",
        content="## 주요 하이라이트\n- NVIDIA GR00T 2.0 발표",
    )

    class MockAdapter(BaseAdapter):
        def call(self, prompt, system=None, **kwargs):
            return LLMResponse(content="review", input_tokens=0, output_tokens=0)
        def call_with_history(self, messages, system=None, **kwargs):
            return LLMResponse(
                content="검토 완료. 누락 사항 없음. 신뢰도 판정 적절.",
                input_tokens=50, output_tokens=30,
            )

    gateway = LLMGateway()
    gateway.register_adapter("gpt5-pro", MockAdapter())

    # Create a checkpoint from a mock session
    checkpoint = Checkpoint(
        history=[
            {"role": "user", "content": "consolidation prompt"},
            {"role": "assistant", "content": "consolidated report"},
        ],
        system="You are a reviewer.",
    )

    reviewer = Reviewer(
        gateway=gateway,
        model="gpt5-pro",
        vault=vault,
        weekly_writer=weekly_writer,
    )

    reviewer.run(week="2026-W15", checkpoint=checkpoint)

    content = (vault.weekly_dir / "2026-W15.md").read_text(encoding="utf-8")
    assert "검토 완료" in content
    assert "GPT5 Pro 검토" in content
