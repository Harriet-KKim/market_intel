# 09. Refinery (Weekly Refinement Pipeline) — 구현 계획

> 이 파일은 전체 구현 플랜의 일부입니다.
> 인덱스: [README.md](./README.md) · 원본 통합본: [../superpowers/plans/2026-04-09-market-intel-implementation.md](../superpowers/plans/2026-04-09-market-intel-implementation.md) · 설계 스펙: [../superpowers/specs/2026-04-09-market-intel-system-design.md](../superpowers/specs/2026-04-09-market-intel-system-design.md)

**모듈:** `src/refinery/` (consolidator, summarizer, reviewer, pipeline)
**역할:** 주간 3-step 멀티모델 정제 파이프라인. 원본 데이터를 통합 → 요약 → 검토.
**핵심 설계 포인트 — Context Branching:**
- **Step 1 (Consolidator, GPT5 Pro)**: 원본 raw 데이터를 직접 읽고 구조화된 factual report 생성. 이 세션을 **Checkpoint**로 저장.
- **Step 2 (Summarizer, Claude Opus)**: 새 세션(독립 context)에서 Consolidated + 현재 profile을 받아 snapshot · company_updates · topic_updates JSON 생성 → WeeklyWriter / ProfileWriter로 파일 업데이트.
- **Step 3 (Reviewer, GPT5 Pro)**: **Step 1 Checkpoint에서 분기**하여 Step 2 snapshot을 검토. 분기로 인해 Step 2의 중간 생성물이 Step 3 context를 오염시키지 않음 — "Step 1의 원본 기억"만 기반으로 검토.
- 파이프라인 오케스트레이터(`RefinementPipeline`)는 이 3단계를 순서대로 실행하고 `session.checkpoint()`로 Step 3 분기점을 넘겨줌.
- **로컬 패치 I5 (Consolidator date_range 필터):** 원본 플랜의 `_read_raw_data`는 `date_range` 인자를 무시하고 `raw/` 하위의 *모든* 날짜 폴더를 스캔했습니다. 그 결과 "2026-W15 주간 정제" 호출이 과거 6개월치 데이터를 전부 GPT5 Pro에 집어넣어 (a) 토큰 폭발, (b) 지난 주 정보가 이번 주 스냅샷에 섞여 들어감. 본 패치는 `date_range`("YYYY-MM-DD ~ YYYY-MM-DD") 문자열을 파싱해 범위 내 날짜 폴더만 읽도록 수정합니다.
- **로컬 패치 I4 (Reviewer system override):** Reviewer가 Step 1 Checkpoint에서 분기할 때 Consolidator의 system prompt("You are a market intelligence analyst... consolidate raw data into a structured factual report")를 그대로 물려받으면 역할이 "검토자"가 아닌 "통합자"가 되어 이미 본 데이터를 다시 통합하는 응답을 생성할 위험이 있습니다. `Session.branch(checkpoint, system_override=REVIEWER_SYSTEM)`로 history(원본 기억)는 보존하면서 역할만 reviewer로 교체합니다. `branch`의 `system_override` 인자는 [04-gateway.md](./04-gateway.md)의 로컬 패치 I4에서 추가됐습니다.

**선행 의존:** [02-registry.md](./02-registry.md), [04-gateway.md](./04-gateway.md) (Session/Checkpoint 필수), [05-writer.md](./05-writer.md)
**공용 fixture:** `sample_registry_dir` — `tests/conftest.py` (Task 2에서 생성). Task 15의 `test_consolidator_generates_report`와 Task 17의 `test_full_refinement_pipeline`이 사용합니다.
**다음 단계:** [10-main.md](./10-main.md)

포함 태스크:
- [Task 15: Consolidator (Step 1)](#task-15-consolidator-step-1)
- [Task 16: Summarizer (Step 2)](#task-16-summarizer-step-2)
- [Task 17: Reviewer (Step 3) & Refinement Pipeline](#task-17-reviewer-step-3--refinement-pipeline)

---

## Phase 5: Weekly Refinement Pipeline

### Task 15: Consolidator (Step 1)

**Files:**
- Create: `src/refinery/__init__.py`
- Create: `src/refinery/consolidator.py`
- Create: `tests/test_consolidator.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_consolidator.py
from src.gateway.base_adapter import LLMResponse


def test_consolidator_generates_report(tmp_path, sample_registry_dir):
    from src.refinery.consolidator import Consolidator
    from src.writer.vault import VaultManager
    from src.writer.raw_writer import RawWriter
    from src.writer.weekly_writer import WeeklyWriter
    from src.registry import Registry
    from src.gateway.gateway import LLMGateway
    from src.gateway.base_adapter import BaseAdapter
    from src.gateway.session import Session

    # Write some raw data
    vault = VaultManager(tmp_path / "vault")
    raw_writer = RawWriter(vault)
    raw_writer.write({
        "id": "article-001",
        "title": "NVIDIA GR00T 2.0",
        "source": {"type": "news", "name": "TechCrunch", "url": "https://ex.com/1", "author": "J"},
        "collected_at": "2026-04-08T14:00:00Z",
        "published_at": "2026-04-08T12:00:00Z",
        "language": "en",
        "companies": ["[[NVIDIA]]"],
        "tags": ["humanoid-robot"],
        "reliability": 0.7,
        "content_type": "article",
        "body": "NVIDIA launched GR00T 2.0.",
    }, date="2026-04-08")

    # Mock GPT5 Pro
    class MockAdapter(BaseAdapter):
        def call(self, prompt, system=None, **kwargs):
            return LLMResponse(content="## Consolidated Report\n- NVIDIA: GR00T 2.0 launched", input_tokens=100, output_tokens=50)
        def call_with_history(self, messages, system=None, **kwargs):
            return LLMResponse(content="## Consolidated Report\n- NVIDIA: GR00T 2.0 launched", input_tokens=100, output_tokens=50)

    gateway = LLMGateway()
    gateway.register_adapter("gpt5-pro", MockAdapter())

    registry = Registry(sample_registry_dir)
    weekly_writer = WeeklyWriter(vault)

    consolidator = Consolidator(
        gateway=gateway,
        model="gpt5-pro",
        vault=vault,
        registry=registry,
        weekly_writer=weekly_writer,
    )

    session, path = consolidator.run(week="2026-W15", date_range="2026-04-06 ~ 2026-04-12")

    assert path.exists()
    assert "GR00T 2.0" in path.read_text(encoding="utf-8")
    assert session is not None  # Session returned for checkpoint


def test_consolidator_filters_raw_by_date_range(tmp_path, sample_registry_dir):
    """로컬 패치 I5: date_range 밖의 raw는 LLM 프롬프트에 포함되면 안 된다.

    원본 플랜의 `_read_raw_data`는 인자를 무시하고 raw/ 전체를 스캔해 이전 주 데이터가
    이번 주 consolidation에 섞여 들어갔습니다. 이 테스트는 프롬프트를 캡처하는 어댑터로
    "주간 경계 밖 본문이 프롬프트에 나타나지 않음"을 검증합니다.
    """
    from src.refinery.consolidator import Consolidator
    from src.writer.vault import VaultManager
    from src.writer.raw_writer import RawWriter
    from src.writer.weekly_writer import WeeklyWriter
    from src.registry import Registry
    from src.gateway.gateway import LLMGateway
    from src.gateway.base_adapter import BaseAdapter

    vault = VaultManager(tmp_path / "vault")
    raw_writer = RawWriter(vault)

    # In-range article (2026-04-08 — 2026-W15의 한가운데)
    raw_writer.write({
        "id": "article-in",
        "title": "In-range headline",
        "source": {"type": "news", "name": "TechCrunch", "url": "https://ex.com/in", "author": "A"},
        "collected_at": "2026-04-08T14:00:00Z",
        "published_at": "2026-04-08T12:00:00Z",
        "language": "en",
        "companies": ["[[NVIDIA]]"],
        "tags": ["humanoid-robot"],
        "reliability": 0.7,
        "content_type": "article",
        "body": "INRANGE_TOKEN body text",
    }, date="2026-04-08")

    # Out-of-range article (2026-03-20 — 3주 이전)
    raw_writer.write({
        "id": "article-out",
        "title": "Out-of-range headline",
        "source": {"type": "news", "name": "TechCrunch", "url": "https://ex.com/out", "author": "A"},
        "collected_at": "2026-03-20T14:00:00Z",
        "published_at": "2026-03-20T12:00:00Z",
        "language": "en",
        "companies": ["[[NVIDIA]]"],
        "tags": ["humanoid-robot"],
        "reliability": 0.7,
        "content_type": "article",
        "body": "OUTRANGE_TOKEN body text",
    }, date="2026-03-20")

    captured_prompts: list[str] = []

    class CapturingAdapter(BaseAdapter):
        def call(self, prompt, system=None, **kwargs):
            captured_prompts.append(prompt)
            return LLMResponse(content="ok", input_tokens=0, output_tokens=0)
        def call_with_history(self, messages, system=None, **kwargs):
            captured_prompts.append(messages[-1]["content"])
            return LLMResponse(content="ok", input_tokens=0, output_tokens=0)

    gateway = LLMGateway()
    gateway.register_adapter("gpt5-pro", CapturingAdapter())

    registry = Registry(sample_registry_dir)
    weekly_writer = WeeklyWriter(vault)

    consolidator = Consolidator(
        gateway=gateway,
        model="gpt5-pro",
        vault=vault,
        registry=registry,
        weekly_writer=weekly_writer,
    )

    consolidator.run(week="2026-W15", date_range="2026-04-06 ~ 2026-04-12")

    assert captured_prompts, "Consolidator did not call the gateway"
    combined = "\n".join(captured_prompts)
    assert "INRANGE_TOKEN" in combined, "범위 내 본문이 프롬프트에 포함되어야 합니다"
    assert "OUTRANGE_TOKEN" not in combined, (
        "범위 밖 본문이 프롬프트에 새어들어갔습니다. _read_raw_data의 date_range 필터 미적용."
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_consolidator.py -v`
Expected: FAIL

- [ ] **Step 3: Implement consolidator**

```python
# src/refinery/__init__.py
```

```python
# src/refinery/consolidator.py
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from src.gateway.gateway import LLMGateway
from src.gateway.session import Session
from src.registry import Registry
from src.writer.vault import VaultManager
from src.writer.weekly_writer import WeeklyWriter
from src.writer.frontmatter import parse_document


CONSOLIDATION_SYSTEM = """You are a market intelligence analyst specializing in Physical AI.
Your task is to consolidate raw collected data into a structured factual report.
Organize by company and by topic. Do NOT summarize — preserve all facts.
Include source reliability scores where available.
Use [[WikiLinks]] for company and topic names."""

CONSOLIDATION_PROMPT = """## Registry
Companies: {companies}
Keywords: {keywords}

## Raw Data (this week)
{raw_data}

## Instructions
Consolidate the above raw data into a structured report organized by:
1. Company-wise developments
2. Topic/trend-wise developments
Preserve all facts. Note source names and reliability scores."""


class Consolidator:
    def __init__(
        self,
        gateway: LLMGateway,
        model: str,
        vault: VaultManager,
        registry: Registry,
        weekly_writer: WeeklyWriter,
    ):
        self._gateway = gateway
        self._model = model
        self._vault = vault
        self._registry = registry
        self._weekly_writer = weekly_writer

    def run(self, week: str, date_range: str) -> tuple[Session, Path]:
        """Run consolidation. Returns (session for checkpoint, path to consolidated file)."""
        # 1. Read all raw data for this week's date range
        raw_data = self._read_raw_data(date_range)

        # 2. Create session and send consolidation request
        session = Session(gateway=self._gateway, model=self._model, system=CONSOLIDATION_SYSTEM)

        companies_str = ", ".join(f"{c.name}" for c in self._registry.companies)
        keywords_str = ", ".join(f"{k.name}" for k in self._registry.keywords)

        prompt = CONSOLIDATION_PROMPT.format(
            companies=companies_str,
            keywords=keywords_str,
            raw_data=raw_data,
        )

        response = session.send(prompt)

        # 3. Write consolidated report
        path = self._weekly_writer.write_consolidated(
            week=week,
            date_range=date_range,
            content=response.content,
        )

        return session, path

    def _read_raw_data(self, date_range: str) -> str:
        """Read raw files whose date folder falls within ``date_range``.

        로컬 패치 I5: 원본 플랜은 ``date_range``를 무시하고 ``raw/`` 전체를 스캔했습니다.
        이번 주 정제 호출이 과거 모든 raw 데이터를 다시 GPT5 Pro에 밀어넣어 비용 폭발과
        기간 오염이 발생했습니다. ``raw_writer``는 ``date`` 인자(``YYYY-MM-DD``)로 폴더를
        만들므로, 폴더 이름을 ``date.fromisoformat``로 파싱해 범위 내만 선택합니다.
        파싱 실패 폴더는 보수적으로 건너뜁니다.
        """
        raw_dir = self._vault.vault_path / "raw"
        if not raw_dir.exists():
            return "(No raw data found)"

        start, end = self._parse_date_range(date_range)

        all_content = []
        for date_dir in sorted(raw_dir.iterdir()):
            if not date_dir.is_dir():
                continue
            try:
                dir_date = date.fromisoformat(date_dir.name)
            except ValueError:
                continue
            if start is not None and dir_date < start:
                continue
            if end is not None and dir_date > end:
                continue
            for md_file in sorted(date_dir.glob("*.md")):
                metadata, body = parse_document(md_file.read_text(encoding="utf-8"))
                all_content.append(
                    f"### {metadata.get('title', md_file.stem)}\n"
                    f"Source: {metadata.get('source', {}).get('name', 'unknown')} "
                    f"(reliability: {metadata.get('reliability', 'N/A')})\n"
                    f"{body}\n"
                )

        return "\n---\n".join(all_content) if all_content else "(No raw data found)"

    @staticmethod
    def _parse_date_range(date_range: str) -> tuple[date | None, date | None]:
        """Parse ``"YYYY-MM-DD ~ YYYY-MM-DD"`` into an inclusive (start, end) pair.

        포맷이 어긋나면 ``(None, None)``을 반환하여 필터링을 건너뜁니다 — 로컬
        실험 중 포맷 오타로 주간 정제가 빈 결과를 내는 것을 피하기 위한 안전장치.
        """
        if not date_range or "~" not in date_range:
            return None, None
        left, _, right = date_range.partition("~")
        try:
            start = date.fromisoformat(left.strip())
            end = date.fromisoformat(right.strip())
        except ValueError:
            return None, None
        return start, end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_consolidator.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/refinery/ tests/test_consolidator.py
git commit -m "feat: consolidator (Step 1) for weekly refinement"
```

---

### Task 16: Summarizer (Step 2)

**Files:**
- Create: `src/refinery/summarizer.py`
- Create: `tests/test_summarizer.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_summarizer.py
from src.gateway.base_adapter import LLMResponse


def test_summarizer_generates_snapshot_and_updates(tmp_path, sample_registry_dir):
    from src.refinery.summarizer import Summarizer
    from src.writer.vault import VaultManager
    from src.writer.weekly_writer import WeeklyWriter
    from src.writer.profile_writer import ProfileWriter
    from src.registry import Registry
    from src.gateway.gateway import LLMGateway
    from src.gateway.base_adapter import BaseAdapter

    vault = VaultManager(tmp_path / "vault")
    registry = Registry(sample_registry_dir)
    profile_writer = ProfileWriter(vault)
    weekly_writer = WeeklyWriter(vault)

    # Create initial company profile
    profile_writer.create_company("NVIDIA", ["엔비디아"])

    # Write a consolidated file
    consolidated_path = weekly_writer.write_consolidated(
        week="2026-W15",
        date_range="2026-04-06 ~ 2026-04-12",
        content="## NVIDIA\n- GR00T 2.0 launched for humanoid robots",
    )

    class MockAdapter(BaseAdapter):
        def call(self, prompt, system=None, **kwargs):
            if "주간 스냅샷" in prompt or "snapshot" in prompt.lower():
                return LLMResponse(
                    content='{"snapshot": "## 주요 하이라이트\\n- NVIDIA GR00T 2.0 발표", "company_updates": {"NVIDIA": "## 회사 개요\\nGPU 기업\\n\\n## 최근 동향\\n- GR00T 2.0 발표\\n\\n## 기술 스택\\n\\n## 파트너십 / 생태계\\n\\n## 전망 / 시사점\\n\\n---\\n\\n## 기타 노트"}, "topic_updates": {}}',
                    input_tokens=200, output_tokens=100,
                )
            return LLMResponse(content="default", input_tokens=0, output_tokens=0)
        def call_with_history(self, messages, system=None, **kwargs):
            return self.call(messages[-1]["content"])

    gateway = LLMGateway()
    gateway.register_adapter("claude-opus", MockAdapter())

    summarizer = Summarizer(
        gateway=gateway,
        model="claude-opus",
        vault=vault,
        registry=registry,
        profile_writer=profile_writer,
        weekly_writer=weekly_writer,
    )

    snapshot_path = summarizer.run(week="2026-W15", date_range="2026-04-06 ~ 2026-04-12")

    assert snapshot_path.exists()
    assert "주요 하이라이트" in snapshot_path.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_summarizer.py -v`
Expected: FAIL

- [ ] **Step 3: Implement summarizer**

```python
# src/refinery/summarizer.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_summarizer.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add src/refinery/summarizer.py tests/test_summarizer.py
git commit -m "feat: summarizer (Step 2) for weekly refinement"
```

---

### Task 17: Reviewer (Step 3) & Refinement Pipeline

**Files:**
- Create: `src/refinery/reviewer.py`
- Create: `src/refinery/pipeline.py`
- Create: `tests/test_reviewer.py`
- Create: `tests/test_refinery_pipeline.py`

- [ ] **Step 1: Write failing test for reviewer**

```python
# tests/test_reviewer.py
from src.gateway.base_adapter import LLMResponse


def test_reviewer_adds_comment(tmp_path):
    from src.refinery.reviewer import Reviewer
    from src.writer.vault import VaultManager
    from src.writer.weekly_writer import WeeklyWriter
    from src.gateway.gateway import LLMGateway
    from src.gateway.session import Session, Checkpoint
    from src.gateway.base_adapter import BaseAdapter

    vault = VaultManager(tmp_path / "vault")
    weekly_writer = WeeklyWriter(vault)

    # Write a snapshot
    weekly_writer.write_snapshot(
        week="2026-W15",
        date_range="2026-04-06 ~ 2026-04-12",
        content="## 주요 하이라이트\n- NVIDIA GR00T 2.0 발표",
    )

    class MockAdapter(BaseAdapter):
        def call(self, prompt, system=None, **kwargs):
            return LLMResponse(content="review", input_tokens=0, output_tokens=0)
        def call_with_history(self, messages, system=None, **kwargs):
            return LLMResponse(
                content="검토 완료. 누락 사항 없음. 신뢰도 판정 적절.",
                input_tokens=50, output_tokens=30,
            )

    gateway = LLMGateway()
    gateway.register_adapter("gpt5-pro", MockAdapter())

    # Create a checkpoint from a mock session
    checkpoint = Checkpoint(
        history=[
            {"role": "user", "content": "consolidation prompt"},
            {"role": "assistant", "content": "consolidated report"},
        ],
        system="You are a reviewer.",
    )

    reviewer = Reviewer(
        gateway=gateway,
        model="gpt5-pro",
        vault=vault,
        weekly_writer=weekly_writer,
    )

    reviewer.run(week="2026-W15", checkpoint=checkpoint)

    content = (vault.weekly_dir / "2026-W15.md").read_text(encoding="utf-8")
    assert "검토 완료" in content
    assert "GPT5 Pro 검토" in content
```

- [ ] **Step 2: Write failing test for refinement pipeline**

```python
# tests/test_refinery_pipeline.py
from src.gateway.base_adapter import BaseAdapter, LLMResponse


def test_full_refinement_pipeline(tmp_path, sample_registry_dir):
    from src.refinery.pipeline import RefinementPipeline
    from src.writer.vault import VaultManager
    from src.writer.raw_writer import RawWriter
    from src.writer.weekly_writer import WeeklyWriter
    from src.writer.profile_writer import ProfileWriter
    from src.registry import Registry
    from src.gateway.gateway import LLMGateway

    vault = VaultManager(tmp_path / "vault")
    registry = Registry(sample_registry_dir)

    # Write raw data
    RawWriter(vault).write({
        "id": "article-001",
        "title": "Test",
        "source": {"type": "news", "name": "Test", "url": "https://ex.com", "author": "A"},
        "collected_at": "2026-04-08T00:00:00Z",
        "published_at": "2026-04-08T00:00:00Z",
        "language": "en",
        "companies": ["[[NVIDIA]]"],
        "tags": ["world-model"],
        "reliability": 0.7,
        "content_type": "article",
        "body": "Test body.",
    }, date="2026-04-08")

    # Create company profile
    ProfileWriter(vault).create_company("NVIDIA", ["엔비디아"])

    class MockGPT(BaseAdapter):
        def call(self, prompt, system=None, **kwargs):
            return LLMResponse(content="consolidated", input_tokens=10, output_tokens=5)
        def call_with_history(self, messages, system=None, **kwargs):
            last = messages[-1]["content"]
            if "consolidated" in str(messages[0].get("content", "")):
                return LLMResponse(content="review OK", input_tokens=10, output_tokens=5)
            return LLMResponse(content="## Consolidated\n- Test data", input_tokens=10, output_tokens=5)

    class MockClaude(BaseAdapter):
        def call(self, prompt, system=None, **kwargs):
            return LLMResponse(
                content='{"snapshot": "## 주요 하이라이트\\n- Test", "company_updates": {}, "topic_updates": {}}',
                input_tokens=20, output_tokens=10,
            )
        def call_with_history(self, messages, system=None, **kwargs):
            return self.call("")

    gateway = LLMGateway()
    gateway.register_adapter("gpt5-pro", MockGPT())
    gateway.register_adapter("claude-opus", MockClaude())

    pipeline = RefinementPipeline(
        gateway=gateway,
        consolidation_model="gpt5-pro",
        summarization_model="claude-opus",
        review_model="gpt5-pro",
        vault=vault,
        registry=registry,
    )

    pipeline.run(week="2026-W15", date_range="2026-04-06 ~ 2026-04-12")

    assert (vault.weekly_dir / "2026-W15-consolidated.md").exists()
    assert (vault.weekly_dir / "2026-W15.md").exists()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_reviewer.py tests/test_refinery_pipeline.py -v`
Expected: FAIL

- [ ] **Step 4: Implement reviewer**

```python
# src/refinery/reviewer.py
from __future__ import annotations

from src.gateway.gateway import LLMGateway
from src.gateway.session import Session, Checkpoint
from src.writer.frontmatter import parse_document
from src.writer.vault import VaultManager
from src.writer.weekly_writer import WeeklyWriter


# 로컬 패치 I4: Reviewer 전용 system prompt.
# 원본 플랜은 Step 1 checkpoint를 그대로 branch해 Consolidator의 "너는 통합자다"
# system prompt를 물려받았습니다. 역할이 "검토"가 아닌 "재통합"으로 편향될 위험이
# 있어 `Session.branch(..., system_override=REVIEWER_SYSTEM)`으로 덮어씁니다.
# history(원본 raw 기억)는 유지되므로 "원본을 아는 검토자"라는 설계 의도는 그대로.
REVIEWER_SYSTEM = """You are a senior Physical AI market strategist acting as a reviewer.
You previously saw the raw data during Step 1 consolidation (it is present in the conversation
history above). Use that memory to audit the weekly snapshot that follows.
Focus on: factual omissions vs. the raw corpus, overstatements, reliability calls, and
cross-company / cross-topic relationship accuracy. Do NOT re-consolidate. Do NOT rewrite
the snapshot. Produce a concise reviewer's note only."""

REVIEW_PROMPT = """다음은 Claude Opus가 생성한 주간 요약본입니다.
당신은 Step 1에서 원본 raw 데이터를 직접 읽었으므로, 그 기억을 기반으로 이 요약을 검토하세요.

## 주간 스냅샷
{snapshot}

## 검토 기준
1. 원본 데이터 대비 누락된 중요 정보가 있는가?
2. 사실이 왜곡되거나 과장된 부분이 있는가?
3. 신뢰도 판정이 적절한가?
4. 회사/주제 간 관계가 올바르게 반영되었는가?

검토 결과를 간결하게 작성하세요."""


class Reviewer:
    def __init__(
        self,
        gateway: LLMGateway,
        model: str,
        vault: VaultManager,
        weekly_writer: WeeklyWriter,
    ):
        self._gateway = gateway
        self._model = model
        self._vault = vault
        self._weekly_writer = weekly_writer

    def run(self, week: str, checkpoint: Checkpoint) -> str:
        """Run review by branching from the consolidation checkpoint."""
        # 1. Read snapshot
        snapshot_path = self._vault.weekly_dir / f"{week}.md"
        _, snapshot_body = parse_document(snapshot_path.read_text(encoding="utf-8"))

        # 2. Branch from the Step 1 checkpoint via Session.branch().
        #    (로컬 패치 I1) 원본 플랜은 Session 객체를 수동 생성한 뒤
        #    `session.history = list(checkpoint.history)`로 내부 상태를 인라인 복원했습니다.
        #    이 방식은 Session/Checkpoint 추상화를 우회하고, `copy.deepcopy`로 얻는
        #    격리성을 잃게 합니다. `Session.branch(checkpoint, ...)`를 사용해 일관된
        #    Context Branching API로 정렬합니다 — 이 분기는 Step 1(원본 데이터 통합)
        #    컨텍스트는 유지하지만 Step 2(Claude Opus summarization) 산출물은
        #    포함하지 않습니다.
        #    (로컬 패치 I4) system prompt는 `REVIEWER_SYSTEM`으로 덮어씁니다. Step 1의
        #    Consolidator system ("너는 통합자다")을 그대로 상속하면 reviewer가 다시
        #    통합 응답을 생성할 수 있습니다. history는 유지되므로 "원본을 아는 검토자"
        #    라는 설계 의도는 지켜집니다.
        seed = Session(gateway=self._gateway, model=self._model)
        session = seed.branch(checkpoint, system_override=REVIEWER_SYSTEM)

        # 3. Send review request
        prompt = REVIEW_PROMPT.format(snapshot=snapshot_body)
        response = session.send(prompt)

        # 4. Append review as comment
        self._weekly_writer.append_review(week, response.content)

        return response.content
```

- [ ] **Step 5: Implement refinement pipeline orchestrator**

```python
# src/refinery/pipeline.py
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
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_reviewer.py tests/test_refinery_pipeline.py -v`
Expected: 2 passed

- [ ] **Step 7: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 8: Commit**

```bash
git add src/refinery/ tests/test_reviewer.py tests/test_refinery_pipeline.py
git commit -m "feat: reviewer, refinement pipeline with 3-step multi-model flow"
```
