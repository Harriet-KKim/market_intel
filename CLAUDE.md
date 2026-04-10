# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

**In-progress.** Phases 1–4 (Tasks 1–14) have landed: config, registry, dedup, LLM Gateway + 3 adapters + sessions, Obsidian Writer module, sources, collector, scheduler. Phase 5 (Refinery, Tasks 15–17) and Phase 6 (Main CLI, Task 18) remain.

- Requirements: `Initial_Requirement.md` (Korean)
- Design spec: `docs/superpowers/specs/2026-04-09-market-intel-system-design.md`
- **Implementation plan — canonical (split version):** `docs/plans/README.md` is the landing page; `docs/plans/01-config.md` … `10-main.md` are the authoritative per-module plans. The split version has **local patches** (K1/P1/P2/I1–I5/C1–C4/G1–G4) applied on top of the original; always read `docs/plans/README.md` first when picking up a task so you inherit the patches. When asked to implement, use `superpowers:subagent-driven-development` or `superpowers:executing-plans`.
- **Original (reference only):** `docs/superpowers/plans/2026-04-09-market-intel-implementation.md` — 18-task monolithic plan. Do NOT execute directly; it has known bugs the split version has already fixed. Use only for cross-checking section layout.
- **Backlog:** `docs/plans/README.md` 의 `알려진 한계 (Not Fixed)` 표(L# IDs) 가 구현 레벨 백로그의 정본. 리뷰어가 발견했지만 즉시 수정하지 않은 항목은 L# 엔트리로 기록.

The user writes docs and discusses in **Korean**; respond in Korean. Code identifiers stay in English.

## What This System Does

Physical AI (로보틱스, 자율주행, embodied AI, world models) 시장을 개인 리서치 용도로 자동 수집·정제하는 Obsidian 기반 워크플로우. Andrej Karpathy의 LLM-Wiki 개념 (B) "지속적 지식 축적 + 구조화된 문서 + 점진적 정제"를 부분 적용.

Two pipelines run on different cadences against a shared Obsidian Vault:

1. **Collection (sub-daily)** — Source modules (RSS / web / SNS / YouTube) fetch articles, Gemini tags them with company/topic registry entries, results land in `vault/raw/{date}/`.
2. **Weekly refinement (3-step multi-model)** — GPT5 Pro consolidates the week's raw into a structured report → Claude Opus summarizes and **merges into existing `vault/companies/*.md` and `vault/topics/*.md`** → GPT5 Pro reviews (same session). The whole output lands under `vault/weekly/`.

## Architectural Load-Bearing Decisions

These are choices the spec/plan explicitly made. Don't revisit them without discussing first — they shape the entire codebase:

- **Hybrid: Python scripts + thin LLM Gateway wrapper.** No agent framework. The pipelines are serial flows; an agent framework would be wasted abstraction.
- **Role split between Script and LLM:** Script handles fetch, parsing, dedup, storage, scheduling. LLM (Gemini) handles tagging only — *except* the web source, where the agent does full extraction+schema+tagging in one call because HTML structures are too varied.
- **URL-only dedup.** Content-similarity dedup is delegated to the refinement models. Dedup store is SQLite (`src/dedup.py`).
- **WikiLinks replace reference tables.** Raw articles embed `[[NVIDIA]]` inline; Obsidian Backlinks handle the reverse index. No separate "mentions" file.
- **Registry lives inside the Vault** (`vault/registry/companies.yaml`, `keywords.yaml`, `source_reputation.yaml`) so the user can edit it in Obsidian alongside the notes.
- **Source reputation is two-stage:** tier-based score applied at collection time from `source_reputation.yaml` (tier_1 0.9 → tier_4 0.3); weekly refinement cross-verifies and can overwrite.
- **Context Branching for the refinement pipeline.** After Step 1 (GPT5 Pro consolidation), save a **Checkpoint**. Step 3 review branches from that Checkpoint instead of continuing the Step 2 thread, so repeated feedback loops don't accumulate context. `src/gateway/session.py` must support this; the OpenAI adapter is the one that actually implements it. Gemini/Anthropic adapters can stub `create_checkpoint` / `branch_from` until needed.
- **No backfill / cold start.** Accumulation starts at first run.
- **Budget tracking is off by default.** Rely on provider dashboards; only enable lightweight aggregation when `budget.enabled: true`.

## File Layout (planned)

```
src/
├── config.py              # YAML config + ${ENV_VAR} substitution
├── registry.py            # Loads companies/keywords/source_reputation from vault/registry/
├── dedup.py               # SQLite URL dedup
├── gateway/               # LLM abstraction
│   ├── gateway.py         # call(model, prompt, options)
│   ├── session.py         # Checkpoint / branch_from (for Context Branching)
│   ├── base_adapter.py
│   └── adapters/          # gemini.py, openai.py, anthropic.py
├── writer/                # Obsidian Vault CRUD
│   ├── frontmatter.py     # YAML frontmatter parse/generate (python-frontmatter)
│   ├── wikilink.py        # Inject [[Name]] based on registry aliases
│   ├── vault.py
│   ├── raw_writer.py      # raw/{date}/{id}.md
│   ├── profile_writer.py  # Reads+merges companies/*.md, topics/*.md (preserves sections)
│   └── weekly_writer.py   # weekly/{YYYY-Wxx}-consolidated.md and {YYYY-Wxx}.md
├── sources/               # Plugin-structured; add source = new file + config entry
│   ├── base.py            # Abstract Source interface
│   ├── rss.py             # feedparser
│   ├── web.py             # httpx + Agent-full-extract
│   ├── sns.py             # X, Reddit, HackerNews
│   └── youtube.py         # yt-dlp transcript + optional multimodal on keyframes
├── collector/pipeline.py  # Orchestrates sources → Gemini tag → raw_writer → dedup
├── refinery/              # Weekly pipeline
│   ├── consolidator.py    # Step 1 (GPT5 Pro)
│   ├── summarizer.py      # Step 2 (Claude Opus) — merges into profile docs
│   ├── reviewer.py        # Step 3 (GPT5 Pro, branched from Step 1 checkpoint)
│   └── pipeline.py
└── scheduler/scheduler.py # APScheduler
```

The Vault is runtime state (created by `main.py` on first run), not source-controlled.

## Development Commands

Once the plan's Task 1 lands `pyproject.toml`:

```bash
pip install -e ".[dev]"          # install with dev deps (pytest, pytest-asyncio)
pytest tests/ -v                 # full suite
pytest tests/test_config.py -v   # single file
pytest tests/test_config.py::test_load_config_env_var_substitution -v  # single test
```

pytest config is inlined in `pyproject.toml`: `testpaths = ["tests"]`, `pythonpath = ["."]`, so imports use `from src.config import ...`.

Required env vars at runtime: `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`. `config.yaml` substitutes `${VAR}` placeholders via `src.config._substitute_env_vars`.

## Working On This Plan

- **Always start from `docs/plans/README.md`**, not the original monolithic plan. The split version's task files (`01-config.md` … `10-main.md`) are the canonical spec; the README lists which local patches (K1, P1, P2, I1–I5, C1–C4) have been pre-applied and which limitations (L1–L19) remain as backlog.
- The plan is structured as **TDD**: each task is write-failing-test → run-and-confirm-fail → implement → run-and-confirm-pass → commit. Don't skip the fail step — it's how the plan validates the test actually tests something.
- Each task ends with its own commit. Don't batch multiple tasks into one commit.
- Profile writer tests (Task 9) are the trickiest: merging into existing company/topic docs must preserve fixed sections (`## 회사 개요`, `## 최근 동향`, etc.) and append under the right headings. Read that task carefully before coding.
- When the plan says "Context Branching" for the refinery pipeline, it means the Step 3 reviewer must be `session.branch_from(checkpoint)`, not a continuation of the Step 2 thread.
- **Windows note:** `python` on Windows 11 may open the MS Store installer. Use `py -m pytest ...` to invoke Python reliably.

## Plugins

`.claude/settings.json` enables the `codex@openai-codex` plugin — the `codex:rescue` subagent is available for second-opinion investigations or handing off stuck coding tasks.
