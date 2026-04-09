# 07. Collector Pipeline — 구현 계획

> 이 파일은 전체 구현 플랜의 일부입니다.
> 인덱스: [README.md](./README.md) · 원본 통합본: [../superpowers/plans/2026-04-09-market-intel-implementation.md](../superpowers/plans/2026-04-09-market-intel-implementation.md) · 설계 스펙: [../superpowers/specs/2026-04-09-market-intel-system-design.md](../superpowers/specs/2026-04-09-market-intel-system-design.md)

**모듈:** `src/collector/`
**역할:** 수집 파이프라인 오케스트레이터. Source → Dedup → Tagging(LLM) → RawWriter 순으로 흐름 제어.
**핵심 설계 포인트:**
- URL dedup은 처리 진입부에서 수행, `process_item`은 중복 시 `None` 반환.
- 태깅은 Gemini(설정값)에게 prompt로 "Registry에 등재된 회사/키워드만 골라 JSON 반환" 지시. JSON 파싱 실패 시 Registry의 문자열 매칭으로 폴백.
- Body는 토큰 효율을 위해 앞부분 2000자만 프롬프트에 실음.
- 비디오(`source_type == "video"`) 아이템은 `has_visual_analysis` / `channel` 메타데이터 추가.
- **로컬 패치 P1:** 본문(`body`) 저장 전 `inject_wikilinks(item.body, registry)`를 호출해 회사/주제 이름을 `[[WikiLink]]`로 치환합니다. frontmatter의 `companies` 필드만으로는 본문 내부 언급이 Obsidian Backlinks에 잡히지 않아, CLAUDE.md의 "WikiLinks replace reference tables" 결정이 무너집니다. 원본 플랜은 `"body": item.body`로 원문을 그대로 저장했습니다.

**선행 의존:** [02-registry.md](./02-registry.md), [03-dedup.md](./03-dedup.md), [04-gateway.md](./04-gateway.md), [05-writer.md](./05-writer.md), [06-sources.md](./06-sources.md)
**공용 fixture:** `sample_registry_dir` — `tests/conftest.py` (Task 2에서 생성). `test_pipeline_processes_item` / `test_pipeline_dedup_skips_seen` 둘 다 사용합니다.
**다음 단계:** [08-scheduler.md](./08-scheduler.md)

---

## Phase 4: Collection Pipeline

### Task 13: Collection Pipeline Orchestrator

**Files:**
- Create: `src/collector/__init__.py`
- Create: `src/collector/pipeline.py`
- Create: `tests/test_collector_pipeline.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_collector_pipeline.py
from src.sources.base import CollectedItem
from src.gateway.base_adapter import LLMResponse


def make_test_item():
    return CollectedItem(
        title="NVIDIA GR00T 2.0",
        url="https://example.com/groot",
        body="NVIDIA launched GR00T 2.0 for humanoid robot control.",
        source_type="news",
        source_name="TechCrunch",
        author="John",
        published_at="2026-04-08T12:00:00Z",
        language="en",
        content_type="article",
    )


def test_pipeline_processes_item(tmp_path, sample_registry_dir):
    from src.collector.pipeline import CollectionPipeline
    from src.writer.vault import VaultManager
    from src.writer.raw_writer import RawWriter
    from src.registry import Registry
    from src.dedup import UrlDedup
    from src.gateway.gateway import LLMGateway
    from src.gateway.base_adapter import BaseAdapter

    # Mock gateway that returns tagging results as JSON
    class MockAdapter(BaseAdapter):
        def call(self, prompt: str, system: str | None = None, **kwargs) -> LLMResponse:
            return LLMResponse(
                content='{"companies": ["nvidia"], "keywords": ["humanoid-robot"]}',
                input_tokens=10,
                output_tokens=5,
            )
        def call_with_history(self, messages, system=None, **kwargs):
            return self.call(messages[-1]["content"])

    gateway = LLMGateway()
    gateway.register_adapter("gemini", MockAdapter())

    vault = VaultManager(tmp_path / "vault")
    registry = Registry(sample_registry_dir)
    dedup = UrlDedup(tmp_path / "dedup.db")
    raw_writer = RawWriter(vault)

    pipeline = CollectionPipeline(
        gateway=gateway,
        tagging_model="gemini",
        registry=registry,
        dedup=dedup,
        raw_writer=raw_writer,
    )

    item = make_test_item()
    result = pipeline.process_item(item)

    assert result is not None
    assert result.exists()
    content = result.read_text(encoding="utf-8")
    assert "[[NVIDIA]]" in content
    assert "humanoid-robot" in content

    # 로컬 패치 P1: frontmatter뿐 아니라 본문 내부에도 [[NVIDIA]] 링크가 주입돼야
    # Obsidian Backlinks가 "어떤 raw 노트가 NVIDIA를 언급했는지" 역인덱스를 구성할 수 있다.
    from src.writer.frontmatter import parse_document
    _, body = parse_document(content)
    assert "[[NVIDIA]]" in body, (
        "body 내부에 WikiLink가 주입되지 않았습니다. inject_wikilinks 호출 누락 가능성."
    )


def test_pipeline_dedup_skips_seen(tmp_path, sample_registry_dir):
    from src.collector.pipeline import CollectionPipeline
    from src.writer.vault import VaultManager
    from src.writer.raw_writer import RawWriter
    from src.registry import Registry
    from src.dedup import UrlDedup
    from src.gateway.gateway import LLMGateway
    from src.gateway.base_adapter import BaseAdapter

    class MockAdapter(BaseAdapter):
        def call(self, prompt, system=None, **kwargs):
            return LLMResponse(content='{"companies": [], "keywords": []}', input_tokens=0, output_tokens=0)
        def call_with_history(self, messages, system=None, **kwargs):
            return self.call("")

    gateway = LLMGateway()
    gateway.register_adapter("gemini", MockAdapter())

    vault = VaultManager(tmp_path / "vault")
    registry = Registry(sample_registry_dir)
    dedup = UrlDedup(tmp_path / "dedup.db")
    raw_writer = RawWriter(vault)

    pipeline = CollectionPipeline(
        gateway=gateway, tagging_model="gemini",
        registry=registry, dedup=dedup, raw_writer=raw_writer,
    )

    item = make_test_item()
    pipeline.process_item(item)
    result2 = pipeline.process_item(item)  # Same URL

    assert result2 is None  # Skipped
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_collector_pipeline.py -v`
Expected: FAIL

- [ ] **Step 3: Implement collection pipeline**

```python
# src/collector/__init__.py
```

```python
# src/collector/pipeline.py
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
        self._dedup.mark_seen(item.url)

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_collector_pipeline.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/collector/ tests/test_collector_pipeline.py
git commit -m "feat: collection pipeline orchestrator with tagging and dedup"
```
