# 08. Scheduler — 구현 계획

> 이 파일은 전체 구현 플랜의 일부입니다.
> 인덱스: [README.md](./README.md) · 원본 통합본: [../superpowers/plans/2026-04-09-market-intel-implementation.md](../superpowers/plans/2026-04-09-market-intel-implementation.md) · 설계 스펙: [../superpowers/specs/2026-04-09-market-intel-system-design.md](../superpowers/specs/2026-04-09-market-intel-system-design.md)

**모듈:** `src/scheduler/`
**역할:** APScheduler 기반 주기적 수집 트리거. Registry를 순회하며 소스별 fetch → CollectionPipeline으로 위임.
**핵심 설계 포인트:**
- 얇은 glue 코드로 유지 — 실제 처리는 전부 `CollectionPipeline.process_item`.
- `start()`는 `BlockingScheduler`로 주기 실행, `run_once()`는 즉시 1회 실행(수동 트리거 / 테스트용).
- 소스별 on/off는 `config.collection.sources`가 결정. 개별 fetch 실패는 로그만 남기고 다음 진행 — 사이클이 끊기지 않도록 방어.
- YouTube 채널은 초기 단계에서 로그만 남기고 실제 영상 discovery는 추후 확장.

**선행 의존:** [01-config.md](./01-config.md), [02-registry.md](./02-registry.md), [06-sources.md](./06-sources.md), [07-collector.md](./07-collector.md)
**다음 단계:** [09-refinery.md](./09-refinery.md)

> ℹ️ **단위 테스트가 없는 이유 (로컬 패치 G4):** Task 14는 단위 테스트 파일을 생성하지 않습니다. `IntelScheduler`는 얇은 glue 코드(APScheduler + Registry 순회 + `CollectionPipeline.process_item` 위임)로, 실제 동작 검증은 `tests/test_collector_pipeline.py`(Task 13)가 커버합니다. APScheduler 자체는 자체 테스트 슈트를 가진 외부 의존이고, `_run_collection_cycle`의 try/except 블록 동작은 수동 실행으로 검증합니다. 새 로직(예: cron 표현식 파싱, 동적 source on/off)을 추가할 때는 단위 테스트를 같이 작성하세요.

---

## Phase 4: Collection Pipeline

### Task 14: Scheduler

**Files:**
- Create: `src/scheduler/__init__.py`
- Create: `src/scheduler/scheduler.py`

- [ ] **Step 1: Implement scheduler**

The scheduler is thin glue code that connects APScheduler with our pipeline. It reads config and registry to determine what to collect, when.

```python
# src/scheduler/__init__.py
```

```python
# src/scheduler/scheduler.py
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
```

- [ ] **Step 2: Commit**

```bash
git add src/scheduler/
git commit -m "feat: collection scheduler with APScheduler"
```
