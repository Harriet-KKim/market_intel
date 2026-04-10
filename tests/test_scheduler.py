from pathlib import Path
from unittest.mock import MagicMock

from src.config import (
    AppConfig, CollectionConfig, SourcesConfig,
    RefineryConfig, ApiKeysConfig, BudgetConfig,
)
from src.scheduler.scheduler import IntelScheduler


def _make_config(**overrides):
    sources = overrides.pop("sources", SourcesConfig(rss=True, web=False, sns=False, youtube=False))
    return AppConfig(
        vault_path=Path("/tmp/vault"),
        collection=CollectionConfig(interval_hours=6, sources=sources),
        refinery=RefineryConfig(schedule_day="monday", schedule_hour=9),
        api_keys=ApiKeysConfig(gemini="", openai="", anthropic=""),
        budget=BudgetConfig(enabled=False, daily_limit_usd=10.0),
    )


def _make_scheduler(config=None, registry=None, pipeline=None):
    config = config or _make_config()
    registry = registry or MagicMock()
    pipeline = pipeline or MagicMock()
    scheduler = IntelScheduler(config=config, registry=registry, pipeline=pipeline)
    return scheduler


def test_scheduler_isolates_per_item_errors():
    """L15: process_item 하나가 실패해도 나머지 아이템은 처리된다."""
    config = _make_config()

    registry = MagicMock()
    company = MagicMock()
    company.sources = {"rss": ["https://example.com/feed"]}
    registry.companies = [company]

    pipeline = MagicMock()

    item1 = MagicMock()
    item1.url = "https://example.com/1"
    item2 = MagicMock()
    item2.url = "https://example.com/2"

    # pipeline.process_item raises on first call, succeeds on second
    pipeline.process_item.side_effect = [RuntimeError("tagging failed"), Path("/tmp/out.md")]

    scheduler = _make_scheduler(config=config, registry=registry, pipeline=pipeline)
    scheduler._rss = MagicMock()
    scheduler._rss.fetch_from_url.return_value = [item1, item2]

    # Should not raise
    scheduler.run_once()

    # Both items should have been attempted
    assert pipeline.process_item.call_count == 2
