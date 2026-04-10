from src.gateway.base_adapter import BaseAdapter, LLMResponse


def test_full_refinement_pipeline(tmp_path, sample_registry_dir):
    from src.refinery.pipeline import RefinementPipeline
    from src.writer.vault import VaultManager
    from src.writer.raw_writer import RawWriter
    from src.writer.profile_writer import ProfileWriter
    from src.registry import Registry
    from src.gateway.gateway import LLMGateway

    vault = VaultManager(tmp_path / "vault")
    registry = Registry(sample_registry_dir)

    # Write raw data
    RawWriter(vault).write({
        "id": "article-001",
        "title": "Test",
        "source": {"type": "news", "name": "Test", "url": "https://ex.com", "author": "A"},
        "collected_at": "2026-04-08T00:00:00Z",
        "published_at": "2026-04-08T00:00:00Z",
        "language": "en",
        "companies": ["[[NVIDIA]]"],
        "tags": ["world-model"],
        "reliability": 0.7,
        "content_type": "article",
        "body": "Test body.",
    }, date="2026-04-08")

    # Create company profile
    ProfileWriter(vault).create_company("NVIDIA", ["엔비디아"])

    class MockGPT(BaseAdapter):
        def call(self, prompt, system=None, **kwargs):
            return LLMResponse(content="consolidated", input_tokens=10, output_tokens=5)
        def call_with_history(self, messages, system=None, **kwargs):
            last = messages[-1]["content"]
            if "consolidated" in str(messages[0].get("content", "")):
                return LLMResponse(content="review OK", input_tokens=10, output_tokens=5)
            return LLMResponse(content="## Consolidated\n- Test data", input_tokens=10, output_tokens=5)

    class MockClaude(BaseAdapter):
        def call(self, prompt, system=None, **kwargs):
            return LLMResponse(
                content='{"snapshot": "## 주요 하이라이트\\n- Test", "company_updates": {}, "topic_updates": {}}',
                input_tokens=20, output_tokens=10,
            )
        def call_with_history(self, messages, system=None, **kwargs):
            return self.call("")

    gateway = LLMGateway()
    gateway.register_adapter("gpt5-pro", MockGPT())
    gateway.register_adapter("claude-opus", MockClaude())

    pipeline = RefinementPipeline(
        gateway=gateway,
        consolidation_model="gpt5-pro",
        summarization_model="claude-opus",
        review_model="gpt5-pro",
        vault=vault,
        registry=registry,
    )

    pipeline.run(week="2026-W15", date_range="2026-04-06 ~ 2026-04-12")

    assert (vault.weekly_dir / "2026-W15-consolidated.md").exists()
    assert (vault.weekly_dir / "2026-W15.md").exists()
