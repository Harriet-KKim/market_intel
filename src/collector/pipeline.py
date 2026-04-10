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
from src.writer.wikilink import inject_wikilinks  # 로컬 패치 P1


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

        # 2. Tag with LLM
        company_ids, keyword_ids = self._tag_item(item)

        # 3. Build article dict
        now = datetime.now(timezone.utc).isoformat()
        article_id = f"{item.source_type}-{uuid.uuid4().hex[:8]}"

        company_links = [f"[[{self._registry.get_company(cid).name}]]" for cid in company_ids if self._registry.get_company(cid)]
        reputation = self._registry.get_reputation_score(item.source_name)

        # 로컬 패치 P1: 본문 내부 회사/주제 이름을 [[WikiLink]]로 치환해 Obsidian Backlinks에 잡히게 함.
        # frontmatter `companies` 필드만 남기면 본문 어디에 언급됐는지 역인덱스가 끊깁니다.
        linked_body = inject_wikilinks(item.body, self._registry)

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
            "body": linked_body,
        }

        if item.source_type == "video":
            article["has_visual_analysis"] = item.has_visual_analysis
            article["source"]["channel"] = item.channel

        # 4. Write to vault
        # 로컬 패치 L7: mark_seen은 write 성공 이후에만 호출. 원래 코드는 is_seen 체크
        # 직후 mark_seen을 찍었기 때문에, tagging/write 중 크래시가 나면 URL은 dedup DB에만
        # 남고 파일은 없는 영구 누락 상태가 됐습니다.
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        result_path = self._raw_writer.write(article, date=date_str)
        self._dedup.mark_seen(item.url)
        return result_path

    def _tag_item(self, item: CollectedItem) -> tuple[list[str], list[str]]:
        """Use LLM to tag companies and keywords."""
        companies_str = ", ".join(f"{c.id} ({c.name})" for c in self._registry.companies)
        keywords_str = ", ".join(f"{k.id} ({k.name})" for k in self._registry.keywords)

        # 로컬 패치 L17: LLM 경로와 fallback 경로가 같은 입력을 쓰도록 정렬. 원래 코드는
        # LLM에는 `item.body[:2000]`을 보내면서 fallback에서는 전체 body를 매칭해 동일
        # 아이템이 경로에 따라 다른 태깅 결과를 낼 수 있었습니다.
        text_for_tagging = item.body[:2000]

        prompt = TAGGING_PROMPT_TEMPLATE.format(
            companies=companies_str,
            keywords=keywords_str,
            title=item.title,
            body=text_for_tagging,
        )

        response = self._gateway.call(self._tagging_model, prompt=prompt)

        try:
            result = json.loads(response.content)
            return result.get("companies", []), result.get("keywords", [])
        except (json.JSONDecodeError, KeyError):
            # Fallback: use registry pattern matching on the same truncated text
            return (
                self._registry.match_companies(text_for_tagging),
                self._registry.match_keywords(text_for_tagging),
            )
