from __future__ import annotations

import logging

from src.gateway.gateway import LLMGateway
from src.registry import Registry
from src.writer.profile_writer import ProfileWriter
from src.writer.vault import VaultManager
from src.writer.weekly_writer import WeeklyWriter
from src.refinery.consolidator import Consolidator
from src.refinery.summarizer import Summarizer
from src.refinery.reviewer import Reviewer

logger = logging.getLogger(__name__)


class RefinementPipeline:
    def __init__(
        self,
        gateway: LLMGateway,
        consolidation_model: str,
        summarization_model: str,
        review_model: str,
        vault: VaultManager,
        registry: Registry,
    ):
        self._vault = vault
        self._weekly_writer = WeeklyWriter(vault)
        self._profile_writer = ProfileWriter(vault)

        self._consolidator = Consolidator(
            gateway=gateway,
            model=consolidation_model,
            vault=vault,
            registry=registry,
            weekly_writer=self._weekly_writer,
        )
        self._summarizer = Summarizer(
            gateway=gateway,
            model=summarization_model,
            vault=vault,
            registry=registry,
            profile_writer=self._profile_writer,
            weekly_writer=self._weekly_writer,
        )
        self._reviewer = Reviewer(
            gateway=gateway,
            model=review_model,
            vault=vault,
            weekly_writer=self._weekly_writer,
        )

    def run(self, week: str, date_range: str) -> None:
        """Execute the full 3-step refinement pipeline."""
        # Step 1: Consolidation (GPT5 Pro)
        logger.info(f"Step 1: Consolidating raw data for {week}")
        session, consolidated_path = self._consolidator.run(week=week, date_range=date_range)
        checkpoint = session.checkpoint()

        # Step 2: Summarization (Claude Opus)
        logger.info(f"Step 2: Generating summary for {week}")
        snapshot_path = self._summarizer.run(week=week, date_range=date_range)

        # Step 3: Review (GPT5 Pro, branching from checkpoint)
        logger.info(f"Step 3: Reviewing summary for {week}")
        review = self._reviewer.run(week=week, checkpoint=checkpoint)

        logger.info(f"Refinement complete for {week}")
