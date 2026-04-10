from __future__ import annotations

import json
from pathlib import Path

from src.gateway.gateway import LLMGateway
from src.registry import Registry
from src.writer.frontmatter import parse_document
from src.writer.profile_writer import ProfileWriter
from src.writer.vault import VaultManager
from src.writer.weekly_writer import WeeklyWriter


SUMMARIZER_SYSTEM = """You are a senior Physical AI market strategist.
Your task is to create a strategic weekly summary and update company/topic profiles.
Focus on: strategic implications, market positioning, technology trends, partnerships.
Use [[WikiLinks]] for company and topic names.
Evaluate source reliability through corpus agreement (multiple sources confirming same facts = higher confidence)."""

SUMMARIZER_PROMPT = """## Consolidated Report (this week)
{consolidated}

## Current Company Profiles
{profiles}

## Instructions
Create a JSON response with these keys:
1. "snapshot": Weekly snapshot content (Markdown) following this structure:
   ## 주요 하이라이트
   ## 회사별 동향
   ## 기술/트렌드별 동향
   ## 신뢰도 이슈
   ## 시사점 / 관찰

2. "company_updates": dict of company_name -> updated full body (Markdown) for each company that has new information. Follow the template: 회사 개요 / 최근 동향 / 기술 스택 / 파트너십 / 전망 / 기타 노트

3. "topic_updates": dict of topic_name -> updated full body (Markdown) for each topic that has new information.

Return valid JSON only."""


class Summarizer:
    def __init__(
        self,
        gateway: LLMGateway,
        model: str,
        vault: VaultManager,
        registry: Registry,
        profile_writer: ProfileWriter,
        weekly_writer: WeeklyWriter,
    ):
        self._gateway = gateway
        self._model = model
        self._vault = vault
        self._registry = registry
        self._profile_writer = profile_writer
        self._weekly_writer = weekly_writer

    def run(self, week: str, date_range: str) -> Path:
        """Run summarization. Returns path to weekly snapshot."""
        # 1. Read consolidated report
        consolidated_path = self._vault.weekly_dir / f"{week}-consolidated.md"
        _, consolidated = parse_document(consolidated_path.read_text(encoding="utf-8"))

        # 2. Read current profiles
        profiles = self._read_current_profiles()

        # 3. Call Claude for summary
        prompt = SUMMARIZER_PROMPT.format(
            consolidated=consolidated,
            profiles=profiles,
        )

        response = self._gateway.call(self._model, prompt=prompt, system=SUMMARIZER_SYSTEM)

        # 4. Parse response and write outputs
        try:
            result = json.loads(response.content)
        except json.JSONDecodeError:
            # If JSON parse fails, use raw content as snapshot
            return self._weekly_writer.write_snapshot(week=week, date_range=date_range, content=response.content)

        # Write weekly snapshot
        snapshot_path = self._weekly_writer.write_snapshot(
            week=week,
            date_range=date_range,
            content=result.get("snapshot", response.content),
        )

        # Update company profiles
        for company_name, new_body in result.get("company_updates", {}).items():
            try:
                self._profile_writer.update_company(company_name, new_body)
            except FileNotFoundError:
                pass  # Company profile doesn't exist yet

        # Update topic profiles
        for topic_name, new_body in result.get("topic_updates", {}).items():
            try:
                self._profile_writer.update_topic(topic_name, new_body)
            except FileNotFoundError:
                pass

        return snapshot_path

    def _read_current_profiles(self) -> str:
        """Read all current company and topic profiles."""
        sections = []

        for md_file in sorted(self._vault.companies_dir.glob("*.md")):
            metadata, body = parse_document(md_file.read_text(encoding="utf-8"))
            sections.append(f"### {md_file.stem}\n{body}")

        for md_file in sorted(self._vault.topics_dir.glob("*.md")):
            metadata, body = parse_document(md_file.read_text(encoding="utf-8"))
            sections.append(f"### {md_file.stem}\n{body}")

        return "\n---\n".join(sections) if sections else "(No profiles yet)"
