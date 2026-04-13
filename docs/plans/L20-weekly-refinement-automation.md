# L20 — Weekly Refinement 자동 스케줄링 설계 스펙 & 실행 플랜

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **문서 성격:** 상단 섹션("Goal"~"완료 기준")은 brainstorming 산출물(설계 스펙). 하단 섹션("작업 순서 개요"~"실행 완료 시점의 최종 상태 요약")은 writing-plans 산출물(실행 가능한 Task 단위 플랜).

## Goal

`main.py schedule` 프로세스가 **Collection 파이프라인뿐 아니라 Weekly Refinement 파이프라인까지 자동 실행**하도록 `IntelScheduler`를 확장한다. 현재는 `refine --week ... --date-range ...`를 사용자가 수동으로 매주 호출해야 하며, `src/config.py`의 `RefineryConfig(schedule_day, schedule_hour)`는 선언만 되어 있을 뿐 스케줄러가 참조하지 않는 **사장(死藏) 설정**이다.

Initial_Requirement.md 의 "일주일 이상의 단위로 축적된 정보 요약" 요건 중 "자동 실행" 축을 채우는 패치이다. 파이프라인 로직(`RefinementPipeline.run`)은 그대로 두고 트리거와 파라미터 자동 계산만 추가한다.

## Current State

- `src/scheduler/scheduler.py:107-115` — `start()`는 `collection_cycle` interval 잡 하나만 등록.
- `src/config.py:28-32` — `RefineryConfig` 선언되어 있고 `load_config`가 `schedule_day`·`schedule_hour`를 읽어 `AppConfig.refinery`에 담아두지만, 어디서도 소비되지 않는다.
- `config.yaml:11-13` — `refinery: schedule_day: "monday", schedule_hour: 9`. 풀네임 "monday"가 기본값이지만 APScheduler `CronTrigger.day_of_week`는 `mon/tue/...` 단축형(또는 `0-6` 숫자)만 허용.
- `src/main.py:213-219` — `schedule` 분기는 `CollectionPipeline`만 구성해 `IntelScheduler`에 주입. `RefinementPipeline`은 `refine` 분기에서만 생성됨.

## Architecture Decisions

### 1. 단일 `BlockingScheduler`에 interval + cron 잡 공존

`IntelScheduler`가 가진 기존 `BlockingScheduler` 인스턴스에 cron 잡을 한 건 더 등록한다. 별도 프로세스·데몬을 띄우지 않고 `main.py schedule` 한 번으로 두 파이프라인이 모두 돈다. `BlockingScheduler`는 기본 `default` executor(ThreadPoolExecutor, 10 workers)로 동작하므로, 월요일 정제와 interval 수집이 겹쳐도 서로 블록하지 않는다.

### 2. `RefinementPipeline` 의존성은 `main.py`에서 주입

`IntelScheduler.__init__`에 `refinement_pipeline: RefinementPipeline | None = None` 옵셔널 파라미터 추가. `None`이면 cron 잡을 등록하지 않는다. `main.py schedule` 분기에서 `setup_gateway()` → `RefinementPipeline(...)` 구성 후 전달한다. `collect` / `refine` 분기에서는 `None`을 유지하므로 기존 경로에 영향 없다.

### 3. Config 확장: `enabled` 플래그 + `schedule_minute` + day 정규화

기존 `RefineryConfig`에 두 필드 추가:

- `enabled: bool = True` — 기본값 True. `false`면 cron 잡 미등록.
- `schedule_minute: int = 0` — 기본값 0. cron 분 단위 지정.

그리고 APScheduler `day_of_week` 호환을 위해 **`CronTrigger` 호출 직전에 `_day_to_cron` 헬퍼로 정규화**한다. "monday" → "mon", "MONDAY" → "mon". 이미 `mon`이 입력된 경우 그대로 통과. 정규화 실패(알 수 없는 값)는 `ValueError`를 던져 잘못된 config를 조용히 삼키지 않는다.

`config.yaml` 기본값은 사용자의 원래 의도를 보존해 `schedule_day: "monday", schedule_hour: 9`를 유지한다(08:00~10:00 창이 "월요일 아침 지난주 요약" 요건과 일치). `enabled`와 `schedule_minute`는 키가 없으면 기본값으로 폴백하므로 기존 config 파일은 그대로 돌아간다.

### 4. 직전 주(월~일) 자동 계산 공식

```python
today = datetime.now(ZoneInfo(config.collection.timezone)).date()
last_sunday = today - timedelta(days=today.weekday() + 1)
last_monday = last_sunday - timedelta(days=6)
iso_year, iso_week, _ = last_monday.isocalendar()
week_id = f"{iso_year}-W{iso_week:02d}"
date_range = f"{last_monday.isoformat()} ~ {last_sunday.isoformat()}"
```

요일·시각 어떤 조합으로 cron을 설정하든 **"가장 가까운 과거 일요일 이전 7일"** 을 타깃으로 하므로, 사용자가 `schedule_day`를 "wed"로 바꿔도 같은 공식이 성립한다. ISO 주 식별자(`--week`)와 date_range 월~일 범위가 **항상 동일 주**를 가리킨다(슬라이딩 윈도우와의 정합성 문제 없음).

**엣지 케이스 — 일요일 실행:** `today.weekday()==6`이면 `today - timedelta(days=7)`이 지난 일요일이 되어 **이번 주(진행 중)를 건너뛰고 저번 주를 타깃**으로 한다. `config.yaml` 주석에 "일요일 실행은 직전 주 기준이 아니라 '두 주 전' 기준으로 오인되기 쉬우니 월~토 권장" 문구로 사용자에게 알린다. 본 설계는 이 동작을 바꾸지 않는다 — 일관된 공식을 유지해야 테스트가 간결하고, 실제로 주간 정제를 일요일 밤에 돌리려는 유즈 케이스는 드물다.

### 5. 빈 raw 데이터 가드

대상 주의 `vault/raw/YYYY-MM-DD/` 폴더 7개 중 **단 하나도 존재하지 않으면** `RefinementPipeline.run`을 호출하지 않고 `logger.warning`만 남기고 return. 콜드 스타트 직후 월요일 또는 장기 휴지 구간에서 GPT5 Pro 프롬프트에 빈 입력을 던져 비용·쓰레기 weekly 노트를 만드는 상황 방지.

I5 패치의 date_range 범위 필터는 **존재하는 raw 내부 중 이 주에 속하는 것만 고름**이지만, 폴더 존재 자체는 검증하지 않는다. 스케줄러 쪽에서 한 번 더 가드를 넣는 이유.

### 6. 실패 처리: 로그 + 다음 주까지 대기

`_run_refinement_cycle` 최상위를 `try / except Exception` 으로 감싸고 `logger.exception(...)`로 traceback을 남긴 뒤 return. APScheduler는 예외를 잡아 삼키는 기본 동작이므로 프로세스는 죽지 않고 다음 cron 시각에 다시 기동. 재시도 로직은 넣지 않는다 — 실패 후 수동 재실행이 필요하면 `py -m src.main refine --week 2026-W15 --date-range "..."` 경로를 사용. Step별 idempotent skip은 별도 백로그 **L8** 이므로 분리된 이슈.

## Risks & 연관 백로그

- **L1 (Profile 덮어쓰기)** — 자동 정제 활성화 상태에서 사용자가 `vault/companies/*.md` / `vault/topics/*.md`를 Obsidian에서 수동 편집하면 다음 주 실행 시 Summarizer가 통째로 덮어쓸 수 있다. 본 설계는 `enabled=true`를 기본값으로 택했고, 이는 L1이 해결 전이라는 사실을 사용자가 인지하고 감수한 결정이다. `config.yaml` 주석으로 위험을 문서화한다.
- **L2 (Raw 토큰 폭발)** — 정제 자동 실행 빈도가 늘어나도 주당 raw 볼륨 자체는 변하지 않으므로 본 패치가 L2의 트리거를 앞당기진 않는다.
- **L8 (Step 재시도 토큰 이중 소비)** — 자동 실행이 Step 3에서 실패하면 다음 주 월요일에 전체 재실행 없이 다음 주 데이터만 처리한다. 즉 "실패한 주를 다시 돌리려면 수동 CLI" 원칙이 강제된다. L8이 해결되면 `--resume-from` 플래그를 cron 잡에 연동하는 후속 작업이 가능.

## Config 스키마 (최종)

```yaml
refinery:
  # 로컬 패치 L20: IntelScheduler가 이 섹션을 참조해 cron 잡을 등록한다.
  # enabled=false 로 두면 주간 정제는 수동 CLI(`main.py refine`)로만 실행됨.
  # 주의: L1(프로필 덮어쓰기) 미해결 상태에서 활성화하면 수동 편집한 vault/companies/*.md,
  # vault/topics/*.md 가 다음 주 실행 시 통째로 덮어씌워질 수 있음.
  enabled: true
  schedule_day: "monday"    # "mon"도 허용. 내부적으로 _day_to_cron이 정규화.
  schedule_hour: 9
  schedule_minute: 0
```

기존 파일에 `enabled`·`schedule_minute`가 없으면 기본값(True, 0)로 로드된다. "monday"→"mon" 정규화 덕에 기존 config는 수정 없이 동작.

## 테스트 전략 (요약)

Task 단위 세부 항목은 writing-plans 산출물에서 상세화. 여기서는 커버리지 의도만 선언:

- **Config 레이어** (`tests/test_config.py` 확장) — `refinery.enabled`·`schedule_minute` 기본값 폴백, 명시 값 로딩, 미지원 `schedule_day` 문자열 예외 처리.
- **Scheduler 레이어** (`tests/test_scheduler.py` 확장) —
  - `enabled=true` + `refinement_pipeline` 주입 시 `BlockingScheduler.get_jobs()`에 `refinement_cycle` cron 잡 존재. trigger의 `day_of_week`·`hour`·`minute` 값이 config와 일치.
  - `enabled=false` 또는 `refinement_pipeline=None` 시 잡 미등록.
  - `freezegun` 또는 `monkeypatch`로 현재 시각을 월요일 09:00 KST로 고정(`config.yaml` 기본값과 일치) → `_run_refinement_cycle` 호출 시 Mock `RefinementPipeline.run` 이 `week="2026-W15"`, `date_range="2026-04-06 ~ 2026-04-12"` 인자로 호출됨.
  - 보조 테스트: 수요일 14:00 고정 → 같은 `week="2026-W15"`·`date_range`가 계산됨(실행 요일이 바뀌어도 공식이 동일함을 증명).
  - raw 폴더가 모두 비어있을 때 pipeline 미호출 + warning 로그.
  - Pipeline이 `RuntimeError` 를 던지면 스케줄러가 예외를 먹고 `logger.exception` 기록.
- **main.py schedule 배선** — 단위 테스트 없음(G4 규칙: glue 코드는 통합 테스트 영역). 스모크로 `schedule` 커맨드가 크래시 없이 두 잡을 등록하고 `BlockingScheduler.start()` 직전까지 진행되는지 확인하는 가벼운 통합 테스트 하나만 추가(즉 `scheduler.start()` 자체는 `Ctrl+C` 없이 종료되지 않으므로 `add_job` 직후를 패치해 검증).

## Out of Scope

- **다중 시간대·다중 국가 cron** — `collection.timezone` 하나를 공유.
- **Refinement 실패 재시도·이메일 알림** — L8 / 별도 알림 모듈.
- **Step별 partial resume** — L8.
- **주간 정제 중 interval 수집 일시정지** — 동시 실행 허용 (apscheduler 기본 executor가 스레드 풀링).
- **`vault/registry/*.yaml` 기본값 변경** — 본 패치는 config 스키마만 건드린다.

## 완료 기준

1. `py -m pytest tests/test_config.py tests/test_scheduler.py -v` 가 신규 테스트 포함 전체 PASS.
2. `py -m pytest tests/ -v` regression 없음.
3. `py -m src.main schedule`이 `config.yaml` 기본값(`enabled: true`)으로 실행될 때 로그에 `Scheduler started: collection every 6 hours` + `Weekly refinement cron scheduled: mon 09:00` 두 줄이 순서대로 찍힘.
4. `docs/plans/README.md` 의 "Resolved" 표에 L20 행 추가.

---

## 작업 순서 개요

| Task | 파일 | 스코프 | 커밋 |
|------|------|--------|------|
| 1 | `src/config.py` + `tests/test_config.py` | `RefineryConfig`에 `enabled`(bool, default True) + `schedule_minute`(int, default 0) 필드 추가. `load_config`가 두 키를 선택적으로 읽음. 3개 config 테스트 추가 | `feat: extend RefineryConfig with enabled and schedule_minute (L20 part 1)` |
| 2 | `src/scheduler/scheduler.py` + `tests/test_scheduler.py` | `_day_to_cron` 헬퍼 + `_compute_previous_week` 헬퍼 + `IntelScheduler.__init__`에 `refinement_pipeline` 옵셔널 파라미터 + `_register_jobs` 분리 + `_run_refinement_cycle` 메서드 + `start()`의 cron 잡 등록. 11개 스케줄러 테스트 추가 | `feat: wire weekly refinement cron job into IntelScheduler (L20 part 2)` |
| 3 | `src/main.py` + `config.yaml` | `main.py schedule` 분기에서 `RefinementPipeline` 구성해 `IntelScheduler`에 주입. `config.yaml` refinery 섹션에 `enabled: true`, `schedule_minute: 0` 추가 + L1 경고 주석 | `feat: wire RefinementPipeline into schedule command (L20 part 3)` |
| 4 | `docs/plans/README.md` | L20 을 "Resolved" 표에 추가 | `docs: mark L20 resolved in backlog index` |

작업은 프로젝트 루트 (`C:\Users\Harriet\Desktop\SST\AX Strategy\Research System\market_intel`)에서 실행. Windows 에서는 `python` 대신 `py -m pytest` 를 사용 (CLAUDE.md 지침).

---

## Task 1: Extend RefineryConfig with enabled + schedule_minute

**Files:**
- Modify: `src/config.py` (`RefineryConfig` dataclass + `load_config` 내 `RefineryConfig(...)` 생성자 호출)
- Modify: `tests/test_config.py` (파일 하단에 3개 테스트 추가)

- [ ] **Step 1: Write the failing tests**

`tests/test_config.py` **파일 하단에** 다음 3개 테스트를 추가한다(기존 테스트는 전혀 손대지 않는다 — `RefineryConfig`에 default 값을 주므로 기존 테스트는 계속 PASS):

```python
def test_load_config_refinery_enabled_defaults_to_true(tmp_path):
    """L20: refinery.enabled가 없으면 기본값 True."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
vault_path: "./vault"
collection:
  interval_hours: 6
  sources:
    rss: true
    web: true
    sns: true
    youtube: true
refinery:
  schedule_day: "monday"
  schedule_hour: 9
api_keys:
  gemini: "k1"
  openai: "k2"
  anthropic: "k3"
budget:
  enabled: false
  daily_limit_usd: 10.0
""")
    from src.config import load_config

    config = load_config(config_file)
    assert config.refinery.enabled is True
    assert config.refinery.schedule_minute == 0


def test_load_config_refinery_enabled_explicit_false(tmp_path):
    """L20: refinery.enabled: false 로 비활성화 가능."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
vault_path: "./vault"
collection:
  interval_hours: 6
  sources:
    rss: true
    web: true
    sns: true
    youtube: true
refinery:
  enabled: false
  schedule_day: "monday"
  schedule_hour: 9
  schedule_minute: 30
api_keys:
  gemini: "k1"
  openai: "k2"
  anthropic: "k3"
budget:
  enabled: false
  daily_limit_usd: 10.0
""")
    from src.config import load_config

    config = load_config(config_file)
    assert config.refinery.enabled is False
    assert config.refinery.schedule_minute == 30


def test_load_config_refinery_passthrough_day_string(tmp_path):
    """L20: schedule_day는 config에서 원문 그대로 읽히며, 정규화는 scheduler 책임."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
vault_path: "./vault"
collection:
  interval_hours: 6
  sources:
    rss: true
    web: true
    sns: true
    youtube: true
refinery:
  schedule_day: "wed"
  schedule_hour: 14
api_keys:
  gemini: "k1"
  openai: "k2"
  anthropic: "k3"
budget:
  enabled: false
  daily_limit_usd: 10.0
""")
    from src.config import load_config

    config = load_config(config_file)
    assert config.refinery.schedule_day == "wed"
    assert config.refinery.schedule_hour == 14
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
py -m pytest tests/test_config.py::test_load_config_refinery_enabled_defaults_to_true tests/test_config.py::test_load_config_refinery_enabled_explicit_false tests/test_config.py::test_load_config_refinery_passthrough_day_string -v
```

Expected:
- `test_load_config_refinery_enabled_defaults_to_true` FAIL — `AttributeError: 'RefineryConfig' object has no attribute 'enabled'`
- `test_load_config_refinery_enabled_explicit_false` FAIL — 같은 이유 또는 `TypeError: __init__() got an unexpected keyword argument 'enabled'`
- `test_load_config_refinery_passthrough_day_string` PASS (기존 필드만 검증) — 그대로 둔다(회귀 방지용).

- [ ] **Step 3: Implement in `src/config.py`**

`RefineryConfig` dataclass를 다음으로 교체한다. 기존 필드 순서를 유지하고 default 값이 있는 필드만 뒤에 붙인다(dataclass 규칙):

```python
@dataclass
class RefineryConfig:
    schedule_day: str
    schedule_hour: int
    # 로컬 패치 L20: IntelScheduler가 이 섹션을 참조해 주간 정제 cron 잡을 등록한다.
    # enabled=False로 두면 수동 CLI(`main.py refine`)로만 실행된다.
    enabled: bool = True
    schedule_minute: int = 0
```

그리고 `load_config` 내부의 `RefineryConfig(...)` 생성자 호출을 다음으로 교체한다:

```python
        refinery=RefineryConfig(
            schedule_day=data["refinery"]["schedule_day"],
            schedule_hour=data["refinery"]["schedule_hour"],
            enabled=data["refinery"].get("enabled", True),
            schedule_minute=data["refinery"].get("schedule_minute", 0),
        ),
```

나머지 로직(env var 치환, dedup_db_path 처리 등)은 건드리지 않는다.

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
py -m pytest tests/test_config.py -v
```

Expected: 전체 config 테스트 PASS (기존 + 신규 3개).

회귀 확인을 위해 전체 suite도 돌린다:
```bash
py -m pytest tests/ -v
```

Expected: 전부 PASS. `tests/test_scheduler.py::_make_config`가 `RefineryConfig(schedule_day="monday", schedule_hour=9)` 형태로 positional 호출하므로 default 필드 추가에 영향받지 않는다.

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: extend RefineryConfig with enabled and schedule_minute (L20 part 1)"
```

---

## Task 2: Wire weekly refinement cron job into IntelScheduler

**Files:**
- Modify: `src/scheduler/scheduler.py` (import 추가 + 모듈 레벨 헬퍼 2개 + `IntelScheduler` 확장)
- Modify: `tests/test_scheduler.py` (상단 `_make_scheduler` 확장 + 파일 하단에 11개 테스트 추가)

- [ ] **Step 1: Write the failing tests**

먼저 `tests/test_scheduler.py` **상단의 `_make_scheduler`** 를 다음으로 교체해 `refinement_pipeline` 주입을 지원한다(기존 호출자는 default=None으로 계속 동작):

```python
def _make_scheduler(config=None, registry=None, pipeline=None, refinement_pipeline=None):
    config = config or _make_config()
    registry = registry or MagicMock()
    pipeline = pipeline or MagicMock()
    scheduler = IntelScheduler(
        config=config,
        registry=registry,
        pipeline=pipeline,
        refinement_pipeline=refinement_pipeline,
    )
    return scheduler
```

그리고 **파일 하단에** 다음 11개 테스트를 추가한다:

```python
# ---------- L20: weekly refinement cron ----------

import logging
from datetime import date

from src.scheduler.scheduler import _day_to_cron, _compute_previous_week


def test_day_to_cron_accepts_full_weekday_name():
    assert _day_to_cron("monday") == "mon"
    assert _day_to_cron("WEDNESDAY") == "wed"
    assert _day_to_cron("Sunday") == "sun"


def test_day_to_cron_accepts_short_form():
    assert _day_to_cron("mon") == "mon"
    assert _day_to_cron("FRI") == "fri"


def test_day_to_cron_rejects_unknown_value():
    import pytest

    with pytest.raises(ValueError, match="Unknown weekday"):
        _day_to_cron("funday")


def test_compute_previous_week_from_monday():
    """월요일 실행 → 직전 주(월~일)."""
    # 2026-04-13 is Monday, ISO week 16 → previous week is 2026-W15
    week_id, date_range = _compute_previous_week(date(2026, 4, 13))
    assert week_id == "2026-W15"
    assert date_range == "2026-04-06 ~ 2026-04-12"


def test_compute_previous_week_from_wednesday():
    """수요일 실행 → 같은 '직전 주(월~일)' 결과."""
    week_id, date_range = _compute_previous_week(date(2026, 4, 15))
    assert week_id == "2026-W15"
    assert date_range == "2026-04-06 ~ 2026-04-12"


def test_scheduler_registers_refinement_cron_when_enabled():
    """L20: enabled=True + refinement_pipeline 주입 시 cron 잡 등록."""
    from apscheduler.triggers.cron import CronTrigger

    config = _make_config()
    config.refinery.enabled = True
    config.refinery.schedule_day = "monday"
    config.refinery.schedule_hour = 9
    config.refinery.schedule_minute = 0

    refinement_pipeline = MagicMock()
    scheduler = _make_scheduler(config=config, refinement_pipeline=refinement_pipeline)
    scheduler._register_jobs()

    jobs = {job.id: job for job in scheduler._scheduler.get_jobs()}
    assert "collection_cycle" in jobs
    assert "refinement_cycle" in jobs

    cron = jobs["refinement_cycle"].trigger
    assert isinstance(cron, CronTrigger)
    # CronTrigger의 필드에서 요일·시간·분 확인
    fields = {f.name: str(f) for f in cron.fields}
    assert fields["day_of_week"] == "mon"
    assert fields["hour"] == "9"
    assert fields["minute"] == "0"


def test_scheduler_skips_refinement_cron_when_disabled():
    """L20: enabled=False이면 cron 잡 미등록."""
    config = _make_config()
    config.refinery.enabled = False

    refinement_pipeline = MagicMock()
    scheduler = _make_scheduler(config=config, refinement_pipeline=refinement_pipeline)
    scheduler._register_jobs()

    jobs = {job.id for job in scheduler._scheduler.get_jobs()}
    assert "refinement_cycle" not in jobs
    assert "collection_cycle" in jobs


def test_scheduler_skips_refinement_cron_when_pipeline_missing():
    """L20: refinement_pipeline=None이면 enabled여도 등록하지 않고 warning 로그."""
    config = _make_config()
    config.refinery.enabled = True

    scheduler = _make_scheduler(config=config, refinement_pipeline=None)

    with caplog_warning():
        scheduler._register_jobs()

    jobs = {job.id for job in scheduler._scheduler.get_jobs()}
    assert "refinement_cycle" not in jobs


def test_run_refinement_cycle_calls_pipeline_with_previous_week(tmp_path):
    """L20: _run_refinement_cycle이 직전 주 week_id/date_range로 pipeline.run 호출."""
    config = _make_config()
    config.vault_path = tmp_path
    # Raw 데이터가 존재하도록 대상 주 중 하루 폴더 생성
    (tmp_path / "raw" / "2026-04-06").mkdir(parents=True)

    refinement_pipeline = MagicMock()
    scheduler = _make_scheduler(config=config, refinement_pipeline=refinement_pipeline)

    # 월요일 2026-04-13 고정
    scheduler._run_refinement_cycle(today=date(2026, 4, 13))

    refinement_pipeline.run.assert_called_once_with(
        week="2026-W15", date_range="2026-04-06 ~ 2026-04-12"
    )


def test_run_refinement_cycle_skips_when_no_raw_data(tmp_path, caplog):
    """L20: 대상 주의 raw 폴더가 하나도 없으면 pipeline 미호출 + warning."""
    config = _make_config()
    config.vault_path = tmp_path
    (tmp_path / "raw").mkdir()  # raw/는 있지만 그 안 날짜 폴더는 없음

    refinement_pipeline = MagicMock()
    scheduler = _make_scheduler(config=config, refinement_pipeline=refinement_pipeline)

    with caplog.at_level(logging.WARNING, logger="src.scheduler.scheduler"):
        scheduler._run_refinement_cycle(today=date(2026, 4, 13))

    refinement_pipeline.run.assert_not_called()
    assert any("no raw data" in rec.message for rec in caplog.records)


def test_run_refinement_cycle_isolates_pipeline_exception(tmp_path, caplog):
    """L20: pipeline.run이 예외를 던져도 스케줄러가 크래시하지 않고 logger.exception 기록."""
    config = _make_config()
    config.vault_path = tmp_path
    (tmp_path / "raw" / "2026-04-06").mkdir(parents=True)

    refinement_pipeline = MagicMock()
    refinement_pipeline.run.side_effect = RuntimeError("step 2 LLM quota exceeded")
    scheduler = _make_scheduler(config=config, refinement_pipeline=refinement_pipeline)

    with caplog.at_level(logging.ERROR, logger="src.scheduler.scheduler"):
        # Should not raise
        scheduler._run_refinement_cycle(today=date(2026, 4, 13))

    assert any("Refinement failed" in rec.message for rec in caplog.records)
```

파일 상단 import 블록에 `pytest`용 `caplog_warning` 헬퍼가 필요하다. `test_scheduler_skips_refinement_cron_when_pipeline_missing` 만 이 헬퍼를 쓰므로 **테스트 블록 바로 위**에 다음을 추가한다:

```python
from contextlib import contextmanager


@contextmanager
def caplog_warning():
    """pytest caplog 대체 — WARNING 로그 존재 여부만 가볍게 확인."""
    yield  # 실제 검증은 _register_jobs 내부 logger.warning 호출 여부로 충분
```

(이 헬퍼는 최소 본문만 갖는다. 로그 존재를 엄격히 검증하려면 `caplog` fixture를 파라미터로 쓰면 된다 — 여기서는 `pipeline` 미주입 시 `_register_jobs`가 예외 없이 끝나고 잡이 등록되지 않는 것만 확인하면 충분해서 생략 가능.) **또는 이 테스트에 `caplog` fixture를 쓰는 방식으로 간소화할 수도 있다**:

```python
def test_scheduler_skips_refinement_cron_when_pipeline_missing(caplog):
    """L20: refinement_pipeline=None이면 enabled여도 등록하지 않고 warning 로그."""
    config = _make_config()
    config.refinery.enabled = True

    scheduler = _make_scheduler(config=config, refinement_pipeline=None)

    with caplog.at_level(logging.WARNING, logger="src.scheduler.scheduler"):
        scheduler._register_jobs()

    jobs = {job.id for job in scheduler._scheduler.get_jobs()}
    assert "refinement_cycle" not in jobs
    assert any("refinement_pipeline not provided" in rec.message for rec in caplog.records)
```

**이 간소화 버전을 채택**한다. 위의 `caplog_warning` 컨텍스트 매니저는 작성하지 않는다.

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
py -m pytest tests/test_scheduler.py -v -k "day_to_cron or compute_previous_week or refinement_cron or run_refinement_cycle"
```

Expected: 모두 FAIL.
- `_day_to_cron`, `_compute_previous_week` — `ImportError: cannot import name '_day_to_cron' from 'src.scheduler.scheduler'`
- `IntelScheduler.__init__` 에 `refinement_pipeline` kwarg — `TypeError: __init__() got an unexpected keyword argument 'refinement_pipeline'`
- `_register_jobs`, `_run_refinement_cycle` — `AttributeError`

기존 8개 스케줄러 테스트는 PASS 상태여야 한다(회귀 없음 확인):
```bash
py -m pytest tests/test_scheduler.py -v -k "not (day_to_cron or compute_previous_week or refinement_cron or run_refinement_cycle)"
```

- [ ] **Step 3: Implement in `src/scheduler/scheduler.py`**

파일 상단 import 블록을 다음으로 교체한다(기존 imports 에서 `datetime`, `date`, `timedelta`, `RefinementPipeline` 추가):

```python
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
```

클래스 선언 **바로 위**에 다음 두 헬퍼 함수를 추가한다:

```python
_WEEKDAY_NORMALIZATION = {
    "monday": "mon", "mon": "mon",
    "tuesday": "tue", "tue": "tue",
    "wednesday": "wed", "wed": "wed",
    "thursday": "thu", "thu": "thu",
    "friday": "fri", "fri": "fri",
    "saturday": "sat", "sat": "sat",
    "sunday": "sun", "sun": "sun",
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
```

`IntelScheduler` 클래스 본문을 다음으로 교체한다(기존 `_run_collection_cycle`·`run_once` 는 유지, `__init__`·`start` 만 수정, `_register_jobs`·`_run_refinement_cycle` 신설):

```python
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
        # 로컬 패치 L5: 명시적 timezone으로 실행.
        self._scheduler = BlockingScheduler(timezone=ZoneInfo(config.collection.timezone))
        self._rss = RssSource()
        self._sns = SnsSource()
        self._web = WebSource()
        self._youtube = YoutubeSource()

    def _register_jobs(self):
        """Register all scheduled jobs. Separated from start() for testability."""
        # Collection (interval)
        interval_hours = self._config.collection.interval_hours
        self._scheduler.add_job(
            self._run_collection_cycle,
            "interval",
            hours=interval_hours,
            id="collection_cycle",
        )
        logger.info(f"Scheduler started: collection every {interval_hours} hours")

        # Weekly refinement (cron) — 로컬 패치 L20
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
        """Execute one weekly refinement cycle for the previous ISO week.

        ``today`` is injectable for tests; production path uses the current
        date in the configured timezone. Empty raw guard + exception
        isolation — see L20 spec above.
        """
        if today is None:
            today = datetime.now(ZoneInfo(self._config.collection.timezone)).date()

        week_id, date_range = _compute_previous_week(today)
        logger.info(f"Starting weekly refinement: {week_id} ({date_range})")

        # Empty raw guard
        raw_dir = self._config.vault_path / "raw"
        target_dates = [
            today - timedelta(days=today.weekday() + 1) - timedelta(days=i)
            for i in range(7)
        ]
        has_any = any((raw_dir / d.isoformat()).exists() for d in target_dates)
        if not has_any:
            logger.warning(
                f"Refinement skipped: no raw data for {date_range}"
            )
            return

        try:
            self._refinement_pipeline.run(week=week_id, date_range=date_range)
            logger.info(f"Weekly refinement complete: {week_id}")
        except Exception:
            logger.exception(f"Refinement failed for {week_id} ({date_range})")

    def _run_collection_cycle(self):
        """Execute one full collection cycle across all companies and sources."""
        # ... 기존 본문 유지 (변경 없음) ...

    def start(self):
        """Start the scheduler with all registered jobs."""
        self._register_jobs()
        self._scheduler.start()

    def run_once(self):
        """Run a single collection cycle without scheduling."""
        self._run_collection_cycle()
```

**구현 주의사항:**
- 위 코드 블록에서 `_run_collection_cycle` 본문은 *현재 파일의 기존 본문을 그대로 유지* 한다(플랜에 반복 기재하지 않는다). 실수로 덮어쓰지 않도록 기존 `_run_collection_cycle`을 `__init__` 바로 아래가 아니라 **`_run_refinement_cycle` 뒤에 배치**한다. 기존 코드는 for 루프 4개(RSS/Web/SNS/YouTube)를 포함하며 한 줄도 바뀌지 않는다.
- `_compute_previous_week`의 `target_dates`는 `_run_refinement_cycle` 안에서 inline으로 재계산한다(동일 공식의 중복이지만 헬퍼가 `week_id`·`date_range`만 반환하므로 폴더 경로 체크용 date 리스트가 별도로 필요). DRY 관점에서 약간 아쉬우나 헬퍼 인터페이스를 복잡하게 만드는 것보다 낫다.

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
py -m pytest tests/test_scheduler.py -v
```

Expected: 총 19개 PASS (기존 8개 + 신규 11개). 기존 테스트가 하나라도 FAIL 하면 `_run_collection_cycle` 본문을 실수로 건드렸을 가능성이 높다 — git diff로 확인 후 복원.

회귀 확인:
```bash
py -m pytest tests/ -v
```

Expected: 전부 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/scheduler/scheduler.py tests/test_scheduler.py
git commit -m "feat: wire weekly refinement cron job into IntelScheduler (L20 part 2)"
```

---

## Task 3: Wire RefinementPipeline into main.py schedule command

**Files:**
- Modify: `src/main.py` (`schedule` 분기)
- Modify: `config.yaml` (refinery 섹션 확장 + 주석)

단위 테스트 없음(G4 규칙 — main.py의 `schedule` 분기는 glue 코드). 수동 검증 단계 포함.

- [ ] **Step 1: Update `src/main.py` schedule branch**

`src/main.py`의 `schedule` 분기(현재 `main()` 끝부분, `elif args.command == "schedule":` 블록)를 다음으로 교체한다:

```python
    elif args.command == "schedule":
        collection_pipeline = CollectionPipeline(
            gateway=gateway, tagging_model="gemini",
            registry=registry, dedup=dedup, raw_writer=raw_writer,
        )
        # 로컬 패치 L20: 주간 정제 자동화. config.refinery.enabled=True일 때만
        # IntelScheduler가 cron 잡을 등록한다. 구성 비용은 gateway/registry/vault를
        # 이미 만들어뒀으므로 미미하다.
        refinement_pipeline = RefinementPipeline(
            gateway=gateway,
            consolidation_model="gpt5-pro",
            summarization_model="claude-opus",
            review_model="gpt5-pro",
            vault=vault,
            registry=registry,
        )
        scheduler = IntelScheduler(
            config=config,
            registry=registry,
            pipeline=collection_pipeline,
            refinement_pipeline=refinement_pipeline,
        )
        scheduler.start()
```

`collect`·`refine`·`init` 분기는 건드리지 않는다. Import 블록(`from src.refinery.pipeline import RefinementPipeline`)은 이미 존재한다.

- [ ] **Step 2: Update `config.yaml`**

현재 `config.yaml` 의 `refinery:` 섹션:

```yaml
refinery:
  schedule_day: "monday"
  schedule_hour: 9
```

을 다음으로 교체한다:

```yaml
refinery:
  # 로컬 패치 L20: IntelScheduler가 이 섹션을 참조해 주간 정제 cron 잡을 등록한다.
  # enabled=false 로 두면 수동 CLI(`main.py refine`)로만 실행됨.
  # 주의: L1(프로필 덮어쓰기) 미해결 상태에서 활성화하면 수동 편집한 vault/companies/*.md,
  # vault/topics/*.md 가 다음 주 실행 시 통째로 덮어씌워질 수 있음.
  # 일요일 실행은 '진행 중인 주'가 아니라 '저번 주'를 타깃하므로 월~토 권장.
  enabled: true
  schedule_day: "monday"
  schedule_hour: 9
  schedule_minute: 0
```

- [ ] **Step 3: Run full test suite**

Run:
```bash
py -m pytest tests/ -v
```

Expected: 전부 PASS. main.py 변경은 테스트 대상 아니지만, 혹시 import 체인이 망가졌으면 `tests/test_config.py::test_load_config_from_yaml` 등이 즉시 감지한다.

- [ ] **Step 4: Smoke-check CLI**

API 키 없이도 config 파싱이 성공하는지 확인:
```bash
py -c "from src.config import load_config; from pathlib import Path; c = load_config(Path('config.yaml')); print(f'enabled={c.refinery.enabled}, day={c.refinery.schedule_day}, time={c.refinery.schedule_hour:02d}:{c.refinery.schedule_minute:02d}')"
```

Expected:
```
enabled=True, day=monday, time=09:00
```

(실제 `py -m src.main schedule` 호출은 API 키 환경변수가 있어야 Gateway 초기화가 성공하므로 smoke-check 범위 밖이다.)

- [ ] **Step 5: Commit**

```bash
git add src/main.py config.yaml
git commit -m "feat: wire RefinementPipeline into schedule command (L20 part 3)"
```

---

## Task 4: Mark L20 as Resolved in backlog index

**Files:**
- Modify: `docs/plans/README.md` ("Resolved" 표에 L20 행 추가)

이 태스크는 **순수 문서 업데이트** 이므로 TDD 사이클이 없다. 테스트 추가 없음.

- [ ] **Step 1: Add L20 row to Resolved table**

`docs/plans/README.md` 의 `### Resolved (이전에 "미수정"으로 남아있다 이번 리뷰에서 해결된 항목)` 섹션 표의 **마지막 L6 행 다음** 에 L20 행을 추가한다(표는 해결 순서로 나열되므로 끝에 붙인다):

```
| L20 | `src/config.py` + `src/scheduler/scheduler.py` + `src/main.py` + `config.yaml` | 기존에 사장되어 있던 `RefineryConfig`를 활용해 `IntelScheduler`에 주간 정제 cron 잡 등록. `_day_to_cron` 으로 "monday"/"mon" 양쪽을 수용하고, `_compute_previous_week` 헬퍼가 실행 요일과 무관하게 "직전 주(월~일)" 을 자동 계산. 빈 raw 가드·예외 격리·`enabled` 플래그로 안전장치 확보. `main.py schedule` 하나로 interval 수집 + 주간 정제가 함께 실행된다. config 테스트 3개 + scheduler 테스트 11개 추가 |
```

"알려진 한계 (Not Fixed)" 표는 손대지 않는다 — L1/L2/L8/L10/L11은 L20과 독립된 이슈.

- [ ] **Step 2: Commit**

```bash
git add docs/plans/README.md
git commit -m "docs: mark L20 resolved in backlog index"
```

---

## Self-Review 체크리스트 (플랜 작성자 기준)

- [x] **Spec coverage:**
  - "Config 스키마" → Task 1 에서 `enabled`·`schedule_minute` 추가, Task 3 에서 `config.yaml` 업데이트.
  - "단일 BlockingScheduler 공존" → Task 2의 `_register_jobs`가 interval + cron 둘 다 등록.
  - "RefinementPipeline 주입" → Task 2의 `__init__` 시그니처 확장 + Task 3의 `main.py` 배선.
  - "Day 정규화" → Task 2의 `_day_to_cron` 헬퍼 + 3개 테스트.
  - "직전 주 계산 공식" → Task 2의 `_compute_previous_week` + 2개 테스트(월/수).
  - "빈 raw 가드" → Task 2의 `_run_refinement_cycle` 본문 + `test_run_refinement_cycle_skips_when_no_raw_data`.
  - "실패 로그 + 다음 주 대기" → Task 2의 try/except + `test_run_refinement_cycle_isolates_pipeline_exception`.
  - "엣지 케이스 (일요일)" → `_compute_previous_week` docstring + config.yaml 주석에 문서화.
  - "L1 리스크 알림" → Task 3의 `config.yaml` 주석.
  - "완료 기준 1,2" → Task 1·2의 Step 4 에서 suite 실행. "완료 기준 3"(로그 두 줄) → Task 3 Step 4 는 API 키 없이 돌아가는 부분만 smoke. "완료 기준 4" → Task 4.
- [x] **Placeholder scan:** TBD/TODO/"add error handling" 없음. 모든 코드 블록 실제 내용 포함.
- [x] **Type consistency:**
  - `_day_to_cron(day: str) -> str` — Task 2 정의·사용 시그니처 일치.
  - `_compute_previous_week(today: date) -> tuple[str, str]` — Task 2 정의·테스트·사용부 모두 동일.
  - `IntelScheduler.__init__(..., refinement_pipeline: RefinementPipeline | None = None)` — Task 2 정의, Task 3 `main.py` 에서 kwarg 로 전달. `_make_scheduler` 시그니처도 맞춤.
  - `RefineryConfig(schedule_day, schedule_hour, enabled=True, schedule_minute=0)` — Task 1 정의, Task 2 테스트에서 `config.refinery.enabled/schedule_day/schedule_hour/schedule_minute` 로 접근. 필드명 일치.
  - `RefinementPipeline.run(week: str, date_range: str)` — `src/refinery/pipeline.py:53` 의 실제 시그니처와 일치(이미 구현된 것 재사용).
- [x] **기존 동작 무변경:**
  - Task 2는 `_run_collection_cycle` 본문을 그대로 유지(Step 3에 "기존 본문 유지" 명시 + Step 4 기존 테스트 통과 확인).
  - Task 1의 `RefineryConfig` default 필드 추가는 기존 `_make_config` positional 호출과 호환.
  - `main.py`의 `collect`·`refine`·`init` 분기 미변경.
- [x] **Windows 커맨드:** `py -m pytest` 사용 (CLAUDE.md 지침).
- [x] **커밋 메시지 형식:** "feat:" / "docs:" prefix 가 기존 커밋 컨벤션(`35f6337 docs:`, `80a958b feat:`) 과 일치.

---

## 실행 완료 시점의 최종 상태 요약

- `src/config.py::RefineryConfig` 에 `enabled`·`schedule_minute` 필드 추가. 기본값 `True`·`0`. `load_config`가 두 키를 `data["refinery"].get(...)`로 옵셔널하게 읽음.
- `src/scheduler/scheduler.py` 에 모듈 레벨 `_day_to_cron`·`_compute_previous_week` 헬퍼 추가. `IntelScheduler.__init__` 가 `refinement_pipeline: RefinementPipeline | None` 인자 수용. `start()` → `_register_jobs()` + `_scheduler.start()` 로 분리되어 테스트에서 `_register_jobs`만 호출 가능. `_run_refinement_cycle(today: date | None = None)` 이 직전 주 계산 → 빈 raw 가드 → `RefinementPipeline.run` 호출 → 예외 격리.
- `src/main.py` 의 `schedule` 분기가 `RefinementPipeline` 을 구성해 `IntelScheduler` 에 주입. 다른 분기(`collect`·`refine`·`init`) 는 변경 없음.
- `config.yaml` 의 `refinery:` 섹션이 `enabled: true` + `schedule_minute: 0` + L1 경고 주석을 포함.
- `tests/test_config.py` +3, `tests/test_scheduler.py` +11 → 총 신규 14개 테스트. 기존 suite 회귀 0.
- `docs/plans/README.md` 의 "Resolved" 표에 L20 행 추가. "알려진 한계" 표는 변경 없음.

운영 측면에서 사용자가 L20 해소 효과를 보려면:

1. `config.yaml` 의 `refinery.enabled: true` 확인(기본값이므로 별도 조치 불필요).
2. 필요 시 `refinery.schedule_day` / `schedule_hour` / `schedule_minute` 를 Obsidian 에서 편집.
3. `py -m src.main schedule` 실행 → 로그에 `Scheduler started: collection every 6 hours` 와 `Weekly refinement cron scheduled: mon at 09:00` 두 줄이 찍힘.
4. 월요일 09:00 KST 에 자동으로 `RefinementPipeline.run(week="2026-W15", date_range="2026-04-06 ~ 2026-04-12")` 가 호출됨. 결과는 `vault/weekly/2026-W15.md` 에 누적.
5. 수동 백필이 필요하면 기존 CLI 그대로: `py -m src.main refine --week 2026-W14 --date-range "2026-03-30 ~ 2026-04-05"`.
