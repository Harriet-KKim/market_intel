from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler

from src.config import AppConfig
from src.registry import Registry
from src.sources.rss import RssSource
from src.sources.sns import SnsSource
from src.sources.web import WebSource
from src.sources.youtube import YoutubeSource
from src.collector.pipeline import CollectionPipeline
from src.refinery.pipeline import RefinementPipeline

logger = logging.getLogger(__name__)


_WEEKDAY_NORMALIZATION = {
    "monday": "mon",
    "mon": "mon",
    "tuesday": "tue",
    "tue": "tue",
    "wednesday": "wed",
    "wed": "wed",
    "thursday": "thu",
    "thu": "thu",
    "friday": "fri",
    "fri": "fri",
    "saturday": "sat",
    "sat": "sat",
    "sunday": "sun",
    "sun": "sun",
}


def _day_to_cron(day: str) -> str:
    """Normalize a weekday string to APScheduler CronTrigger short form.

    Accepts either full names ("monday") or already-short ("mon"). Case
    insensitive. Raises ValueError for unknown strings so a typo in
    config.yaml surfaces at scheduler registration instead of silently
    running on the wrong day.
    """
    key = day.strip().lower()
    if key not in _WEEKDAY_NORMALIZATION:
        raise ValueError(f"Unknown weekday: {day!r}")
    return _WEEKDAY_NORMALIZATION[key]


def _compute_previous_week(today: date) -> tuple[str, str]:
    """Return (week_id, date_range) for the ISO week immediately preceding ``today``.

    Formula: walk back to the nearest past Sunday, then 6 days before that
    is the Monday of the target week. Works for any weekday of execution.

    Edge case — Sunday: ``today.weekday() == 6`` skips the in-progress week
    and targets the week before. Documented in the spec; intentional.
    """
    last_sunday = today - timedelta(days=today.weekday() + 1)
    last_monday = last_sunday - timedelta(days=6)
    iso_year, iso_week, _ = last_monday.isocalendar()
    week_id = f"{iso_year}-W{iso_week:02d}"
    date_range = f"{last_monday.isoformat()} ~ {last_sunday.isoformat()}"
    return week_id, date_range


class IntelScheduler:
    def __init__(
        self,
        config: AppConfig,
        registry: Registry,
        pipeline: CollectionPipeline,
        refinement_pipeline: RefinementPipeline | None = None,
    ):
        self._config = config
        self._registry = registry
        self._pipeline = pipeline
        self._refinement_pipeline = refinement_pipeline
        # 로컬 패치 L5: 명시적 timezone으로 실행. 시스템 TZ에 의존하지 않아 컨테이너/
        # 서버 배포 환경 차이로 실제 실행 시각이 달라지는 문제를 방지한다.
        self._scheduler = BlockingScheduler(timezone=ZoneInfo(config.collection.timezone))
        self._rss = RssSource()
        self._sns = SnsSource()
        self._web = WebSource()
        self._youtube = YoutubeSource()

    def _register_jobs(self):
        """Register all scheduled jobs. Separated from start() for testability."""
        interval_hours = self._config.collection.interval_hours
        self._scheduler.add_job(
            self._run_collection_cycle,
            "interval",
            hours=interval_hours,
            id="collection_cycle",
        )
        logger.info(f"Scheduler started: collection every {interval_hours} hours")

        refinery = self._config.refinery
        if not refinery.enabled:
            logger.info("Weekly refinement cron disabled (refinery.enabled=false)")
            return
        if self._refinement_pipeline is None:
            logger.warning(
                "Weekly refinement cron skipped: refinement_pipeline not provided"
            )
            return

        day_of_week = _day_to_cron(refinery.schedule_day)
        self._scheduler.add_job(
            self._run_refinement_cycle,
            "cron",
            day_of_week=day_of_week,
            hour=refinery.schedule_hour,
            minute=refinery.schedule_minute,
            id="refinement_cycle",
        )
        logger.info(
            f"Weekly refinement cron scheduled: {day_of_week} "
            f"at {refinery.schedule_hour:02d}:{refinery.schedule_minute:02d}"
        )

    def _run_refinement_cycle(self, today: date | None = None):
        """Execute one weekly refinement cycle for the previous ISO week."""
        if today is None:
            today = datetime.now(ZoneInfo(self._config.collection.timezone)).date()

        week_id, date_range = _compute_previous_week(today)
        logger.info(f"Starting weekly refinement: {week_id} ({date_range})")

        raw_dir = self._config.vault_path / "raw"
        target_dates = [
            today - timedelta(days=today.weekday() + 1) - timedelta(days=i)
            for i in range(7)
        ]
        has_any = any((raw_dir / d.isoformat()).exists() for d in target_dates)
        if not has_any:
            logger.warning(f"Refinement skipped: no raw data for {date_range}")
            return

        try:
            self._refinement_pipeline.run(week=week_id, date_range=date_range)
            logger.info(f"Weekly refinement complete: {week_id}")
        except Exception:
            logger.exception(f"Refinement failed for {week_id} ({date_range})")

    def _run_collection_cycle(self):
        """Execute one full collection cycle across all companies and sources."""
        logger.info("Starting collection cycle")

        for company in self._registry.companies:
            # RSS feeds
            if self._config.collection.sources.rss:
                for feed_url in company.sources.get("rss", []):
                    try:
                        items = self._rss.fetch_from_url(feed_url)
                    except Exception:
                        logger.exception(f"RSS fetch failed for {feed_url}")
                        continue
                    for item in items:
                        try:
                            self._pipeline.process_item(item)
                        except Exception:
                            logger.exception(f"RSS process_item failed for {item.url}")

            # Official web pages
            if self._config.collection.sources.web:
                for page_url in company.sources.get("official", []):
                    try:
                        items = self._web.fetch_from_url(page_url)
                    except Exception:
                        logger.exception(f"Web fetch failed for {page_url}")
                        continue
                    for item in items:
                        try:
                            self._pipeline.process_item(item)
                        except Exception:
                            logger.exception(f"Web process_item failed for {item.url}")

            # SNS (Reddit search by company name)
            if self._config.collection.sources.sns:
                try:
                    items = self._sns.fetch_reddit("robotics", company.name)
                except Exception:
                    logger.exception(f"SNS fetch failed for {company.name}")
                    items = []
                for item in items:
                    try:
                        self._pipeline.process_item(item)
                    except Exception:
                        logger.exception(f"SNS process_item failed for {item.url}")

            # YouTube channels — L6 resolved: discovery via public Atom feed.
            # fetch_channel_videos returns items whose body is the Atom entry
            # description (not the transcript). Transcript extraction remains
            # an opt-in path via YoutubeSource.fetch_from_url; see
            # src/sources/youtube.py::fetch_channel_videos for rationale.
            if self._config.collection.sources.youtube:
                for channel in company.sources.get("youtube", []):
                    try:
                        items = self._youtube.fetch_channel_videos(channel)
                    except Exception:
                        logger.exception(f"YouTube fetch failed for {channel}")
                        continue
                    for item in items:
                        try:
                            self._pipeline.process_item(item)
                        except Exception:
                            logger.exception(
                                f"YouTube process_item failed for {item.url}"
                            )

        logger.info("Collection cycle complete")

    def start(self):
        """Start the scheduler with all registered jobs."""
        self._register_jobs()
        self._scheduler.start()

    def run_once(self):
        """Run a single collection cycle without scheduling."""
        self._run_collection_cycle()
