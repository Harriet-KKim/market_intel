# Physical AI Market Intelligence System — Design Spec

## 1. 개요

### 1.1 목적
Physical AI 시장 조사 및 전략 분석을 위해 회사별 최신 정보를 자동 수집하고, 주기적으로 정제/요약하는 개인 리서치 워크플로우 시스템 구축.

### 1.2 범위
- Physical AI 전 범위: 로보틱스, 자율주행/모빌리티, 산업 자동화, Embodied AI 연구 (simulation, world models, spatial intelligence)
- 소규모 시작 → 30-50개사 확장
- 개인 리서치 용도 (Markdown/Obsidian 기반)

### 1.3 LLM-Wiki 개념 적용
Andrej Karpathy의 LLM-Wiki 중 다음을 부분 적용:
- **(B) 지속적 지식 축적 + 구조화된 문서 체계 + 점진적 정제**
- 새 정보가 들어올 때마다 기존 문서를 merge/update하여 지식이 정제되는 구조
- **(C) LLM-native 검색**은 확장 가능하도록 문서 구조만 대비, 초기에는 Obsidian Graph View/Backlinks로 대체

---

## 2. 시스템 아키텍처

### 2.1 전체 구조

```
┌──────────────────────────────────────────────────────────┐
│                    Obsidian Vault                         │
│  companies/ · topics/ · raw/ · weekly/ · registry/ · assets/ │
└────────────────────────┬─────────────────────────────────┘
                         │ 읽기/쓰기
┌────────────────────────▼─────────────────────────────────┐
│                  Obsidian Writer                          │
│  (Vault 파일 생성/업데이트/위키링크 처리 유틸)               │
└────────────────────────┬─────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────────┐
│  수집 파이프라인 │ │  주간 정제      │ │  비용 모니터링     │
│  (하루 미만)    │ │  (주간)        │ │  (제공사 대시보드) │
└──────┬───────┘ └──────┬───────┘ └──────────────────┘
       │                │
       ▼                ▼
┌──────────────────────────────────────────────────────────┐
│                    LLM Gateway                           │
│  Gemini (수집 태깅) · GPT5 Pro (통합/검토) · Claude Opus (요약) │
└──────────────────────────────────────────────────────────┘
```

### 2.2 핵심 컴포넌트

| 컴포넌트 | 역할 |
|----------|------|
| 수집 파이프라인 | 스케줄러 + 소스 모듈 + Agent 태깅 |
| 주간 정제 | 3-Step 멀티 모델 파이프라인 |
| LLM Gateway | 모델 종류에 무관한 통합 호출 인터페이스 |
| Obsidian Writer | Vault 파일 CRUD + 위키링크/frontmatter 처리 |

### 2.3 구현 접근법
하이브리드 — Script 기반 + LLM 호출만 경량 래핑.
- 수집/저장/스케줄링은 Python 스크립트
- LLM 호출 부분만 Gateway로 추상화
- Agent 프레임워크 미사용 (파이프라인이 직렬 흐름이므로 불필요)

---

## 3. 수집 파이프라인

### 3.1 아키텍처

하이브리드 (Source 모듈 + Company 스케줄러)

```
┌─────────────────────────────────┐
│     Company/Keyword Registry    │
│  (companies.yaml / keywords.yaml) │
└──────────────┬──────────────────┘
               │
       ┌───────▼───────┐
       │  스케줄러/Cron  │
       └───────┬───────┘
               │
   ┌─────┬─────┼─────┬──────┐
   ▼     ▼     ▼     ▼      ▼
[RSS] [웹페이지] [SNS] [YouTube] [...]
```

소스 모듈은 플러그인 구조로 설계하여 새 소스 추가 시 모듈 파일 생성 + config 등록만으로 확장 가능.

### 3.2 소스 유형별 Script / Agent 역할 분담

| 단계 | RSS / 구조화된 API | 웹 페이지 | SNS | YouTube |
|------|-------------------|----------|-----|---------|
| 데이터 가져오기 | Script (API 호출) | Script (HTTP fetch) | Script (API 호출) | Script (API + 자막) |
| 본문 추출 | Script (API 파싱) | **Agent** | Script (API 응답) | Script (자막) |
| 기본 메타데이터 | Script (필드 매핑) | **Agent** | Script (필드 매핑) | Script (필드 매핑) |
| 회사/키워드 태깅 | **Agent** | **Agent** | **Agent** | **Agent** |
| content_type | Script (소스 결정) | **Agent** | Script (소스 결정) | Script (소스 결정) |
| 외부 링크 판단 | — | — | **Agent** | — |
| Multimodal 분석 | — | — | — | **Agent** (선택적) |
| URL dedup | Script | Script | Script | Script |
| 저장 | Script | Script | Script | Script |

- 웹 페이지만 Agent가 전체 처리 (본문 추출 + 스키마 + 태깅을 한 번의 호출로)
- 나머지는 태깅만 Agent
- YouTube는 기본 Transcript 수집 + Agent가 "시각 분석 필요" 판단 시 키프레임 추출 → Multimodal 분석
- 수집 모델: 저비용 모델 (Gemini)

### 3.3 수집 데이터 스키마

```yaml
---
id: "article-xxxx"
title: "NVIDIA와 Boston Dynamics, world model 기반 로봇 플랫폼 공동 발표"
source:
  type: "news"           # news | paper | sns | official | github | blog | video
  name: "TechCrunch"
  url: "https://..."
  author: "John Doe"
collected_at: 2026-04-08T14:30:00Z
published_at: 2026-04-08T12:00:00Z
language: "en"
companies:
  - "[[NVIDIA]]"
  - "[[Boston Dynamics]]"
tags:
  - world-model
  - robot-control
reliability: null                    # 수집 시 source_reputation.yaml 기반 기본 점수 자동 부여, 주간 정제 시 교차 확인으로 보정
content_type: "article"              # article | abstract | thread | release | commit | post | demo
---

[[NVIDIA]]와 [[Boston Dynamics]]가 공동으로...
(본문 — 회사/주제 언급 시 위키링크 사용)
```

영상 소스 추가 필드:
```yaml
has_visual_analysis: true            # 키프레임 Multimodal 분석 수행 여부
source:
  type: "video"
  channel: "Figure"                  # YouTube 채널명
```

### 3.4 데이터 저장

원본 1회 저장 + Obsidian 위키링크 활용.

- 수집 원본은 `raw/{날짜}/` 에 1회만 저장
- 본문 내 `[[NVIDIA]]` 등 위키링크 → Obsidian Backlinks가 자동으로 회사 문서와 연결
- 별도 참조 링크 파일 불필요

### 3.5 중복 제거

URL 일치만 체크. 내용 기반 dedup은 분석 모델에 위임.

### 3.6 언어

구분 없음. 스키마에 `language` 기록만.

### 3.7 Cold Start

백필 없이 가동 시점부터 축적.

---

## 4. 검증

### 4.1 2단계 검증 구조

| 단계 | 방식 | 시점 |
|------|------|------|
| 소스 평판 스코어링 | `source_reputation.yaml` 기반 자동 점수 부여 | 수집 시 (Script) |
| 코퍼스 일치도 + 요약 시점 통합 검증 | 고급 모델이 주간 요약 시 여러 소스를 읽으며 교차 확인 + 신뢰도 판정 | 주간 요약 시 |

### 4.2 소스 평판 등급

```
tier_1 (0.9): Reuters, IEEE Spectrum, Nature, Science Robotics
tier_2 (0.7): TechCrunch, The Robot Report, 기업 공식 블로그
tier_3 (0.5): Reddit, HackerNews, 개인 블로그
tier_4 (0.3): X/Twitter, 출처 불명
```

### 4.3 Backlog

Claim 추출 + 교차 검증 파이프라인 — 정밀도 필요 시 추가.

---

## 5. 주간 정제 파이프라인

### 5.1 3-Step 멀티 모델 파이프라인 + Context Branching

```
┌─── GPT5 Pro 세션 (유지) ─────────────────────────┐
│                                                  │
│  Step 1: 통합본 생성                               │
│  Input:  raw/ 1주일치 + registry/                  │
│  Output: weekly/2026-W15-consolidated.md          │
│                                                  │
│  ★ Checkpoint (Context 분기점)                     │
│                                                  │
│          ┌──────────────────────────────┐         │
│          │  Step 2: 요약본 생성           │         │
│          │  Model: Claude Opus 4.6      │         │
│          │  Input:  통합본 + 기존 문서들   │         │
│          │  Output: 주간 스냅샷           │         │
│          │    + 회사/주제 문서 업데이트     │         │
│          └──────────────┬───────────────┘         │
│                         │                        │
│  Step 3: 내용 검토 (Checkpoint에서 Branch)         │
│  Input:  Claude의 output                          │
│  컨텍스트: Step 1에서 파악한 raw 데이터 기억         │
│  Output: 검토 코멘트                               │
│                                                  │
└──────────────────────────────────────────────────┘
```

### 5.2 Context Branching 전략

- Step 1 완료 시점을 Checkpoint로 저장
- 매 피드백 루프마다 Checkpoint에서 새 Branch 생성
- 각 Branch는 Step 1 컨텍스트 + 해당 회차 Claude output만 포함
- 이전 회차 피드백 이력이 누적되지 않아 컨텍스트 일정 유지

### 5.3 Step별 상세

**Step 1: 통합본 생성 (GPT5 Pro)**
- 흩어진 raw 데이터를 회사별/주제별로 정리
- 중복 내용 통합, 소스 평판 점수 반영
- 아직 요약이 아닌 구조화된 팩트 모음

**Step 2: 요약본 생성 (Claude Opus 4.6)**
- 전략적 관점에서 요약, 시사점 도출
- 코퍼스 일치도 기반 신뢰도 판정
- 기존 회사/주제 문서를 읽어서 merge/update
- Output: 주간 스냅샷 + 회사/주제 문서 업데이트

**Step 3: 내용 검토 (GPT5 Pro — 동일 세션)**
- Claude의 요약에서 누락/왜곡 확인
- Step 1에서 raw 데이터를 직접 읽은 컨텍스트 활용
- Output: 검토 코멘트

### 5.4 검토 피드백 처리

- **초기:** 검토 결과를 주간 스냅샷 하단에 코멘트로 남김, 본인이 판단
- **전환 후:** Step 2로 피드백 루프 (Context Branching 적용)

### 5.5 산출물

| 산출물 | 경로 | 성격 |
|--------|------|------|
| 통합본 | `weekly/2026-W15-consolidated.md` | Step 1 산출물, 원본 보존 |
| 주간 스냅샷 | `weekly/2026-W15.md` | Step 2 산출물, 최종 요약 |
| 검토 결과 | `weekly/2026-W15.md` 내 코멘트 | Step 3 피드백 |
| 회사 문서 업데이트 | `companies/{회사이름}.md` | Step 2에서 업데이트 |
| 주제 문서 업데이트 | `topics/{주제이름}.md` | Step 2에서 업데이트 |

---

## 6. Obsidian Vault 구조

### 6.1 폴더 구조

```
vault/
├── companies/
│   ├── NVIDIA.md
│   ├── Tesla.md
│   └── Boston Dynamics.md
├── topics/
│   ├── World Models.md
│   └── Humanoid Robot.md
├── raw/
│   └── 2026-04-08/
│       └── article-xxxx.md
├── weekly/
│   ├── 2026-W15-consolidated.md
│   └── 2026-W15.md
├── assets/
│   └── (키프레임 이미지 등)
└── registry/
    ├── companies.yaml
    ├── keywords.yaml
    └── source_reputation.yaml
```

### 6.2 회사 문서 템플릿 (`companies/{회사이름}.md`)

```markdown
---
aliases: ["NVIDIA", "엔비디아", "Jensen Huang"]
tags:
  - company
---

## 회사 개요
(사업 영역, 핵심 제품/플랫폼, Physical AI 관련 포지션)

## 최근 동향
(주간 정제 시 업데이트 — 최신순)

## 기술 스택
(보유 기술, 플랫폼, 주요 연구 방향)

## 파트너십 / 생태계
(협력 관계, 투자, M&A — [[Boston Dynamics]], [[Figure AI]] 등 위키링크)

## 전망 / 시사점
(전략적 의미, 개인 리서치 관점의 판단)

---

## 기타 노트
(고정 섹션에 맞지 않는 자유 형식 메모)
```

### 6.3 주제 문서 템플릿 (`topics/{주제이름}.md`)

```markdown
---
aliases: ["world model", "world models", "월드 모델"]
tags:
  - topic
---

## 개요
(이 기술/개념이 무엇인지, Physical AI에서의 의미)

## 주요 플레이어
(이 분야에서 활발한 회사/연구기관 — [[NVIDIA]], [[DeepMind]] 등 위키링크)

## 최근 동향
(주간 정제 시 업데이트)

## 핵심 논문 / 레퍼런스
(중요 논문, 발표, 데모 링크)

## 시사점
(기술 방향성, 전략적 의미)

---

## 기타 노트
```

### 6.4 주간 스냅샷 템플릿 (`weekly/2026-W15.md`)

```markdown
---
period: "2026-W15"
date_range: "2026-04-06 ~ 2026-04-12"
tags:
  - weekly
---

## 주요 하이라이트
(이번 주 가장 중요한 3-5개 이벤트 요약)

## 회사별 동향
### [[NVIDIA]]
- ...
### [[Figure AI]]
- ...

## 기술/트렌드별 동향
### [[World Models]]
- ...
### [[Humanoid Robot]]
- ...

## 신뢰도 이슈
(교차 확인 안 된 정보, 출처 불명확 정보 등 플래그)

## 시사점 / 관찰
(주간 종합 판단)
```

### 6.5 Obsidian 활용

- **Backlinks:** 수집 원본의 `[[NVIDIA]]` 위키링크 → NVIDIA.md에서 Backlinks로 자동 연결
- **Graph View:** 회사 ↔ 기술/트렌드 간 양방향 네트워크 자동 시각화
- **(C) 확장 대비:** 문서 구조가 인덱스 레이어 추가에 적합 (위키링크 + 태그 + frontmatter 메타데이터)

---

## 7. Registry

### 7.1 companies.yaml

```yaml
companies:
  - id: nvidia
    name: "NVIDIA"
    aliases: ["엔비디아", "Jensen Huang", "Cosmos", "Isaac", "GR00T"]
    sources:
      rss: ["https://blogs.nvidia.com/feed/"]
      youtube: ["@NVIDIA"]
      official: ["https://nvidianews.nvidia.com/"]
    topics: ["world-model", "sim-to-real", "gpu-computing"]
```

### 7.2 keywords.yaml

```yaml
keywords:
  - id: world-model
    name: "World Models"
    aliases: ["world model", "월드 모델", "world simulator"]
```

### 7.3 source_reputation.yaml

```yaml
tiers:
  tier_1:
    score: 0.9
    sources: ["Reuters", "IEEE Spectrum", "Nature"]
  tier_2:
    score: 0.7
    sources: ["TechCrunch", "The Robot Report"]
  tier_3:
    score: 0.5
    sources: ["Reddit", "HackerNews"]
  tier_4:
    score: 0.3
    sources: ["X/Twitter"]
```

---

## 8. LLM Gateway

### 8.1 구조

```
LLM Gateway
├── 통합 인터페이스: call(model, prompt, options)
├── Model Adapters: Gemini, GPT5 Pro, Claude Opus (+ 확장 가능)
├── 세션 관리: Context Branching, Checkpoint 지원
└── 비용 추적: 예산 제한 on/off 시에만 경량 집계 (기본 off, 제공사 대시보드 활용)
```

### 8.2 역할

| 컴포넌트 | 설명 |
|----------|------|
| 통합 인터페이스 | 모델 종류에 무관하게 동일한 방식으로 호출 |
| Model Adapter | 각 모델 API의 차이를 흡수 (인증, 요청 포맷, 응답 파싱) |
| 세션 관리 | GPT5 Pro의 Checkpoint/Branching 지원 |
| 비용 추적 | 예산 제한 on 시에만 API 응답 토큰 수 집계 |

새 모델 추가 시 Adapter만 작성.

---

## 9. Obsidian Writer

### 9.1 구조

| 컴포넌트 | 설명 |
|----------|------|
| Vault Manager | Vault 경로 관리, 폴더 존재 확인/생성 |
| Raw Writer | 수집 원본을 `raw/{날짜}/` 에 스키마 포맷으로 저장 |
| Profile Writer | `companies/*.md`, `topics/*.md` 읽기/업데이트 |
| Weekly Writer | `weekly/` 통합본, 스냅샷 생성 |
| Frontmatter Handler | YAML frontmatter 생성, 파싱, 필드 업데이트 |
| WikiLink Handler | Registry 기반으로 본문 내 회사/키워드를 `[[위키링크]]`로 자동 변환 |

---

## 10. 운영

### 10.1 실행 환경

- 로컬 PC 기본 실행
- 클라우드/자체 서버로 이식 가능한 구조
  - 실행 환경 비의존 (OS 종속 기능에 직접 결합하지 않음)
  - 설정 외부화 (API 키, 경로, 수집 주기 등 config 파일 분리)
  - Vault 경로 설정화

### 10.2 비용 관리

- 기본: 제공사 대시보드 활용 (자체 구현 불필요)
- 예산 제한 필요 시: on/off 가능한 경량 집계 로직 추가 (기본 off)

---

## 11. 프로젝트 디렉토리 구조

```
market_intel/
├── src/
│   ├── scheduler/
│   ├── sources/            # 소스 모듈 (플러그인 구조)
│   │   ├── base.py         # 공통 인터페이스 (추상 클래스)
│   │   ├── rss.py
│   │   ├── web.py
│   │   ├── sns.py
│   │   └── youtube.py
│   ├── gateway/            # LLM Gateway
│   │   ├── gateway.py
│   │   ├── adapters/       # 모델별 Adapter
│   │   └── session.py      # 세션/Checkpoint 관리
│   ├── writer/             # Obsidian Writer
│   ├── refinery/           # 주간 정제 파이프라인
│
├── config.yaml
│
├── vault/                  # Obsidian Vault
│   ├── companies/
│   ├── topics/
│   ├── raw/
│   ├── weekly/
│   ├── assets/
│   └── registry/
│       ├── companies.yaml
│       ├── keywords.yaml
│       └── source_reputation.yaml
│
└── docs/
    └── superpowers/
        └── specs/
            └── (이 문서)
```

---

## 12. Backlog / 확장 경로

| 항목 | 설명 | 트리거 |
|------|------|--------|
| (C) LLM-native 검색 | 인덱스 레이어 추가, LLM이 문서를 직접 탐색 | 회사 수 증가, cross-cutting 질문 빈번 |
| Claim 추출 + 교차 검증 | 핵심 주장 추출 → 다른 소스에서 검증 | 검증 정밀도 필요 |
| 피드백 루프 자동화 | Step 3 → Step 2 자동 루프 (Context Branching 적용) | 수동 검토에서 전환 |
| 예산 제한 | 일일/월간 토큰 상한, 초과 시 중단/경고 | 비용 증가 |
