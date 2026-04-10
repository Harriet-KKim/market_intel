from pathlib import Path
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from src.config import (
    AppConfig, CollectionConfig, SourcesConfig,
    RefineryConfig, ApiKeysConfig, BudgetConfig,
)
from src.config import SourcesConfig
from src.scheduler.scheduler import IntelScheduler


def _make_config(**overrides):
    sources = overrides.pop("sources", SourcesConfig(rss=True, web=False, sns=False, youtube=False))
    timezone = overrides.pop("timezone", "Asia/Seoul")
    return AppConfig(
        vault_path=Path("/tmp/vault"),
        collection=CollectionConfig(interval_hours=6, sources=sources, timezone=timezone),
        refinery=RefineryConfig(schedule_day="monday", schedule_hour=9),
        api_keys=ApiKeysConfig(gemini="", openai="", anthropic=""),
        budget=BudgetConfig(enabled=False, daily_limit_usd=10.0),
        dedup_db_path=Path("/tmp/vault/.dedup.db"),
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


def test_scheduler_calls_sns_when_enabled():
    """L16: config.sources.sns=True일 때 SnsSource.fetch_reddit이 호출된다."""
    config = _make_config(sources=SourcesConfig(rss=False, web=False, sns=True, youtube=False))

    registry = MagicMock()
    company = MagicMock()
    company.name = "NVIDIA"
    company.sources = {}
    registry.companies = [company]

    pipeline = MagicMock()
    pipeline.process_item.return_value = Path("/tmp/out.md")

    scheduler = _make_scheduler(config=config, registry=registry, pipeline=pipeline)
    mock_sns = MagicMock()
    item = MagicMock()
    item.url = "https://reddit.com/r/robotics/test"
    mock_sns.fetch_reddit.return_value = [item]
    scheduler._sns = mock_sns

    scheduler.run_once()

    mock_sns.fetch_reddit.assert_called_once_with("robotics", "NVIDIA")
    pipeline.process_item.assert_called_once_with(item)


def test_scheduler_uses_configured_timezone():
    """L5: BlockingScheduler가 config.collection.timezone 값을 ZoneInfo로 주입받는다."""
    config = _make_config(timezone="Asia/Seoul")
    scheduler = _make_scheduler(config=config)
    assert scheduler._scheduler.timezone == ZoneInfo("Asia/Seoul")


def test_scheduler_honors_custom_timezone():
    """L5: 다른 timezone 값으로도 동작한다."""
    config = _make_config(timezone="America/New_York")
    scheduler = _make_scheduler(config=config)
    assert scheduler._scheduler.timezone == ZoneInfo("America/New_York")


def test_scheduler_skips_sns_when_disabled():
    """L16: config.sources.sns=False일 때 SnsSource.fetch_reddit이 호출되지 않는다."""
    config = _make_config(sources=SourcesConfig(rss=False, web=False, sns=False, youtube=False))

    registry = MagicMock()
    company = MagicMock()
    company.name = "NVIDIA"
    company.sources = {}
    registry.companies = [company]

    pipeline = MagicMock()

    scheduler = _make_scheduler(config=config, registry=registry, pipeline=pipeline)
    mock_sns = MagicMock()
    scheduler._sns = mock_sns

    scheduler.run_once()

    mock_sns.fetch_reddit.assert_not_called()


def test_scheduler_discovers_youtube_videos():
    """L6: sources.youtube=True일 때 fetch_channel_videos 호출 결과가 pipeline.process_item 으로 흐른다."""
    config = _make_config(
        sources=SourcesConfig(rss=False, web=False, sns=False, youtube=True)
    )

    registry = MagicMock()
    company = MagicMock()
    company.name = "NVIDIA"
    company.sources = {"youtube": ["UCHuFmzwsYryg1kUV0IMzEag"]}
    registry.companies = [company]

    pipeline = MagicMock()
    pipeline.process_item.return_value = Path("/tmp/out.md")

    scheduler = _make_scheduler(config=config, registry=registry, pipeline=pipeline)

    mock_youtube = MagicMock()
    item1 = MagicMock()
    item1.url = "https://www.youtube.com/watch?v=abc123"
    item2 = MagicMock()
    item2.url = "https://www.youtube.com/watch?v=def456"
    mock_youtube.fetch_channel_videos.return_value = [item1, item2]
    scheduler._youtube = mock_youtube

    scheduler.run_once()

    mock_youtube.fetch_channel_videos.assert_called_once_with(
        "UCHuFmzwsYryg1kUV0IMzEag"
    )
    assert pipeline.process_item.call_count == 2
    pipeline.process_item.assert_any_call(item1)
    pipeline.process_item.assert_any_call(item2)


def test_scheduler_skips_youtube_discovery_when_disabled():
    """sources.youtube=False일 때 fetch_channel_videos 는 호출되지 않는다."""
    config = _make_config(
        sources=SourcesConfig(rss=False, web=False, sns=False, youtube=False)
    )

    registry = MagicMock()
    company = MagicMock()
    company.name = "NVIDIA"
    company.sources = {"youtube": ["UCHuFmzwsYryg1kUV0IMzEag"]}
    registry.companies = [company]

    pipeline = MagicMock()
    scheduler = _make_scheduler(config=config, registry=registry, pipeline=pipeline)
    mock_youtube = MagicMock()
    scheduler._youtube = mock_youtube

    scheduler.run_once()

    mock_youtube.fetch_channel_videos.assert_not_called()
    pipeline.process_item.assert_not_called()
