from __future__ import annotations

import logging
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler

from src.config import AppConfig
from src.registry import Registry
from src.sources.rss import RssSource
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
        self._scheduler = BlockingScheduler()
        self._rss = RssSource()
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
                        for item in items:
                            self._pipeline.process_item(item)
                    except Exception as e:
                        logger.error(f"RSS fetch failed for {feed_url}: {e}")

            # Official web pages
            if self._config.collection.sources.web:
                for page_url in company.sources.get("official", []):
                    try:
                        items = self._web.fetch_from_url(page_url)
                        for item in items:
                            self._pipeline.process_item(item)
                    except Exception as e:
                        logger.error(f"Web fetch failed for {page_url}: {e}")

            # YouTube channels
            if self._config.collection.sources.youtube:
                for channel in company.sources.get("youtube", []):
                    try:
                        # YouTube channel fetching requires search API or scraping
                        # Individual video URLs would be discovered and processed
                        logger.info(f"YouTube channel check: {channel}")
                    except Exception as e:
                        logger.error(f"YouTube fetch failed for {channel}: {e}")

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
