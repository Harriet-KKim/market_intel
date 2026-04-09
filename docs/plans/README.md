# Market Intelligence System — 모듈별 구현 플랜 인덱스

이 폴더는 [원본 통합 플랜](../superpowers/plans/2026-04-09-market-intel-implementation.md)(18개 태스크, 6개 페이즈)을 **모듈 단위로 분할**한 결과물입니다. 각 파일은 독립적으로 읽고 실행할 수 있도록 태스크 정의·실패 테스트·구현 코드·커밋 명령을 모두 포함합니다.

> ⚠️ **이 분할본은 원본 플랜의 알려진 버그·모호성에 대해 로컬 패치가 적용되어 있습니다.** 원본 통합본과 drift가 있으며, **분할본이 더 실행 가능한 상태**입니다. 개발은 분할본을 정본으로 진행하세요. 패치 내역은 아래 [적용된 로컬 패치](#적용된-로컬-패치) 참조.

- 원본 통합본(참고): [`../superpowers/plans/2026-04-09-market-intel-implementation.md`](../superpowers/plans/2026-04-09-market-intel-implementation.md)
- 설계 스펙: [`../superpowers/specs/2026-04-09-market-intel-system-design.md`](../superpowers/specs/2026-04-09-market-intel-system-design.md)

---

## 목표 요약

- **대상:** Physical AI (로보틱스, 자율주행, 월드모델, Embodied AI) 시장 정보의 일상적 자동 수집·주간 정제
- **아키텍처:** 파이썬 스크립트 파이프라인 + 경량 LLM Gateway (에이전트 프레임워크 사용 안 함)
- **두 개의 파이프라인:**
  - **Collection Pipeline** — 소스별 수집 → URL dedup → LLM 태깅 → Obsidian Vault `raw/{date}/` 기록
  - **Weekly Refinement Pipeline** — GPT5 Pro 통합 → Claude Opus 요약 → GPT5 Pro 검토(Context Branching)
- **스토리지:** Obsidian Vault (Markdown + Frontmatter + `[[WikiLinks]]`)

---

## 의존 순서 / 구현 순서

`01` → `10` 순서로 구현하면 의존성 충돌 없이 TDD 루프를 돌릴 수 있습니다.

| # | 파일 | 모듈 | 역할 | 포함 태스크 |
|---|------|------|------|--------------|
| 01 | [01-config.md](./01-config.md) | `src/config.py` + `config.yaml` + `pyproject.toml` | 프로젝트 셋업 / 설정 로더 / env 치환 | Task 1 |
| 02 | [02-registry.md](./02-registry.md) | `src/registry.py` | 회사 / 키워드 / 소스 평판 레지스트리 + 텍스트 매칭 | Task 2 |
| 03 | [03-dedup.md](./03-dedup.md) | `src/dedup.py` | SQLite 기반 URL dedup | Task 3 |
| 04 | [04-gateway.md](./04-gateway.md) | `src/gateway/` | LLM Gateway + 3종 어댑터 + **Session / Checkpoint** (Context Branching의 핵심) | Task 4–6 |
| 05 | [05-writer.md](./05-writer.md) | `src/writer/` | Frontmatter · WikiLink · VaultManager · Raw / Profile / Weekly Writer | Task 7–9 |
| 06 | [06-sources.md](./06-sources.md) | `src/sources/` | 플러그인 소스 (base, rss, web, sns, youtube) | Task 10–12 |
| 07 | [07-collector.md](./07-collector.md) | `src/collector/` | 수집 파이프라인 오케스트레이터 (dedup + tagging + write) | Task 13 |
| 08 | [08-scheduler.md](./08-scheduler.md) | `src/scheduler/` | APScheduler 기반 주기 수집 트리거 | Task 14 |
| 09 | [09-refinery.md](./09-refinery.md) | `src/refinery/` | Consolidator / Summarizer / Reviewer / Refinement Pipeline | Task 15–17 |
| 10 | [10-main.md](./10-main.md) | `src/main.py` | CLI 진입점 (`collect`, `refine`, `schedule`, `init`) | Task 18 |

---

## 페이즈 맵핑

| Phase | 파일 | 설명 |
|-------|------|------|
| **1. Foundation** | 01·02·03 | 설정, Registry, URL dedup — 외부 의존 없음 |
| **2. LLM Gateway** | 04 | 모든 LLM 호출의 단일 진입점. Session/Checkpoint는 Refinement의 전제 |
| **3. Obsidian Writer** | 05 | Vault 구조 + Frontmatter/WikiLink + Raw/Profile/Weekly Writer |
| **4. Collection Pipeline** | 06·07·08 | 소스 플러그인 → Collector → Scheduler |
| **5. Weekly Refinement** | 09 | 3-step 멀티모델 파이프라인 (Context Branching 사용) |
| **6. Integration** | 10 | CLI 진입점, Vault init, 어댑터 배선 |

---

## 공용 컨벤션

모든 모듈이 공유하는 규약. 태스크 중간에 새로 사용되는 값이 나오면 여기를 먼저 확인하세요.

### 환경 변수
런타임에 `config.yaml`의 `${VAR}` 치환에 사용됩니다.

| 변수 | 용도 | 필요 시점 |
|------|------|-----------|
| `GEMINI_API_KEY` | Collection tagging | Task 13 이후 실제 실행 시 |
| `OPENAI_API_KEY` | Weekly Consolidator + Reviewer (GPT5 Pro) | Task 15, 17 이후 실제 실행 시 |
| `ANTHROPIC_API_KEY` | Weekly Summarizer (Claude Opus) | Task 16 이후 실제 실행 시 |

테스트는 전부 Mock adapter 기반이므로 실제 키 없이도 `pytest`가 통과해야 합니다.

### 설치 / 테스트 커맨드
Task 1(`01-config.md`) 완료 후부터 사용 가능:

```bash
pip install -e ".[dev]"                      # pyproject.toml 기반 개발 설치
pytest tests/ -v                             # 전체 테스트
pytest tests/test_config.py -v               # 단일 파일
pytest tests/test_config.py::test_name -v    # 단일 테스트
```

pytest config는 `pyproject.toml`에 인라인(`testpaths = ["tests"]`, `pythonpath = ["."]`). 테스트는 `from src.xxx import ...` 형태.

### 공용 테스트 fixture
- `sample_registry_dir` — `tests/conftest.py`에 정의. **Task 2(`02-registry.md`)에서 최초 생성**. Registry 기반 테스트는 전부 이 fixture에 의존합니다. 사용처: 02·05·07·09.
- `tmp_path` — pytest 기본 제공. Vault / SQLite DB 격리용.

---

## Load-bearing 설계 결정

다음 결정들은 스펙·플랜 전체를 관통하는 축이므로 **사전 논의 없이 뒤집지 마세요**. 뒤집는 순간 여러 모듈이 연쇄적으로 깨집니다.

- **하이브리드 아키텍처:** Python 스크립트 파이프라인 + 얇은 LLM Gateway. 에이전트 프레임워크 미사용.
- **역할 분담:** 스크립트 = fetch/parse/dedup/storage/schedule. LLM = tagging only (단, `WebSource`만 예외적으로 추출+태깅을 한 번에 수행 — HTML 구조가 소스마다 달라서).
- **URL-only dedup:** 내용 유사도 dedup은 정제 단계 LLM에게 위임. Dedup store는 SQLite (`src/dedup.py`).
- **WikiLinks로 참조 테이블 대체:** Raw 아티클에 `[[NVIDIA]]`를 인라인으로 삽입, Obsidian Backlinks가 역인덱스 역할. 별도 "mentions" 파일 없음.
- **Registry는 Vault 안에:** `vault/registry/companies.yaml`, `keywords.yaml`, `source_reputation.yaml`. 사용자가 Obsidian에서 바로 편집.
- **Source reputation 2-stage:** 수집 시 tier 기반 score 적용 (`tier_1=0.9` → `tier_4=0.3`), 주간 정제 단계에서 교차 검증·덮어쓰기 가능.
- **Context Branching (Refinement):** Step 1(Consolidator) 이후 Checkpoint 저장 → Step 3(Reviewer)는 **Step 2 continuation이 아니라 Step 1 checkpoint에서 branch**. 이게 Gateway `Session` 설계의 존재 이유입니다 (`04-gateway.md`).
- **No backfill / cold start:** 첫 실행 시점부터 누적. 과거 데이터 소급 수집 없음.
- **Budget tracking off by default:** `budget.enabled: true` 일 때만 경량 집계. 평소엔 프로바이더 대시보드에 의존.

---

## 작업 방식

- **TDD 원칙:** 각 태스크는 `실패하는 테스트 작성 → 실행(FAIL 확인) → 구현 → 실행(PASS 확인) → 커밋`. 한 태스크 = 한 커밋.
- **테스트 픽스처:** 모든 테스트가 `tests/conftest.py`의 `sample_registry_dir` fixture를 공용. Task 2에서 최초 생성.
- **Mock 우선:** Gateway / 외부 API는 테스트에서 `BaseAdapter` 서브클래스로 대체. 실제 API 호출은 `main.py`의 `setup_gateway()`에서만.
- **모듈 분할 원칙:** 분할된 각 파일은 원본의 해당 섹션을 출발점으로 삼되, **아래 "적용된 로컬 패치" 항목에 대해서만 선별적으로 수정**되어 있습니다. 원본과 drift가 있으며 **분할본이 정본**입니다. 원본을 직접 참조할 일이 있다면 반드시 이 README의 패치 목록을 먼저 확인하세요.

---

## 적용된 로컬 패치

원본 통합본에서 발견된 이슈들 중 **개발 실행을 차단하거나 애매함을 남기는** 항목에 대해 분할본에만 적용된 수정 내역. 각 항목은 해당 파일의 해당 위치에 인라인으로 표시되어 있습니다.

### Critical (실행 차단 — 반드시 수정됨)

| ID | 위치 | 문제 | 수정 |
|----|------|------|------|
| C1 | `01-config.md` Task 1 | `pyproject.toml`의 `build-backend`가 존재하지 않는 `setuptools.backends._legacy:_Backend`로 지정되어 `pip install -e .` 실패 | 공식 값 `setuptools.build_meta`로 교체 |
| C2 | `10-main.md` Task 18 | `main()`이 `init` 분기보다 먼저 `Registry(...)`를 호출 → Registry YAML 파일이 없는 최초 실행 시 `init` 커맨드 자체가 크래시 | init 분기를 앞으로 이동. `init_vault()`가 YAML 템플릿을 먼저 기록한 뒤 Registry를 로드하도록 재구조화 |
| C3 | `01-config.md` Task 1 | Task 1의 Files 목록에 `tests/conftest.py`가 포함돼 있으나 실제 `conftest.py` 생성은 Task 2(`02-registry.md`)에서 수행 → 중복·순서 혼란 | Task 1에서 `conftest.py` 항목 제거 |
| C4 | `10-main.md` Task 18 `REGISTRY_TEMPLATES` | `source_reputation.yaml` 템플릿이 `tier_1: 0.9` 형태의 평면 구조 → `Registry._load_reputation`가 기대하는 `{score, sources}` nested 스키마와 불일치. `init` 직후 첫 `collect`/`refine`이 `TypeError: 'float' object is not subscriptable`로 크래시 | 02-registry.md의 `test_get_reputation_score`와 동일한 nested 스키마로 템플릿 교체. 기본 tier별 소스 예시도 채워 사용자가 즉시 참고 가능 |

### Important (논리 결함·스펙 정합성 — 수정됨)

| ID | 위치 | 문제 | 수정 |
|----|------|------|------|
| I1 | `09-refinery.md` Task 17 | `Reviewer.run()`이 `Session.branch()` API를 우회해서 `session.history = list(checkpoint.history)`로 인라인 복원 → Context Branching 설계 의도를 코드가 따르지 않음 | `seed.branch(checkpoint)` 호출로 변경. Session 레이어가 일관되게 Checkpoint API를 사용하도록 정렬 |
| I2 | `04-gateway.md` Task 6 | Session/Checkpoint가 **client-side deepcopy** 기반임이 코드로만 암시됨 → 추후 adapter-native checkpoint와 혼동 가능 | 모듈 서두 "핵심 설계 포인트"에 "Checkpoint는 client-side deepcopy이며 provider native checkpoint API가 아니다"라는 주석 추가 |
| I3 | `10-main.md` Task 18 | `init` 커맨드가 Registry YAML 템플릿을 자동 생성하지 않아 사용자가 수동 작성 필요 → "최초 실행 후 init" UX와 불일치 | `REGISTRY_TEMPLATES` dict와 YAML 씨드 로직 추가. `init_vault()`는 ①YAML 템플릿 기록 → ②Registry 로드 → ③프로필 생성 순서로 동작 |
| I4 | `04-gateway.md` Task 6 + `09-refinery.md` Task 17 | Reviewer가 Step 1 Checkpoint에서 branch할 때 Consolidator의 system prompt("너는 통합자다")를 그대로 상속 → 역할이 재통합으로 편향될 위험. `Session.branch`에 system 교체 수단 없음 | `Session.branch(checkpoint, system_override=...)` 파라미터 신설(+ 테스트). Reviewer가 `REVIEWER_SYSTEM` 상수로 system만 교체하고 history(원본 raw 기억)는 보존 |
| I5 | `09-refinery.md` Task 15 `Consolidator._read_raw_data` | `date_range` 인자를 무시하고 `raw/` 전체를 스캔 → "2026-W15" 정제 호출이 과거 모든 날짜를 GPT5 Pro에 주입해 (a) 토큰 폭발, (b) 이전 주 정보가 이번 주 스냅샷 오염 | `_parse_date_range` staticmethod로 "YYYY-MM-DD ~ YYYY-MM-DD" 파싱 후 `date.fromisoformat`로 폴더 이름과 비교해 범위 필터. `test_consolidator_filters_raw_by_date_range` 테스트 신설 |
| P1 | `07-collector.md` Task 13 `CollectionPipeline.process_item` | raw 아티클의 `body`에 `[[WikiLink]]` 치환이 없어 frontmatter `companies` 필드 밖의 본문 언급이 Obsidian Backlinks 역인덱스에서 누락. "WikiLinks replace reference tables" 설계 결정(CLAUDE.md) 붕괴 | `inject_wikilinks(item.body, registry)`를 article dict 구성 전에 호출해 `linked_body`를 저장. `test_pipeline_processes_item`이 `parse_document`로 body를 분리 검증하도록 확장 |
| P2 | `06-sources.md` Task 12 `YoutubeSource.extract_transcript` | `yt-dlp --write-auto-sub --dump-json` 호출 결과를 그대로 반환 → 자막이 아닌 비디오 메타데이터 JSON이 transcript 자리에 들어감 | `subprocess.run`으로 `.vtt` 파일을 temp dir에 다운로드한 뒤 자체 구현 `_parse_vtt`로 cue 텍스트만 추출. `test_parse_vtt_extracts_cue_text` 유닛 테스트 신설 |

### Context Gaps (원본엔 없던 컨텍스트 — 분할본에 보강됨)

| ID | 위치 | 보강 내용 |
|----|------|-----------|
| G1 | README (이 파일) | **공용 컨벤션** 섹션: 환경 변수, 설치/테스트 커맨드, 공용 fixture 목록 |
| G2 | README (이 파일) | **Load-bearing 설계 결정** 섹션: 사전 논의 없이 뒤집으면 안 되는 아키텍처 축 |
| G3 | `05/07/09` | "선행 의존" 아래에 `공용 fixture:` 라인 추가 — 해당 태스크가 `sample_registry_dir`에 의존한다는 점을 명시 |
| G4 | `08/10` | "단위 테스트 없음이 의도된 이유"를 명시 (glue 코드는 통합 테스트 영역) |

### Resolved (이전에 "미수정"으로 남아있다 이번 리뷰에서 해결된 항목)

| ID | 위치 | 해결 방법 |
|----|------|-----------|
| K1 | `06-sources.md` Task 10 `RssSource.fetch_from_url` | `feed.feed.get("title")` → `urlparse(feed_url).netloc` → `feed_url` 순으로 폴백해 `source_name`을 설정. `test_rss_source_fallback_to_domain` 테스트 추가 |

### 알려진 한계 (Not Fixed — 구현·운영 중 주의)

다음 항목들은 "당장의 실행을 막진 않지만" 운영 단계에서 수면 위로 올라올 가능성이 있는 이슈입니다. 현 리뷰 사이클에서는 **의도적으로 손대지 않았고**, 실제로 문제가 관측될 때 패치 판단을 내리세요. ID는 `L#` 접두사로 구분합니다(Limit).

| ID | 위치 | 한계 | 관측 시 대응 |
|----|------|------|--------------|
| L1 | `09-refinery.md` Task 16 `Summarizer` + `ProfileWriter.update_company/update_topic` | Summarizer가 매 주 `company_updates[name]` 키에 **전체 본문 Markdown**을 내려보내고 ProfileWriter가 그대로 덮어씀 → 사용자가 Obsidian에서 수동 편집한 내용이 주간 실행마다 손실될 수 있음 | 섹션별 append/merge 전략으로 전환하거나, Summarizer에게 "기존 본문을 인자로 받고 부분 patch만 반환하라"는 스키마로 변경 |
| L2 | `09-refinery.md` Task 15 `Consolidator._read_raw_data` | 범위 필터는 적용되지만(I5) 필터 내부 raw는 여전히 **전량**이 단일 프롬프트로 전송 → raw 볼륨이 커지면 GPT5 Pro 토큰 한도 초과 | `max_chars_per_article` · `max_total_chars` 파라미터 추가, 또는 회사/주제별 사전 그룹핑 후 chunk 단위로 호출 |
| L3 | `10-main.md` `main()` | `UrlDedup(Path("dedup.db"))`가 CWD에 상대 경로로 고정 → 다른 디렉터리에서 `python -m src.main`을 실행하면 새 DB가 생성되어 dedup이 초기화 | `config.yaml`에 `dedup.db_path` 키 신설, 기본값을 `vault_path / ".dedup.db"` 등 절대 경로로 지정 |
| L4 | `05-writer.md` Task 8 `inject_wikilinks` | alias의 단어 경계 매칭이 정규식 수준으로 보장되지 않을 경우 다른 단어의 substring에 잘못 치환될 위험(예: alias "AI" → "AIR"에 매칭). 현 구현은 기본 문자열 교체 | 실제 오인 사례가 보이면 `re.escape` + `\b` 또는 유니코드 경계 + 케이스 민감 옵션으로 재작성 |
| L5 | `08-scheduler.md` Task 14 `IntelScheduler` | APScheduler `BlockingScheduler()`가 타임존 인자 없이 생성됨 → 컨테이너/서버의 시스템 TZ에 따라 실제 실행 시각이 달라짐 | 명시 TZ(`ZoneInfo("Asia/Seoul")` 등)를 `config.yaml`로 주입 |
| L6 | `08-scheduler.md` Task 14 YouTube 분기 | 현재는 `logger.info(f"YouTube channel check: {channel}")`만 찍고 실제 비디오 discovery 없음 — 스펙에도 "추후 확장"으로 기재 | 실제 필요해지면 yt-dlp `--flat-playlist` 또는 RSS(`feeds/videos.xml?channel_id=...`) 기반 discovery 구현 |
| L7 | `07-collector.md` Task 13 `CollectionPipeline.process_item` | `dedup.mark_seen` → `raw_writer.write` 사이에 크래시가 나면 URL은 seen으로 찍혔는데 파일은 없는 inconsistent state → 이후 재실행 시 영구 누락 | `raw_writer.write` 성공 이후에만 `mark_seen`을 호출하도록 순서 변경(중복 파일 허용) 또는 SQLite `BEGIN IMMEDIATE`로 두 동작을 트랜잭션화 |
| L8 | `09-refinery.md` Task 17 `RefinementPipeline.run` | 3-step 시퀀스 중 Step 3에서 실패하면 Step 1·2의 산출물은 이미 Vault에 기록된 상태로 전체 재실행이 필요 → 재시도 시 토큰 이중 소비 | `--resume-from` 플래그 또는 step별 idempotent skip 도입 |
| L9 | `02-registry.md` + `05-writer.md` `ProfileWriter` | 프로필 파일 이름이 `companies/{company.name}.md` 기반인 반면 태깅/매칭은 `company.id` 기반으로 흐름이 섞여 있음 → alias/id/name 트리플이 어긋나면 Summarizer의 `company_updates` 키와 실제 파일이 1:1로 매칭되지 않을 수 있음 | 현재는 `name` 문자열이 유일 식별자로 통일돼 있다는 전제이므로 괜찮지만, 다국어 alias가 실제 파일명으로 쓰이기 시작하면 `id → path` 역인덱스를 `ProfileWriter`에 추가 |
