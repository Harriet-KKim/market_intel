from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler

from src.config import AppConfig
from src.registry import Registry
from src.sources.rss import RssSource
from src.sources.sns import SnsSource
from src.sources.web import WebSource
from src.sources.youtube import YoutubeSource
from src.collector.pipeline import CollectionPipeline

logger = logging.getLogger(__name__)


class IntelScheduler:
    def __init__(
        self,
        config: AppConfig,
        registry: Registry,
        pipeline: CollectionPipeline,
    ):
        self._config = config
        self._registry = registry
        self._pipeline = pipeline
        # 로컬 패치 L5: 명시적 timezone으로 실행. 시스템 TZ에 의존하지 않아 컨테이너/
        # 서버 배포 환경 차이로 실제 실행 시각이 달라지는 문제를 방지한다.
        self._scheduler = BlockingScheduler(timezone=ZoneInfo(config.collection.timezone))
        self._rss = RssSource()
        self._sns = SnsSource()
        self._web = WebSource()
        self._youtube = YoutubeSource()

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

            # YouTube channels (discovery stub — L6)
            if self._config.collection.sources.youtube:
                for channel in company.sources.get("youtube", []):
                    logger.info(f"YouTube channel check: {channel}")

        logger.info("Collection cycle complete")

    def start(self):
        """Start the scheduler with configured intervals."""
        interval_hours = self._config.collection.interval_hours
        self._scheduler.add_job(
            self._run_collection_cycle,
            "interval",
            hours=interval_hours,
            id="collection_cycle",
        )
        logger.info(f"Scheduler started: collection every {interval_hours} hours")
        self._scheduler.start()

    def run_once(self):
        """Run a single collection cycle without scheduling."""
        self._run_collection_cycle()
