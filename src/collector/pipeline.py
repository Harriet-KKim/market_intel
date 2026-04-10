from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.dedup import UrlDedup
from src.gateway.gateway import LLMGateway
from src.registry import Registry
from src.sources.base import CollectedItem
from src.writer.raw_writer import RawWriter


TAGGING_PROMPT_TEMPLATE = """You are a tagging agent. Given the following article, identify which companies and keywords from the registry are mentioned.

## Registry
Companies: {companies}
Keywords: {keywords}

## Article
Title: {title}
Body: {body}

## Output
Return a JSON object with two keys:
- "companies": list of company IDs from the registry that are mentioned
- "keywords": list of keyword IDs from the registry that are mentioned

Only include companies/keywords that are actually relevant to the article content. Return valid JSON only."""


class CollectionPipeline:
    def __init__(
        self,
        gateway: LLMGateway,
        tagging_model: str,
        registry: Registry,
        dedup: UrlDedup,
        raw_writer: RawWriter,
    ):
        self._gateway = gateway
        self._tagging_model = tagging_model
        self._registry = registry
        self._dedup = dedup
        self._raw_writer = raw_writer

    def process_item(self, item: CollectedItem) -> Path | None:
        """Process a single collected item through the pipeline. Returns file path or None if deduped."""
        # 1. URL dedup
        if self._dedup.is_seen(item.url):
            return None
        self._dedup.mark_seen(item.url)

        # 2. Tag with LLM
        company_ids, keyword_ids = self._tag_item(item)

        # 3. Build article dict
        now = datetime.now(timezone.utc).isoformat()
        article_id = f"{item.source_type}-{uuid.uuid4().hex[:8]}"

        company_links = [f"[[{self._registry.get_company(cid).name}]]" for cid in company_ids if self._registry.get_company(cid)]
        reputation = self._registry.get_reputation_score(item.source_name)

        article = {
            "id": article_id,
            "title": item.title,
            "source": {
                "type": item.source_type,
                "name": item.source_name,
                "url": item.url,
                "author": item.author,
            },
            "collected_at": now,
            "published_at": item.published_at,
            "language": item.language,
            "companies": company_links,
            "tags": keyword_ids,
            "reliability": reputation,
            "content_type": item.content_type,
            "body": item.body,
        }

        if item.source_type == "video":
            article["has_visual_analysis"] = item.has_visual_analysis
            article["source"]["channel"] = item.channel

        # 4. Write to vault
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self._raw_writer.write(article, date=date_str)

    def _tag_item(self, item: CollectedItem) -> tuple[list[str], list[str]]:
        """Use LLM to tag companies and keywords."""
        companies_str = ", ".join(f"{c.id} ({c.name})" for c in self._registry.companies)
        keywords_str = ", ".join(f"{k.id} ({k.name})" for k in self._registry.keywords)

        prompt = TAGGING_PROMPT_TEMPLATE.format(
            companies=companies_str,
            keywords=keywords_str,
            title=item.title,
            body=item.body[:2000],  # Limit body length for token efficiency
        )

        response = self._gateway.call(self._tagging_model, prompt=prompt)

        try:
            result = json.loads(response.content)
            return result.get("companies", []), result.get("keywords", [])
        except (json.JSONDecodeError, KeyError):
            # Fallback: use registry pattern matching
            return self._registry.match_companies(item.body), self._registry.match_keywords(item.body)
