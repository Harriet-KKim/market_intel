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


def _make_scheduler(config=None, registry=None, pipeline=None, refinement_pipeline=None):
    config = config or _make_config()
    registry = registry or MagicMock()
    pipeline = pipeline or MagicMock()
    scheduler = IntelScheduler(
        config=config,
        registry=registry,
        pipeline=pipeline,
        refinement_pipeline=refinement_pipeline,
    )
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


# ---------- L20: weekly refinement cron ----------

import logging
from datetime import date

from src.scheduler.scheduler import _day_to_cron, _compute_previous_week


def test_day_to_cron_accepts_full_weekday_name():
    assert _day_to_cron("monday") == "mon"
    assert _day_to_cron("WEDNESDAY") == "wed"
    assert _day_to_cron("Sunday") == "sun"


def test_day_to_cron_accepts_short_form():
    assert _day_to_cron("mon") == "mon"
    assert _day_to_cron("FRI") == "fri"


def test_day_to_cron_rejects_unknown_value():
    import pytest

    with pytest.raises(ValueError, match="Unknown weekday"):
        _day_to_cron("funday")


def test_compute_previous_week_from_monday():
    """월요일 실행 → 직전 주(월~일)."""
    week_id, date_range = _compute_previous_week(date(2026, 4, 13))
    assert week_id == "2026-W15"
    assert date_range == "2026-04-06 ~ 2026-04-12"


def test_compute_previous_week_from_wednesday():
    """수요일 실행 → 같은 '직전 주(월~일)' 결과."""
    week_id, date_range = _compute_previous_week(date(2026, 4, 15))
    assert week_id == "2026-W15"
    assert date_range == "2026-04-06 ~ 2026-04-12"


def test_scheduler_registers_refinement_cron_when_enabled():
    """L20: enabled=True + refinement_pipeline 주입 시 cron 잡 등록."""
    from apscheduler.triggers.cron import CronTrigger

    config = _make_config()
    config.refinery.enabled = True
    config.refinery.schedule_day = "monday"
    config.refinery.schedule_hour = 9
    config.refinery.schedule_minute = 0

    refinement_pipeline = MagicMock()
    scheduler = _make_scheduler(config=config, refinement_pipeline=refinement_pipeline)
    scheduler._register_jobs()

    jobs = {job.id: job for job in scheduler._scheduler.get_jobs()}
    assert "collection_cycle" in jobs
    assert "refinement_cycle" in jobs

    cron = jobs["refinement_cycle"].trigger
    assert isinstance(cron, CronTrigger)
    fields = {f.name: str(f) for f in cron.fields}
    assert fields["day_of_week"] == "mon"
    assert fields["hour"] == "9"
    assert fields["minute"] == "0"


def test_scheduler_skips_refinement_cron_when_disabled():
    """L20: enabled=False이면 cron 잡 미등록."""
    config = _make_config()
    config.refinery.enabled = False

    refinement_pipeline = MagicMock()
    scheduler = _make_scheduler(config=config, refinement_pipeline=refinement_pipeline)
    scheduler._register_jobs()

    jobs = {job.id for job in scheduler._scheduler.get_jobs()}
    assert "refinement_cycle" not in jobs
    assert "collection_cycle" in jobs


def test_scheduler_skips_refinement_cron_when_pipeline_missing(caplog):
    """L20: refinement_pipeline=None이면 enabled여도 등록하지 않고 warning 로그."""
    config = _make_config()
    config.refinery.enabled = True

    scheduler = _make_scheduler(config=config, refinement_pipeline=None)

    with caplog.at_level(logging.WARNING, logger="src.scheduler.scheduler"):
        scheduler._register_jobs()

    jobs = {job.id for job in scheduler._scheduler.get_jobs()}
    assert "refinement_cycle" not in jobs
    assert any("refinement_pipeline not provided" in rec.message for rec in caplog.records)


def test_run_refinement_cycle_calls_pipeline_with_previous_week(tmp_path):
    """L20: _run_refinement_cycle이 직전 주 week_id/date_range로 pipeline.run 호출."""
    config = _make_config()
    config.vault_path = tmp_path
    (tmp_path / "raw" / "2026-04-06").mkdir(parents=True)

    refinement_pipeline = MagicMock()
    scheduler = _make_scheduler(config=config, refinement_pipeline=refinement_pipeline)

    scheduler._run_refinement_cycle(today=date(2026, 4, 13))

    refinement_pipeline.run.assert_called_once_with(
        week="2026-W15", date_range="2026-04-06 ~ 2026-04-12"
    )


def test_run_refinement_cycle_skips_when_no_raw_data(tmp_path, caplog):
    """L20: 대상 주의 raw 폴더가 하나도 없으면 pipeline 미호출 + warning."""
    config = _make_config()
    config.vault_path = tmp_path
    (tmp_path / "raw").mkdir()

    refinement_pipeline = MagicMock()
    scheduler = _make_scheduler(config=config, refinement_pipeline=refinement_pipeline)

    with caplog.at_level(logging.WARNING, logger="src.scheduler.scheduler"):
        scheduler._run_refinement_cycle(today=date(2026, 4, 13))

    refinement_pipeline.run.assert_not_called()
    assert any("no raw data" in rec.message for rec in caplog.records)


def test_run_refinement_cycle_isolates_pipeline_exception(tmp_path, caplog):
    """L20: pipeline.run이 예외를 던져도 스케줄러가 크래시하지 않고 logger.exception 기록."""
    config = _make_config()
    config.vault_path = tmp_path
    (tmp_path / "raw" / "2026-04-06").mkdir(parents=True)

    refinement_pipeline = MagicMock()
    refinement_pipeline.run.side_effect = RuntimeError("step 2 LLM quota exceeded")
    scheduler = _make_scheduler(config=config, refinement_pipeline=refinement_pipeline)

    with caplog.at_level(logging.ERROR, logger="src.scheduler.scheduler"):
        scheduler._run_refinement_cycle(today=date(2026, 4, 13))

    assert any("Refinement failed" in rec.message for rec in caplog.records)
