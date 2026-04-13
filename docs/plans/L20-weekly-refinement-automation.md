# L20 — Weekly Refinement 자동 스케줄링 설계 스펙

> **문서 성격:** 설계 스펙(brainstorming 산출물). 실행 가능한 Task 단위 플랜은 이 파일 아래에 `writing-plans` 스킬이 이어서 작성합니다. 현 시점에서는 "무엇을 왜 만드는가" 까지의 합의 기록입니다.

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
