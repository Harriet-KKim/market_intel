# Physical AI Market Intelligence System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Physical AI 시장 정보를 자동 수집하고, 주간 단위로 멀티 모델 파이프라인을 통해 정제/요약하는 Obsidian 기반 개인 리서치 시스템 구축.

**Architecture:** Python Script 기반 + LLM Gateway 경량 래핑 하이브리드 구조. 수집 파이프라인(하루 미만 주기)이 소스별 모듈을 통해 데이터를 가져오고 Gemini로 태깅한 뒤 Obsidian Vault에 저장. 주간 정제 파이프라인이 GPT5 Pro(통합) → Claude Opus(요약) → GPT5 Pro(검토) 3단계로 정제하여 회사/주제 문서를 업데이트.

**Tech Stack:** Python 3.12+, httpx (HTTP), feedparser (RSS), yt-dlp (YouTube), python-frontmatter (Markdown frontmatter), PyYAML, APScheduler, google-genai (Gemini), openai (GPT5 Pro), anthropic (Claude), pytest, SQLite (URL dedup)

---

## File Structure

```
market_intel/
├── pyproject.toml
├── src/
│   ├── __init__.py
│   ├── config.py                    # Config loading from YAML
│   ├── registry.py                  # Registry loading (companies, keywords, reputation)
│   ├── dedup.py                     # URL dedup with SQLite
│   ├── gateway/
│   │   ├── __init__.py
│   │   ├── base_adapter.py          # Abstract adapter interface
│   │   ├── gateway.py               # Unified LLM call interface
│   │   ├── session.py               # Session/Checkpoint management
│   │   └── adapters/
│   │       ├── __init__.py
│   │       ├── gemini.py            # Google Gemini adapter
│   │       ├── openai.py            # OpenAI GPT5 Pro adapter
│   │       └── anthropic.py         # Anthropic Claude adapter
│   ├── writer/
│   │   ├── __init__.py
│   │   ├── frontmatter.py           # YAML frontmatter parse/generate
│   │   ├── wikilink.py              # WikiLink injection based on registry
│   │   ├── vault.py                 # Vault manager (path, folder creation)
│   │   ├── raw_writer.py            # Write raw collected articles
│   │   ├── profile_writer.py        # Read/update company & topic docs
│   │   └── weekly_writer.py         # Write consolidated & snapshot docs
│   ├── sources/
│   │   ├── __init__.py
│   │   ├── base.py                  # Abstract source module interface
│   │   ├── rss.py                   # RSS/API source
│   │   ├── web.py                   # Web page source (Agent full extraction)
│   │   ├── sns.py                   # SNS source (X, Reddit, HackerNews)
│   │   └── youtube.py               # YouTube source (transcript + optional multimodal)
│   ├── collector/
│   │   ├── __init__.py
│   │   └── pipeline.py              # Collection pipeline orchestrator
│   ├── refinery/
│   │   ├── __init__.py
│   │   ├── consolidator.py          # Step 1: consolidated report (GPT5 Pro)
│   │   ├── summarizer.py            # Step 2: summary + doc updates (Claude Opus)
│   │   ├── reviewer.py              # Step 3: review (GPT5 Pro, same session)
│   │   └── pipeline.py              # Refinement pipeline orchestrator
│   └── scheduler/
│       ├── __init__.py
│       └── scheduler.py             # APScheduler setup
├── config.yaml                      # Main configuration
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  # Shared fixtures
│   ├── test_config.py
│   ├── test_registry.py
│   ├── test_dedup.py
│   ├── test_frontmatter.py
│   ├── test_wikilink.py
│   ├── test_vault.py
│   ├── test_raw_writer.py
│   ├── test_profile_writer.py
│   ├── test_weekly_writer.py
│   ├── test_gateway.py
│   ├── test_session.py
│   ├── test_source_base.py
│   ├── test_source_rss.py
│   ├── test_source_web.py
│   ├── test_source_sns.py
│   ├── test_source_youtube.py
│   ├── test_collector_pipeline.py
│   ├── test_consolidator.py
│   ├── test_summarizer.py
│   ├── test_reviewer.py
│   └── test_refinery_pipeline.py
├── vault/                           # Obsidian Vault (created at runtime)
└── docs/
    └── superpowers/
        ├── specs/
        └── plans/
```

---

## Phase 1: Foundation

### Task 1: Project Setup & Config

**Files:**
- Create: `pyproject.toml`
- Create: `config.yaml`
- Create: `src/__init__.py`
- Create: `src/config.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Initialize project with pyproject.toml**

```toml
# pyproject.toml
[project]
name = "market-intel"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.27",
    "feedparser>=6.0",
    "yt-dlp>=2024.0",
    "python-frontmatter>=1.1",
    "pyyaml>=6.0",
    "apscheduler>=3.10",
    "google-genai>=1.0",
    "openai>=1.50",
    "anthropic>=0.40",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.24"]

[build-system]
requires = ["setuptools>=75.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

```yaml
# config.yaml
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
  gemini: "${GEMINI_API_KEY}"
  openai: "${OPENAI_API_KEY}"
  anthropic: "${ANTHROPIC_API_KEY}"
budget:
  enabled: false
  daily_limit_usd: 10.0
```

```python
# src/__init__.py
```

```python
# tests/__init__.py
```

Run: `pip install -e ".[dev]"`

- [ ] **Step 2: Write the failing test for config loading**

```python
# tests/test_config.py
import os
from pathlib import Path


def test_load_config_from_yaml(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
vault_path: "./vault"
collection:
  interval_hours: 6
  sources:
    rss: true
    web: true
    sns: false
    youtube: true
refinery:
  schedule_day: "monday"
  schedule_hour: 9
api_keys:
  gemini: "test-gemini-key"
  openai: "test-openai-key"
  anthropic: "test-anthropic-key"
budget:
  enabled: false
  daily_limit_usd: 10.0
""")
    from src.config import load_config

    config = load_config(config_file)

    assert config.vault_path == Path("./vault")
    assert config.collection.interval_hours == 6
    assert config.collection.sources.rss is True
    assert config.collection.sources.sns is False
    assert config.refinery.schedule_day == "monday"
    assert config.api_keys.gemini == "test-gemini-key"
    assert config.budget.enabled is False


def test_load_config_env_var_substitution(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "env-gemini-key")
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
  gemini: "${GEMINI_API_KEY}"
  openai: "direct-key"
  anthropic: "direct-key"
budget:
  enabled: false
  daily_limit_usd: 10.0
""")
    from src.config import load_config

    config = load_config(config_file)

    assert config.api_keys.gemini == "env-gemini-key"
    assert config.api_keys.openai == "direct-key"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.config'`

- [ ] **Step 4: Implement config module**

```python
# src/config.py
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class SourcesConfig:
    rss: bool
    web: bool
    sns: bool
    youtube: bool


@dataclass
class CollectionConfig:
    interval_hours: int
    sources: SourcesConfig


@dataclass
class RefineryConfig:
    schedule_day: str
    schedule_hour: int


@dataclass
class ApiKeysConfig:
    gemini: str
    openai: str
    anthropic: str


@dataclass
class BudgetConfig:
    enabled: bool
    daily_limit_usd: float


@dataclass
class AppConfig:
    vault_path: Path
    collection: CollectionConfig
    refinery: RefineryConfig
    api_keys: ApiKeysConfig
    budget: BudgetConfig


def _substitute_env_vars(value: str) -> str:
    """Replace ${VAR_NAME} with environment variable value."""
    def replacer(match):
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))
    return re.sub(r"\$\{(\w+)\}", replacer, value)


def _process_env_vars(data: dict) -> dict:
    """Recursively substitute environment variables in string values."""
    result = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = _process_env_vars(value)
        elif isinstance(value, str):
            result[key] = _substitute_env_vars(value)
        else:
            result[key] = value
    return result


def load_config(path: Path) -> AppConfig:
    """Load and parse config from a YAML file."""
    with open(path) as f:
        raw = yaml.safe_load(f)

    data = _process_env_vars(raw)

    return AppConfig(
        vault_path=Path(data["vault_path"]),
        collection=CollectionConfig(
            interval_hours=data["collection"]["interval_hours"],
            sources=SourcesConfig(**data["collection"]["sources"]),
        ),
        refinery=RefineryConfig(
            schedule_day=data["refinery"]["schedule_day"],
            schedule_hour=data["refinery"]["schedule_hour"],
        ),
        api_keys=ApiKeysConfig(
            gemini=data["api_keys"]["gemini"],
            openai=data["api_keys"]["openai"],
            anthropic=data["api_keys"]["anthropic"],
        ),
        budget=BudgetConfig(
            enabled=data["budget"]["enabled"],
            daily_limit_usd=data["budget"]["daily_limit_usd"],
        ),
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml config.yaml src/__init__.py src/config.py tests/__init__.py tests/test_config.py
git commit -m "feat: project setup and config loading module"
```

---

### Task 2: Registry Module

**Files:**
- Create: `src/registry.py`
- Create: `tests/test_registry.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create shared test fixtures**

```python
# tests/conftest.py
import pytest
from pathlib import Path


@pytest.fixture
def sample_registry_dir(tmp_path):
    """Create a temporary registry directory with sample YAML files."""
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir()

    (registry_dir / "companies.yaml").write_text("""
companies:
  - id: nvidia
    name: "NVIDIA"
    aliases: ["엔비디아", "Jensen Huang", "Cosmos", "Isaac"]
    sources:
      rss: ["https://blogs.nvidia.com/feed/"]
      youtube: ["@NVIDIA"]
      official: ["https://nvidianews.nvidia.com/"]
    topics: ["world-model", "sim-to-real"]
  - id: figure-ai
    name: "Figure AI"
    aliases: ["Figure", "Figure 01", "Figure 02"]
    sources:
      youtube: ["@figureai"]
      official: ["https://www.figure.ai/news"]
    topics: ["humanoid-robot", "manipulation"]
""")

    (registry_dir / "keywords.yaml").write_text("""
keywords:
  - id: world-model
    name: "World Models"
    aliases: ["world model", "월드 모델", "world simulator"]
  - id: humanoid-robot
    name: "Humanoid Robot"
    aliases: ["humanoid", "휴머노이드"]
""")

    (registry_dir / "source_reputation.yaml").write_text("""
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
""")

    return registry_dir
```

- [ ] **Step 2: Write failing tests for registry**

```python
# tests/test_registry.py
def test_load_companies(sample_registry_dir):
    from src.registry import Registry

    registry = Registry(sample_registry_dir)

    assert len(registry.companies) == 2
    nvidia = registry.get_company("nvidia")
    assert nvidia.name == "NVIDIA"
    assert "Jensen Huang" in nvidia.aliases
    assert "world-model" in nvidia.topics


def test_load_keywords(sample_registry_dir):
    from src.registry import Registry

    registry = Registry(sample_registry_dir)

    assert len(registry.keywords) == 2
    wm = registry.get_keyword("world-model")
    assert wm.name == "World Models"
    assert "월드 모델" in wm.aliases


def test_get_reputation_score(sample_registry_dir):
    from src.registry import Registry

    registry = Registry(sample_registry_dir)

    assert registry.get_reputation_score("Reuters") == 0.9
    assert registry.get_reputation_score("TechCrunch") == 0.7
    assert registry.get_reputation_score("Unknown Source") is None


def test_match_companies_from_text(sample_registry_dir):
    from src.registry import Registry

    registry = Registry(sample_registry_dir)
    text = "Jensen Huang unveiled NVIDIA's new robotics platform. Figure AI also announced partnership."

    matches = registry.match_companies(text)

    assert "nvidia" in matches
    assert "figure-ai" in matches


def test_match_keywords_from_text(sample_registry_dir):
    from src.registry import Registry

    registry = Registry(sample_registry_dir)
    text = "New advances in world model research for humanoid robots."

    matches = registry.match_keywords(text)

    assert "world-model" in matches
    assert "humanoid-robot" in matches
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_registry.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Implement registry module**

```python
# src/registry.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Company:
    id: str
    name: str
    aliases: list[str]
    sources: dict[str, list[str]]
    topics: list[str]


@dataclass
class Keyword:
    id: str
    name: str
    aliases: list[str]


@dataclass
class ReputationTier:
    score: float
    sources: list[str]


class Registry:
    def __init__(self, registry_dir: Path):
        self.registry_dir = registry_dir
        self.companies: list[Company] = []
        self.keywords: list[Keyword] = []
        self.reputation_tiers: list[ReputationTier] = []
        self._company_map: dict[str, Company] = {}
        self._keyword_map: dict[str, Keyword] = {}
        self._reputation_map: dict[str, float] = {}
        self._load()

    def _load(self):
        self._load_companies()
        self._load_keywords()
        self._load_reputation()

    def _load_companies(self):
        path = self.registry_dir / "companies.yaml"
        with open(path) as f:
            data = yaml.safe_load(f)
        for entry in data.get("companies", []):
            company = Company(
                id=entry["id"],
                name=entry["name"],
                aliases=entry.get("aliases", []),
                sources=entry.get("sources", {}),
                topics=entry.get("topics", []),
            )
            self.companies.append(company)
            self._company_map[company.id] = company

    def _load_keywords(self):
        path = self.registry_dir / "keywords.yaml"
        with open(path) as f:
            data = yaml.safe_load(f)
        for entry in data.get("keywords", []):
            keyword = Keyword(
                id=entry["id"],
                name=entry["name"],
                aliases=entry.get("aliases", []),
            )
            self.keywords.append(keyword)
            self._keyword_map[keyword.id] = keyword

    def _load_reputation(self):
        path = self.registry_dir / "source_reputation.yaml"
        with open(path) as f:
            data = yaml.safe_load(f)
        for tier_name, tier_data in data.get("tiers", {}).items():
            tier = ReputationTier(
                score=tier_data["score"],
                sources=tier_data["sources"],
            )
            self.reputation_tiers.append(tier)
            for source_name in tier.sources:
                self._reputation_map[source_name.lower()] = tier.score

    def get_company(self, company_id: str) -> Company | None:
        return self._company_map.get(company_id)

    def get_keyword(self, keyword_id: str) -> Keyword | None:
        return self._keyword_map.get(keyword_id)

    def get_reputation_score(self, source_name: str) -> float | None:
        return self._reputation_map.get(source_name.lower())

    def match_companies(self, text: str) -> list[str]:
        """Return list of company IDs whose name or aliases appear in text."""
        text_lower = text.lower()
        matched = []
        for company in self.companies:
            search_terms = [company.name.lower()] + [a.lower() for a in company.aliases]
            if any(term in text_lower for term in search_terms):
                matched.append(company.id)
        return matched

    def match_keywords(self, text: str) -> list[str]:
        """Return list of keyword IDs whose name or aliases appear in text."""
        text_lower = text.lower()
        matched = []
        for keyword in self.keywords:
            search_terms = [keyword.name.lower()] + [a.lower() for a in keyword.aliases]
            if any(term in text_lower for term in search_terms):
                matched.append(keyword.id)
        return matched
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_registry.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add src/registry.py tests/conftest.py tests/test_registry.py
git commit -m "feat: registry module for companies, keywords, and source reputation"
```

---

### Task 3: URL Dedup Store

**Files:**
- Create: `src/dedup.py`
- Create: `tests/test_dedup.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_dedup.py
def test_url_not_seen_initially(tmp_path):
    from src.dedup import UrlDedup

    dedup = UrlDedup(tmp_path / "dedup.db")

    assert dedup.is_seen("https://example.com/article-1") is False


def test_mark_url_as_seen(tmp_path):
    from src.dedup import UrlDedup

    dedup = UrlDedup(tmp_path / "dedup.db")
    dedup.mark_seen("https://example.com/article-1")

    assert dedup.is_seen("https://example.com/article-1") is True
    assert dedup.is_seen("https://example.com/article-2") is False


def test_persistence_across_instances(tmp_path):
    from src.dedup import UrlDedup

    db_path = tmp_path / "dedup.db"
    dedup1 = UrlDedup(db_path)
    dedup1.mark_seen("https://example.com/article-1")
    dedup1.close()

    dedup2 = UrlDedup(db_path)
    assert dedup2.is_seen("https://example.com/article-1") is True
    dedup2.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dedup.py -v`
Expected: FAIL

- [ ] **Step 3: Implement dedup module**

```python
# src/dedup.py
from __future__ import annotations

import sqlite3
from pathlib import Path


class UrlDedup:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS seen_urls (url TEXT PRIMARY KEY, seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        self._conn.commit()

    def is_seen(self, url: str) -> bool:
        cursor = self._conn.execute("SELECT 1 FROM seen_urls WHERE url = ?", (url,))
        return cursor.fetchone() is not None

    def mark_seen(self, url: str) -> None:
        self._conn.execute("INSERT OR IGNORE INTO seen_urls (url) VALUES (?)", (url,))
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dedup.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/dedup.py tests/test_dedup.py
git commit -m "feat: URL dedup store with SQLite"
```

---

## Phase 2: LLM Gateway

### Task 4: Base Adapter & Gateway Interface

**Files:**
- Create: `src/gateway/__init__.py`
- Create: `src/gateway/base_adapter.py`
- Create: `src/gateway/gateway.py`
- Create: `src/gateway/adapters/__init__.py`
- Create: `tests/test_gateway.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_gateway.py
import pytest


def test_gateway_call_routes_to_adapter():
    from src.gateway.gateway import LLMGateway
    from src.gateway.base_adapter import BaseAdapter, LLMResponse

    class MockAdapter(BaseAdapter):
        def call(self, prompt: str, system: str | None = None, **kwargs) -> LLMResponse:
            return LLMResponse(content=f"mock: {prompt}", input_tokens=10, output_tokens=5)

        def call_with_history(self, messages: list[dict], system: str | None = None, **kwargs) -> LLMResponse:
            return LLMResponse(content="mock history", input_tokens=10, output_tokens=5)

    gateway = LLMGateway()
    gateway.register_adapter("mock-model", MockAdapter())

    response = gateway.call("mock-model", prompt="hello")

    assert response.content == "mock: hello"
    assert response.input_tokens == 10


def test_gateway_unknown_model_raises():
    from src.gateway.gateway import LLMGateway

    gateway = LLMGateway()

    with pytest.raises(KeyError, match="no-such-model"):
        gateway.call("no-such-model", prompt="hello")


def test_gateway_call_with_history():
    from src.gateway.gateway import LLMGateway
    from src.gateway.base_adapter import BaseAdapter, LLMResponse

    class MockAdapter(BaseAdapter):
        def call(self, prompt: str, system: str | None = None, **kwargs) -> LLMResponse:
            return LLMResponse(content="mock", input_tokens=0, output_tokens=0)

        def call_with_history(self, messages: list[dict], system: str | None = None, **kwargs) -> LLMResponse:
            last_msg = messages[-1]["content"]
            return LLMResponse(content=f"history: {last_msg}", input_tokens=20, output_tokens=10)

    gateway = LLMGateway()
    gateway.register_adapter("mock-model", MockAdapter())

    messages = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "response"},
        {"role": "user", "content": "second"},
    ]
    response = gateway.call_with_history("mock-model", messages=messages)

    assert response.content == "history: second"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_gateway.py -v`
Expected: FAIL

- [ ] **Step 3: Implement base adapter and gateway**

```python
# src/gateway/__init__.py
```

```python
# src/gateway/adapters/__init__.py
```

```python
# src/gateway/base_adapter.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    content: str
    input_tokens: int
    output_tokens: int


class BaseAdapter(ABC):
    @abstractmethod
    def call(self, prompt: str, system: str | None = None, **kwargs) -> LLMResponse:
        """Single prompt call."""
        ...

    @abstractmethod
    def call_with_history(self, messages: list[dict], system: str | None = None, **kwargs) -> LLMResponse:
        """Call with conversation history for session continuity."""
        ...
```

```python
# src/gateway/gateway.py
from __future__ import annotations

from src.gateway.base_adapter import BaseAdapter, LLMResponse


class LLMGateway:
    def __init__(self):
        self._adapters: dict[str, BaseAdapter] = {}

    def register_adapter(self, model_name: str, adapter: BaseAdapter) -> None:
        self._adapters[model_name] = adapter

    def call(self, model: str, prompt: str, system: str | None = None, **kwargs) -> LLMResponse:
        adapter = self._get_adapter(model)
        return adapter.call(prompt=prompt, system=system, **kwargs)

    def call_with_history(self, model: str, messages: list[dict], system: str | None = None, **kwargs) -> LLMResponse:
        adapter = self._get_adapter(model)
        return adapter.call_with_history(messages=messages, system=system, **kwargs)

    def _get_adapter(self, model: str) -> BaseAdapter:
        if model not in self._adapters:
            raise KeyError(f"No adapter registered for model: {model}")
        return self._adapters[model]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_gateway.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/gateway/ tests/test_gateway.py
git commit -m "feat: LLM Gateway with base adapter interface"
```

---

### Task 5: Model Adapters (Gemini, OpenAI, Anthropic)

**Files:**
- Create: `src/gateway/adapters/gemini.py`
- Create: `src/gateway/adapters/openai.py`
- Create: `src/gateway/adapters/anthropic.py`

Each adapter wraps the respective SDK. Tests use monkeypatching to avoid real API calls.

- [ ] **Step 1: Write failing test for Gemini adapter**

```python
# tests/test_gateway.py (append to existing file)


def test_gemini_adapter_call(monkeypatch):
    from src.gateway.adapters.gemini import GeminiAdapter

    class MockResponse:
        text = "gemini response"
        usage_metadata = type("Usage", (), {"prompt_token_count": 15, "candidates_token_count": 8})()

    class MockModel:
        def generate_content(self, contents, **kwargs):
            return MockResponse()

    class MockClient:
        models = type("Models", (), {"generate_content": MockModel().generate_content})()

    adapter = GeminiAdapter(client=MockClient(), model_id="gemini-2.0-flash")
    response = adapter.call("test prompt")

    assert response.content == "gemini response"
    assert response.input_tokens == 15
    assert response.output_tokens == 8


def test_openai_adapter_call():
    from src.gateway.adapters.openai import OpenAIAdapter

    class MockMessage:
        content = "gpt response"

    class MockChoice:
        message = MockMessage()

    class MockUsage:
        prompt_tokens = 20
        completion_tokens = 12

    class MockCompletion:
        choices = [MockChoice()]
        usage = MockUsage()

    class MockChat:
        class completions:
            @staticmethod
            def create(**kwargs):
                return MockCompletion()

    class MockClient:
        chat = MockChat()

    adapter = OpenAIAdapter(client=MockClient(), model_id="gpt-5-pro")
    response = adapter.call("test prompt")

    assert response.content == "gpt response"
    assert response.input_tokens == 20
    assert response.output_tokens == 12


def test_anthropic_adapter_call():
    from src.gateway.adapters.anthropic import AnthropicAdapter

    class MockContentBlock:
        text = "claude response"

    class MockUsage:
        input_tokens = 25
        output_tokens = 15

    class MockResponse:
        content = [MockContentBlock()]
        usage = MockUsage()

    class MockMessages:
        def create(self, **kwargs):
            return MockResponse()

    class MockClient:
        messages = MockMessages()

    adapter = AnthropicAdapter(client=MockClient(), model_id="claude-opus-4-6")
    response = adapter.call("test prompt")

    assert response.content == "claude response"
    assert response.input_tokens == 25
    assert response.output_tokens == 15
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_gateway.py -v -k "adapter"`
Expected: FAIL

- [ ] **Step 3: Implement Gemini adapter**

```python
# src/gateway/adapters/gemini.py
from __future__ import annotations

from src.gateway.base_adapter import BaseAdapter, LLMResponse


class GeminiAdapter(BaseAdapter):
    def __init__(self, client, model_id: str):
        self._client = client
        self._model_id = model_id

    def call(self, prompt: str, system: str | None = None, **kwargs) -> LLMResponse:
        contents = prompt
        if system:
            contents = f"{system}\n\n{prompt}"

        response = self._client.models.generate_content(
            contents=contents,
            model=self._model_id,
            **kwargs,
        )

        return LLMResponse(
            content=response.text,
            input_tokens=response.usage_metadata.prompt_token_count,
            output_tokens=response.usage_metadata.candidates_token_count,
        )

    def call_with_history(self, messages: list[dict], system: str | None = None, **kwargs) -> LLMResponse:
        # Gemini uses contents list format
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        response = self._client.models.generate_content(
            contents=contents,
            model=self._model_id,
            **kwargs,
        )

        return LLMResponse(
            content=response.text,
            input_tokens=response.usage_metadata.prompt_token_count,
            output_tokens=response.usage_metadata.candidates_token_count,
        )
```

- [ ] **Step 4: Implement OpenAI adapter**

```python
# src/gateway/adapters/openai.py
from __future__ import annotations

from src.gateway.base_adapter import BaseAdapter, LLMResponse


class OpenAIAdapter(BaseAdapter):
    def __init__(self, client, model_id: str):
        self._client = client
        self._model_id = model_id

    def call(self, prompt: str, system: str | None = None, **kwargs) -> LLMResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self._client.chat.completions.create(
            model=self._model_id,
            messages=messages,
            **kwargs,
        )

        return LLMResponse(
            content=response.choices[0].message.content,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )

    def call_with_history(self, messages: list[dict], system: str | None = None, **kwargs) -> LLMResponse:
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        response = self._client.chat.completions.create(
            model=self._model_id,
            messages=full_messages,
            **kwargs,
        )

        return LLMResponse(
            content=response.choices[0].message.content,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )
```

- [ ] **Step 5: Implement Anthropic adapter**

```python
# src/gateway/adapters/anthropic.py
from __future__ import annotations

from src.gateway.base_adapter import BaseAdapter, LLMResponse


class AnthropicAdapter(BaseAdapter):
    def __init__(self, client, model_id: str):
        self._client = client
        self._model_id = model_id

    def call(self, prompt: str, system: str | None = None, **kwargs) -> LLMResponse:
        params = {
            "model": self._model_id,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": kwargs.pop("max_tokens", 4096),
            **kwargs,
        }
        if system:
            params["system"] = system

        response = self._client.messages.create(**params)

        return LLMResponse(
            content=response.content[0].text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    def call_with_history(self, messages: list[dict], system: str | None = None, **kwargs) -> LLMResponse:
        params = {
            "model": self._model_id,
            "messages": messages,
            "max_tokens": kwargs.pop("max_tokens", 4096),
            **kwargs,
        }
        if system:
            params["system"] = system

        response = self._client.messages.create(**params)

        return LLMResponse(
            content=response.content[0].text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_gateway.py -v`
Expected: 6 passed

- [ ] **Step 7: Commit**

```bash
git add src/gateway/adapters/
git commit -m "feat: Gemini, OpenAI, and Anthropic adapters for LLM Gateway"
```

---

### Task 6: Session Management (Context Branching)

**Files:**
- Create: `src/gateway/session.py`
- Create: `tests/test_session.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_session.py
from src.gateway.base_adapter import LLMResponse


def make_mock_gateway():
    from src.gateway.gateway import LLMGateway
    from src.gateway.base_adapter import BaseAdapter

    class MockAdapter(BaseAdapter):
        def call(self, prompt: str, system: str | None = None, **kwargs) -> LLMResponse:
            return LLMResponse(content=f"response to: {prompt}", input_tokens=10, output_tokens=5)

        def call_with_history(self, messages: list[dict], system: str | None = None, **kwargs) -> LLMResponse:
            last = messages[-1]["content"]
            return LLMResponse(content=f"history response to: {last}", input_tokens=20, output_tokens=10)

    gw = LLMGateway()
    gw.register_adapter("test-model", MockAdapter())
    return gw


def test_session_tracks_history():
    from src.gateway.session import Session

    gateway = make_mock_gateway()
    session = Session(gateway=gateway, model="test-model", system="You are helpful.")

    response = session.send("hello")

    assert response.content == "history response to: hello"
    assert len(session.history) == 2  # user + assistant


def test_session_checkpoint_and_branch():
    from src.gateway.session import Session

    gateway = make_mock_gateway()
    session = Session(gateway=gateway, model="test-model")

    session.send("step 1 input")
    checkpoint = session.checkpoint()

    session.send("step 3 attempt 1")
    assert len(session.history) == 4  # 2 from step1 + 2 from step3

    branched = session.branch(checkpoint)
    assert len(branched.history) == 2  # only step 1 history

    branched.send("step 3 attempt 2")
    assert len(branched.history) == 4  # step1 + new step3
    assert len(session.history) == 4  # original unchanged
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_session.py -v`
Expected: FAIL

- [ ] **Step 3: Implement session management**

```python
# src/gateway/session.py
from __future__ import annotations

import copy
from dataclasses import dataclass, field

from src.gateway.base_adapter import LLMResponse
from src.gateway.gateway import LLMGateway


@dataclass
class Checkpoint:
    history: list[dict]
    system: str | None


class Session:
    def __init__(self, gateway: LLMGateway, model: str, system: str | None = None):
        self._gateway = gateway
        self._model = model
        self._system = system
        self.history: list[dict] = []

    def send(self, message: str) -> LLMResponse:
        """Send a message and append both user message and response to history."""
        self.history.append({"role": "user", "content": message})

        response = self._gateway.call_with_history(
            model=self._model,
            messages=self.history,
            system=self._system,
        )

        self.history.append({"role": "assistant", "content": response.content})
        return response

    def checkpoint(self) -> Checkpoint:
        """Save current history as a checkpoint for later branching."""
        return Checkpoint(
            history=copy.deepcopy(self.history),
            system=self._system,
        )

    def branch(self, checkpoint: Checkpoint) -> Session:
        """Create a new session branching from a checkpoint."""
        new_session = Session(
            gateway=self._gateway,
            model=self._model,
            system=checkpoint.system,
        )
        new_session.history = copy.deepcopy(checkpoint.history)
        return new_session
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_session.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/gateway/session.py tests/test_session.py
git commit -m "feat: session management with checkpoint and context branching"
```

---

## Phase 3: Obsidian Writer

### Task 7: Frontmatter & WikiLink Handlers

**Files:**
- Create: `src/writer/__init__.py`
- Create: `src/writer/frontmatter.py`
- Create: `src/writer/wikilink.py`
- Create: `tests/test_frontmatter.py`
- Create: `tests/test_wikilink.py`

- [ ] **Step 1: Write failing tests for frontmatter**

```python
# tests/test_frontmatter.py
def test_generate_frontmatter():
    from src.writer.frontmatter import generate_frontmatter

    metadata = {
        "id": "article-001",
        "title": "Test Article",
        "tags": ["world-model", "robotics"],
        "companies": ['[[NVIDIA]]', '[[Tesla]]'],
    }
    result = generate_frontmatter(metadata)

    assert result.startswith("---\n")
    assert result.endswith("---\n")
    assert "id: article-001" in result
    assert "- world-model" in result
    assert "- '[[NVIDIA]]'" in result


def test_parse_frontmatter():
    from src.writer.frontmatter import parse_document

    doc = """---
id: article-001
title: Test Article
tags:
  - world-model
---

This is the body content."""

    metadata, body = parse_document(doc)

    assert metadata["id"] == "article-001"
    assert "world-model" in metadata["tags"]
    assert body.strip() == "This is the body content."


def test_update_frontmatter_field():
    from src.writer.frontmatter import update_field

    doc = """---
id: article-001
reliability: null
---

Body."""

    result = update_field(doc, "reliability", 0.7)

    assert "reliability: 0.7" in result
    assert "Body." in result
```

- [ ] **Step 2: Write failing tests for wikilink**

```python
# tests/test_wikilink.py
def test_inject_wikilinks(sample_registry_dir):
    from src.registry import Registry
    from src.writer.wikilink import inject_wikilinks

    registry = Registry(sample_registry_dir)
    text = "NVIDIA announced a partnership with Figure AI on humanoid robots."

    result = inject_wikilinks(text, registry)

    assert "[[NVIDIA]]" in result
    assert "[[Figure AI]]" in result


def test_inject_wikilinks_no_double_wrap(sample_registry_dir):
    from src.registry import Registry
    from src.writer.wikilink import inject_wikilinks

    registry = Registry(sample_registry_dir)
    text = "[[NVIDIA]] already has wikilinks."

    result = inject_wikilinks(text, registry)

    assert result.count("[[NVIDIA]]") == 1
    assert "[[[[NVIDIA]]]]" not in result
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_frontmatter.py tests/test_wikilink.py -v`
Expected: FAIL

- [ ] **Step 4: Implement frontmatter handler**

```python
# src/writer/__init__.py
```

```python
# src/writer/frontmatter.py
from __future__ import annotations

import frontmatter
import yaml
import io


def generate_frontmatter(metadata: dict) -> str:
    """Generate YAML frontmatter string from a dict."""
    stream = io.StringIO()
    yaml.dump(metadata, stream, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return f"---\n{stream.getvalue()}---\n"


def parse_document(text: str) -> tuple[dict, str]:
    """Parse a Markdown document with YAML frontmatter. Returns (metadata, body)."""
    post = frontmatter.loads(text)
    return dict(post.metadata), post.content


def update_field(text: str, field: str, value) -> str:
    """Update a single frontmatter field in a document string."""
    metadata, body = parse_document(text)
    metadata[field] = value
    return generate_frontmatter(metadata) + "\n" + body
```

- [ ] **Step 5: Implement wikilink handler**

```python
# src/writer/wikilink.py
from __future__ import annotations

import re
from src.registry import Registry


def inject_wikilinks(text: str, registry: Registry) -> str:
    """Replace company/keyword names in text with [[wikilinks]]."""
    # Collect all replacement targets: (search_term, link_name)
    replacements: list[tuple[str, str]] = []

    for company in registry.companies:
        replacements.append((company.name, company.name))
        for alias in company.aliases:
            replacements.append((alias, company.name))

    for keyword in registry.keywords:
        replacements.append((keyword.name, keyword.name))
        for alias in keyword.aliases:
            replacements.append((alias, keyword.name))

    # Sort by length descending to match longer terms first
    replacements.sort(key=lambda x: len(x[0]), reverse=True)

    for search_term, link_name in replacements:
        # Skip if already wrapped in [[ ]]
        pattern = re.compile(
            r"(?<!\[\[)" + re.escape(search_term) + r"(?!\]\])",
            re.IGNORECASE,
        )
        text = pattern.sub(f"[[{link_name}]]", text, count=0)

    return text
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_frontmatter.py tests/test_wikilink.py -v`
Expected: 5 passed

- [ ] **Step 7: Commit**

```bash
git add src/writer/ tests/test_frontmatter.py tests/test_wikilink.py
git commit -m "feat: frontmatter and wikilink handlers for Obsidian Writer"
```

---

### Task 8: Vault Manager & Raw Writer

**Files:**
- Create: `src/writer/vault.py`
- Create: `src/writer/raw_writer.py`
- Create: `tests/test_vault.py`
- Create: `tests/test_raw_writer.py`

- [ ] **Step 1: Write failing tests for vault manager**

```python
# tests/test_vault.py
def test_vault_ensures_directories(tmp_path):
    from src.writer.vault import VaultManager

    vault = VaultManager(tmp_path / "vault")

    assert (tmp_path / "vault" / "companies").is_dir()
    assert (tmp_path / "vault" / "topics").is_dir()
    assert (tmp_path / "vault" / "raw").is_dir()
    assert (tmp_path / "vault" / "weekly").is_dir()
    assert (tmp_path / "vault" / "assets").is_dir()
    assert (tmp_path / "vault" / "registry").is_dir()


def test_vault_raw_dir_for_date(tmp_path):
    from src.writer.vault import VaultManager

    vault = VaultManager(tmp_path / "vault")
    raw_dir = vault.raw_dir_for_date("2026-04-08")

    assert raw_dir == tmp_path / "vault" / "raw" / "2026-04-08"
    assert raw_dir.is_dir()
```

- [ ] **Step 2: Write failing tests for raw writer**

```python
# tests/test_raw_writer.py
from datetime import datetime, timezone


def test_write_raw_article(tmp_path):
    from src.writer.vault import VaultManager
    from src.writer.raw_writer import RawWriter

    vault = VaultManager(tmp_path / "vault")
    writer = RawWriter(vault)

    article = {
        "id": "article-001",
        "title": "Test Article",
        "source": {
            "type": "news",
            "name": "TechCrunch",
            "url": "https://example.com/article",
            "author": "John Doe",
        },
        "collected_at": "2026-04-08T14:30:00Z",
        "published_at": "2026-04-08T12:00:00Z",
        "language": "en",
        "companies": ["[[NVIDIA]]"],
        "tags": ["world-model"],
        "reliability": 0.7,
        "content_type": "article",
        "body": "NVIDIA announced a new platform for [[World Models]].",
    }

    path = writer.write(article, date="2026-04-08")

    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "title: Test Article" in content
    assert "[[NVIDIA]]" in content
    assert "[[World Models]]" in content
    assert "id: article-001" in content
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_vault.py tests/test_raw_writer.py -v`
Expected: FAIL

- [ ] **Step 4: Implement vault manager**

```python
# src/writer/vault.py
from __future__ import annotations

from pathlib import Path


VAULT_SUBDIRS = ["companies", "topics", "raw", "weekly", "assets", "registry"]


class VaultManager:
    def __init__(self, vault_path: Path):
        self.vault_path = vault_path
        self._ensure_directories()

    def _ensure_directories(self):
        for subdir in VAULT_SUBDIRS:
            (self.vault_path / subdir).mkdir(parents=True, exist_ok=True)

    def raw_dir_for_date(self, date: str) -> Path:
        """Get or create raw directory for a specific date (YYYY-MM-DD)."""
        raw_dir = self.vault_path / "raw" / date
        raw_dir.mkdir(parents=True, exist_ok=True)
        return raw_dir

    @property
    def companies_dir(self) -> Path:
        return self.vault_path / "companies"

    @property
    def topics_dir(self) -> Path:
        return self.vault_path / "topics"

    @property
    def weekly_dir(self) -> Path:
        return self.vault_path / "weekly"

    @property
    def assets_dir(self) -> Path:
        return self.vault_path / "assets"

    @property
    def registry_dir(self) -> Path:
        return self.vault_path / "registry"
```

- [ ] **Step 5: Implement raw writer**

```python
# src/writer/raw_writer.py
from __future__ import annotations

from pathlib import Path

from src.writer.frontmatter import generate_frontmatter
from src.writer.vault import VaultManager


class RawWriter:
    def __init__(self, vault: VaultManager):
        self._vault = vault

    def write(self, article: dict, date: str) -> Path:
        """Write a raw article to vault/raw/{date}/{id}.md"""
        raw_dir = self._vault.raw_dir_for_date(date)
        article_id = article["id"]
        body = article.pop("body", "")

        # Build frontmatter metadata (everything except body)
        metadata = {k: v for k, v in article.items()}

        content = generate_frontmatter(metadata) + "\n" + body + "\n"

        path = raw_dir / f"{article_id}.md"
        path.write_text(content, encoding="utf-8")
        return path
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_vault.py tests/test_raw_writer.py -v`
Expected: 3 passed

- [ ] **Step 7: Commit**

```bash
git add src/writer/vault.py src/writer/raw_writer.py tests/test_vault.py tests/test_raw_writer.py
git commit -m "feat: vault manager and raw writer for Obsidian"
```

---

### Task 9: Profile Writer & Weekly Writer

**Files:**
- Create: `src/writer/profile_writer.py`
- Create: `src/writer/weekly_writer.py`
- Create: `tests/test_profile_writer.py`
- Create: `tests/test_weekly_writer.py`

- [ ] **Step 1: Write failing tests for profile writer**

```python
# tests/test_profile_writer.py
def test_create_company_profile(tmp_path):
    from src.writer.vault import VaultManager
    from src.writer.profile_writer import ProfileWriter

    vault = VaultManager(tmp_path / "vault")
    writer = ProfileWriter(vault)

    writer.create_company(
        name="NVIDIA",
        aliases=["엔비디아", "Jensen Huang"],
    )

    path = vault.companies_dir / "NVIDIA.md"
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "aliases:" in content
    assert "엔비디아" in content
    assert "## 회사 개요" in content
    assert "## 최근 동향" in content


def test_create_topic_profile(tmp_path):
    from src.writer.vault import VaultManager
    from src.writer.profile_writer import ProfileWriter

    vault = VaultManager(tmp_path / "vault")
    writer = ProfileWriter(vault)

    writer.create_topic(
        name="World Models",
        aliases=["world model", "월드 모델"],
    )

    path = vault.topics_dir / "World Models.md"
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "## 개요" in content
    assert "## 주요 플레이어" in content


def test_read_profile(tmp_path):
    from src.writer.vault import VaultManager
    from src.writer.profile_writer import ProfileWriter

    vault = VaultManager(tmp_path / "vault")
    writer = ProfileWriter(vault)
    writer.create_company(name="NVIDIA", aliases=["엔비디아"])

    metadata, body = writer.read_company("NVIDIA")

    assert "엔비디아" in metadata["aliases"]
    assert "## 회사 개요" in body


def test_update_profile(tmp_path):
    from src.writer.vault import VaultManager
    from src.writer.profile_writer import ProfileWriter

    vault = VaultManager(tmp_path / "vault")
    writer = ProfileWriter(vault)
    writer.create_company(name="NVIDIA", aliases=["엔비디아"])

    new_body = """## 회사 개요
GPU 및 AI 컴퓨팅 플랫폼 기업.

## 최근 동향
- 2026-W15: GR00T 2.0 발표

## 기술 스택
Cosmos, Isaac, GR00T

## 파트너십 / 생태계
[[Boston Dynamics]]와 협력

## 전망 / 시사점
로보틱스 생태계 핵심 인프라 역할 강화

---

## 기타 노트
"""

    writer.update_company("NVIDIA", new_body)
    _, body = writer.read_company("NVIDIA")

    assert "GR00T 2.0 발표" in body
    assert "[[Boston Dynamics]]" in body
```

- [ ] **Step 2: Write failing tests for weekly writer**

```python
# tests/test_weekly_writer.py
def test_write_consolidated(tmp_path):
    from src.writer.vault import VaultManager
    from src.writer.weekly_writer import WeeklyWriter

    vault = VaultManager(tmp_path / "vault")
    writer = WeeklyWriter(vault)

    writer.write_consolidated(
        week="2026-W15",
        date_range="2026-04-06 ~ 2026-04-12",
        content="## NVIDIA\n- GR00T 2.0 발표\n\n## Figure AI\n- 시리즈 B 유치",
    )

    path = vault.weekly_dir / "2026-W15-consolidated.md"
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "period: 2026-W15" in content
    assert "GR00T 2.0" in content


def test_write_snapshot(tmp_path):
    from src.writer.vault import VaultManager
    from src.writer.weekly_writer import WeeklyWriter

    vault = VaultManager(tmp_path / "vault")
    writer = WeeklyWriter(vault)

    writer.write_snapshot(
        week="2026-W15",
        date_range="2026-04-06 ~ 2026-04-12",
        content="## 주요 하이라이트\n- GR00T 2.0 발표",
    )

    path = vault.weekly_dir / "2026-W15.md"
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "weekly" in content
    assert "주요 하이라이트" in content


def test_append_review_comment(tmp_path):
    from src.writer.vault import VaultManager
    from src.writer.weekly_writer import WeeklyWriter

    vault = VaultManager(tmp_path / "vault")
    writer = WeeklyWriter(vault)
    writer.write_snapshot(
        week="2026-W15",
        date_range="2026-04-06 ~ 2026-04-12",
        content="## 주요 하이라이트\n- Test",
    )

    writer.append_review("2026-W15", "검토 결과: 누락 사항 없음")

    content = (vault.weekly_dir / "2026-W15.md").read_text(encoding="utf-8")
    assert "검토 결과: 누락 사항 없음" in content
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_profile_writer.py tests/test_weekly_writer.py -v`
Expected: FAIL

- [ ] **Step 4: Implement profile writer**

```python
# src/writer/profile_writer.py
from __future__ import annotations

from pathlib import Path

from src.writer.frontmatter import generate_frontmatter, parse_document
from src.writer.vault import VaultManager

COMPANY_TEMPLATE = """## 회사 개요


## 최근 동향


## 기술 스택


## 파트너십 / 생태계


## 전망 / 시사점


---

## 기타 노트
"""

TOPIC_TEMPLATE = """## 개요


## 주요 플레이어


## 최근 동향


## 핵심 논문 / 레퍼런스


## 시사점


---

## 기타 노트
"""


class ProfileWriter:
    def __init__(self, vault: VaultManager):
        self._vault = vault

    def create_company(self, name: str, aliases: list[str]) -> Path:
        metadata = {"aliases": [name] + aliases, "tags": ["company"]}
        content = generate_frontmatter(metadata) + "\n" + COMPANY_TEMPLATE
        path = self._vault.companies_dir / f"{name}.md"
        path.write_text(content, encoding="utf-8")
        return path

    def create_topic(self, name: str, aliases: list[str]) -> Path:
        metadata = {"aliases": [name] + aliases, "tags": ["topic"]}
        content = generate_frontmatter(metadata) + "\n" + TOPIC_TEMPLATE
        path = self._vault.topics_dir / f"{name}.md"
        path.write_text(content, encoding="utf-8")
        return path

    def read_company(self, name: str) -> tuple[dict, str]:
        path = self._vault.companies_dir / f"{name}.md"
        return parse_document(path.read_text(encoding="utf-8"))

    def read_topic(self, name: str) -> tuple[dict, str]:
        path = self._vault.topics_dir / f"{name}.md"
        return parse_document(path.read_text(encoding="utf-8"))

    def update_company(self, name: str, new_body: str) -> None:
        path = self._vault.companies_dir / f"{name}.md"
        metadata, _ = parse_document(path.read_text(encoding="utf-8"))
        content = generate_frontmatter(metadata) + "\n" + new_body
        path.write_text(content, encoding="utf-8")

    def update_topic(self, name: str, new_body: str) -> None:
        path = self._vault.topics_dir / f"{name}.md"
        metadata, _ = parse_document(path.read_text(encoding="utf-8"))
        content = generate_frontmatter(metadata) + "\n" + new_body
        path.write_text(content, encoding="utf-8")
```

- [ ] **Step 5: Implement weekly writer**

```python
# src/writer/weekly_writer.py
from __future__ import annotations

from pathlib import Path

from src.writer.frontmatter import generate_frontmatter
from src.writer.vault import VaultManager


class WeeklyWriter:
    def __init__(self, vault: VaultManager):
        self._vault = vault

    def write_consolidated(self, week: str, date_range: str, content: str) -> Path:
        metadata = {
            "period": week,
            "date_range": date_range,
            "tags": ["weekly", "consolidated"],
        }
        doc = generate_frontmatter(metadata) + "\n" + content + "\n"
        path = self._vault.weekly_dir / f"{week}-consolidated.md"
        path.write_text(doc, encoding="utf-8")
        return path

    def write_snapshot(self, week: str, date_range: str, content: str) -> Path:
        metadata = {
            "period": week,
            "date_range": date_range,
            "tags": ["weekly"],
        }
        doc = generate_frontmatter(metadata) + "\n" + content + "\n"
        path = self._vault.weekly_dir / f"{week}.md"
        path.write_text(doc, encoding="utf-8")
        return path

    def append_review(self, week: str, review_content: str) -> None:
        path = self._vault.weekly_dir / f"{week}.md"
        existing = path.read_text(encoding="utf-8")
        updated = existing.rstrip() + "\n\n---\n\n## GPT5 Pro 검토\n\n" + review_content + "\n"
        path.write_text(updated, encoding="utf-8")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_profile_writer.py tests/test_weekly_writer.py -v`
Expected: 7 passed

- [ ] **Step 7: Commit**

```bash
git add src/writer/profile_writer.py src/writer/weekly_writer.py tests/test_profile_writer.py tests/test_weekly_writer.py
git commit -m "feat: profile writer and weekly writer for Obsidian"
```

---

## Phase 4: Collection Pipeline

### Task 10: Source Base Class

**Files:**
- Create: `src/sources/__init__.py`
- Create: `src/sources/base.py`
- Create: `tests/test_source_base.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_source_base.py
import pytest


def test_source_module_interface():
    from src.sources.base import BaseSource, CollectedItem

    class TestSource(BaseSource):
        source_type = "test"

        def fetch(self, company_id: str, keywords: list[str]) -> list[CollectedItem]:
            return [
                CollectedItem(
                    title="Test Article",
                    url="https://example.com/1",
                    body="Body text",
                    source_type=self.source_type,
                    source_name="TestSource",
                    author="Author",
                    published_at="2026-04-08T12:00:00Z",
                    language="en",
                    content_type="article",
                )
            ]

    source = TestSource()
    items = source.fetch("nvidia", ["world-model"])

    assert len(items) == 1
    assert items[0].title == "Test Article"
    assert items[0].source_type == "test"


def test_cannot_instantiate_base_source():
    from src.sources.base import BaseSource

    with pytest.raises(TypeError):
        BaseSource()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_source_base.py -v`
Expected: FAIL

- [ ] **Step 3: Implement source base class**

```python
# src/sources/__init__.py
```

```python
# src/sources/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CollectedItem:
    title: str
    url: str
    body: str
    source_type: str          # news | paper | sns | official | github | blog | video
    source_name: str          # e.g., "TechCrunch", "arXiv"
    author: str | None
    published_at: str | None  # ISO 8601
    language: str | None
    content_type: str         # article | abstract | thread | release | commit | post | demo
    channel: str | None = None          # YouTube channel
    has_visual_analysis: bool = False


class BaseSource(ABC):
    source_type: str  # Must be set by subclass

    @abstractmethod
    def fetch(self, company_id: str, keywords: list[str]) -> list[CollectedItem]:
        """Fetch items for a given company/keyword combination. Returns raw collected items."""
        ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_source_base.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/sources/ tests/test_source_base.py
git commit -m "feat: abstract base class for source modules"
```

---

### Task 11: RSS Source Module

**Files:**
- Create: `src/sources/rss.py`
- Create: `tests/test_source_rss.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_source_rss.py
def test_rss_source_parses_feed(monkeypatch):
    from src.sources.rss import RssSource
    from src.sources.base import CollectedItem

    sample_feed = {
        "entries": [
            {
                "title": "NVIDIA GR00T 2.0 Launch",
                "link": "https://blogs.nvidia.com/groot-2",
                "summary": "NVIDIA launches GR00T 2.0 for humanoid robots.",
                "author": "NVIDIA Blog",
                "published": "Wed, 08 Apr 2026 12:00:00 GMT",
            },
            {
                "title": "Unrelated Post",
                "link": "https://blogs.nvidia.com/gaming",
                "summary": "New GPU for gaming.",
                "author": "NVIDIA Blog",
                "published": "Wed, 08 Apr 2026 10:00:00 GMT",
            },
        ]
    }

    import feedparser
    monkeypatch.setattr(feedparser, "parse", lambda url: sample_feed)

    source = RssSource()
    items = source.fetch_from_url("https://blogs.nvidia.com/feed/")

    assert len(items) == 2
    assert items[0].title == "NVIDIA GR00T 2.0 Launch"
    assert items[0].source_type == "news"
    assert items[0].url == "https://blogs.nvidia.com/groot-2"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_source_rss.py -v`
Expected: FAIL

- [ ] **Step 3: Implement RSS source**

```python
# src/sources/rss.py
from __future__ import annotations

import feedparser
from email.utils import parsedate_to_datetime

from src.sources.base import BaseSource, CollectedItem


class RssSource(BaseSource):
    source_type = "news"

    def fetch(self, company_id: str, keywords: list[str]) -> list[CollectedItem]:
        """Not used directly — use fetch_from_url for RSS sources."""
        return []

    def fetch_from_url(self, feed_url: str) -> list[CollectedItem]:
        """Fetch and parse an RSS feed URL."""
        feed = feedparser.parse(feed_url)
        items = []

        for entry in feed.get("entries", []):
            published_at = None
            if "published" in entry:
                try:
                    dt = parsedate_to_datetime(entry["published"])
                    published_at = dt.isoformat()
                except (ValueError, TypeError):
                    published_at = entry.get("published")

            items.append(
                CollectedItem(
                    title=entry.get("title", ""),
                    url=entry.get("link", ""),
                    body=entry.get("summary", ""),
                    source_type=self.source_type,
                    source_name=feed_url,
                    author=entry.get("author"),
                    published_at=published_at,
                    language=None,
                    content_type="article",
                )
            )

        return items
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_source_rss.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add src/sources/rss.py tests/test_source_rss.py
git commit -m "feat: RSS source module"
```

---

### Task 12: Web Page, SNS, YouTube Source Modules

**Files:**
- Create: `src/sources/web.py`
- Create: `src/sources/sns.py`
- Create: `src/sources/youtube.py`
- Create: `tests/test_source_web.py`
- Create: `tests/test_source_sns.py`
- Create: `tests/test_source_youtube.py`

These modules follow the same BaseSource pattern. Web and SNS make HTTP calls, YouTube uses yt-dlp for transcripts. The actual content extraction for web pages is delegated to the LLM Gateway (Agent), so the source module only handles HTTP fetching.

- [ ] **Step 1: Write failing test for web source**

```python
# tests/test_source_web.py
def test_web_source_fetches_html(monkeypatch):
    from src.sources.web import WebSource

    class MockResponse:
        status_code = 200
        text = "<html><body><h1>Press Release</h1><p>Figure AI raises $500M.</p></body></html>"

    monkeypatch.setattr("httpx.get", lambda url, **kwargs: MockResponse())

    source = WebSource()
    items = source.fetch_from_url("https://figure.ai/news/series-b")

    assert len(items) == 1
    assert "<html>" in items[0].body  # Raw HTML, Agent will extract
    assert items[0].source_type == "web"
    assert items[0].content_type == "raw_html"
```

- [ ] **Step 2: Write failing test for SNS source**

```python
# tests/test_source_sns.py
def test_sns_source_placeholder():
    from src.sources.sns import SnsSource

    source = SnsSource()
    # SNS requires API keys; test the interface exists
    items = source.fetch("nvidia", ["world-model"])

    assert isinstance(items, list)
```

- [ ] **Step 3: Write failing test for YouTube source**

```python
# tests/test_source_youtube.py
def test_youtube_source_fetches_transcript(monkeypatch):
    from src.sources.youtube import YoutubeSource

    mock_transcript = "Hello everyone. Today we're announcing GR00T 2.0."

    monkeypatch.setattr(
        "src.sources.youtube.extract_transcript",
        lambda video_url: mock_transcript,
    )

    source = YoutubeSource()
    items = source.fetch_from_url("https://youtube.com/watch?v=abc123", channel="NVIDIA")

    assert len(items) == 1
    assert "GR00T 2.0" in items[0].body
    assert items[0].source_type == "video"
    assert items[0].channel == "NVIDIA"
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `pytest tests/test_source_web.py tests/test_source_sns.py tests/test_source_youtube.py -v`
Expected: FAIL

- [ ] **Step 5: Implement web source**

```python
# src/sources/web.py
from __future__ import annotations

import httpx

from src.sources.base import BaseSource, CollectedItem


class WebSource(BaseSource):
    source_type = "web"

    def fetch(self, company_id: str, keywords: list[str]) -> list[CollectedItem]:
        return []

    def fetch_from_url(self, url: str) -> list[CollectedItem]:
        """Fetch raw HTML from a URL. Content extraction is handled by Agent."""
        response = httpx.get(url, follow_redirects=True, timeout=30)
        if response.status_code != 200:
            return []

        return [
            CollectedItem(
                title="",  # Agent will extract
                url=url,
                body=response.text,  # Raw HTML for Agent
                source_type=self.source_type,
                source_name=url,
                author=None,
                published_at=None,
                language=None,
                content_type="raw_html",  # Marks as unprocessed
            )
        ]
```

- [ ] **Step 6: Implement SNS source**

```python
# src/sources/sns.py
from __future__ import annotations

from src.sources.base import BaseSource, CollectedItem


class SnsSource(BaseSource):
    source_type = "sns"

    def fetch(self, company_id: str, keywords: list[str]) -> list[CollectedItem]:
        """SNS fetch requires API keys configured per platform.
        Returns empty list if no API is configured.
        Platforms: X/Twitter, Reddit, HackerNews.
        """
        # Placeholder: actual API integration depends on available keys
        # Each platform will be a method: fetch_reddit, fetch_hackernews, etc.
        return []

    def fetch_reddit(self, subreddit: str, query: str) -> list[CollectedItem]:
        """Fetch posts from Reddit matching query."""
        import httpx

        url = f"https://www.reddit.com/r/{subreddit}/search.json"
        params = {"q": query, "sort": "new", "limit": 25, "restrict_sr": "on"}
        headers = {"User-Agent": "market-intel/0.1"}

        response = httpx.get(url, params=params, headers=headers, timeout=30)
        if response.status_code != 200:
            return []

        items = []
        for post in response.json().get("data", {}).get("children", []):
            data = post["data"]
            items.append(
                CollectedItem(
                    title=data.get("title", ""),
                    url=f"https://reddit.com{data.get('permalink', '')}",
                    body=data.get("selftext", ""),
                    source_type=self.source_type,
                    source_name="Reddit",
                    author=data.get("author"),
                    published_at=None,
                    language="en",
                    content_type="post",
                )
            )
        return items
```

- [ ] **Step 7: Implement YouTube source**

```python
# src/sources/youtube.py
from __future__ import annotations

import subprocess
import json

from src.sources.base import BaseSource, CollectedItem


def extract_transcript(video_url: str) -> str:
    """Extract transcript from YouTube video using yt-dlp."""
    result = subprocess.run(
        ["yt-dlp", "--write-auto-sub", "--sub-lang", "en", "--skip-download",
         "--print", "%(subtitles)j", video_url],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        # Fallback: try to get auto-generated captions via yt-dlp subtitle extraction
        result = subprocess.run(
            ["yt-dlp", "--write-auto-sub", "--sub-lang", "en",
             "--sub-format", "txt", "--skip-download",
             "-o", "%(id)s", video_url],
            capture_output=True, text=True, timeout=60,
        )
    return result.stdout


class YoutubeSource(BaseSource):
    source_type = "video"

    def fetch(self, company_id: str, keywords: list[str]) -> list[CollectedItem]:
        return []

    def fetch_from_url(self, video_url: str, channel: str | None = None) -> list[CollectedItem]:
        """Fetch transcript from a YouTube video URL."""
        transcript = extract_transcript(video_url)
        if not transcript:
            return []

        return [
            CollectedItem(
                title="",  # Will be enriched by Agent or yt-dlp metadata
                url=video_url,
                body=transcript,
                source_type=self.source_type,
                source_name="YouTube",
                author=None,
                published_at=None,
                language=None,
                content_type="transcript",
                channel=channel,
            )
        ]
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `pytest tests/test_source_web.py tests/test_source_sns.py tests/test_source_youtube.py -v`
Expected: 3 passed

- [ ] **Step 9: Commit**

```bash
git add src/sources/web.py src/sources/sns.py src/sources/youtube.py tests/test_source_web.py tests/test_source_sns.py tests/test_source_youtube.py
git commit -m "feat: web, SNS, and YouTube source modules"
```

---

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_collector_pipeline.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/collector/ tests/test_collector_pipeline.py
git commit -m "feat: collection pipeline orchestrator with tagging and dedup"
```

---

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
        """Read all raw files within the date range."""
        raw_dir = self._vault.vault_path / "raw"
        if not raw_dir.exists():
            return "(No raw data found)"

        all_content = []
        for date_dir in sorted(raw_dir.iterdir()):
            if not date_dir.is_dir():
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_consolidator.py -v`
Expected: 1 passed

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

        # 2. Branch from checkpoint (carries Step 1 context)
        session = Session(
            gateway=self._gateway,
            model=self._model,
            system=checkpoint.system,
        )
        session.history = list(checkpoint.history)  # Restore checkpoint history

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

---

## Phase 6: Integration & Entry Point

### Task 18: Main Entry Point & Vault Initialization

**Files:**
- Create: `src/main.py`

- [ ] **Step 1: Create main entry point**

```python
# src/main.py
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from src.config import load_config
from src.registry import Registry
from src.dedup import UrlDedup
from src.gateway.gateway import LLMGateway
from src.writer.vault import VaultManager
from src.writer.raw_writer import RawWriter
from src.writer.profile_writer import ProfileWriter
from src.collector.pipeline import CollectionPipeline
from src.refinery.pipeline import RefinementPipeline
from src.scheduler.scheduler import IntelScheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def setup_gateway(config) -> LLMGateway:
    """Initialize LLM Gateway with configured adapters."""
    gateway = LLMGateway()

    # Gemini (collection tagging)
    from google import genai
    from src.gateway.adapters.gemini import GeminiAdapter
    gemini_client = genai.Client(api_key=config.api_keys.gemini)
    gateway.register_adapter("gemini", GeminiAdapter(client=gemini_client, model_id="gemini-2.0-flash"))

    # OpenAI GPT5 Pro (consolidation + review)
    from openai import OpenAI
    from src.gateway.adapters.openai import OpenAIAdapter
    openai_client = OpenAI(api_key=config.api_keys.openai)
    gateway.register_adapter("gpt5-pro", OpenAIAdapter(client=openai_client, model_id="gpt-5-pro"))

    # Anthropic Claude (summarization)
    from anthropic import Anthropic
    from src.gateway.adapters.anthropic import AnthropicAdapter
    anthropic_client = Anthropic(api_key=config.api_keys.anthropic)
    gateway.register_adapter("claude-opus", AnthropicAdapter(client=anthropic_client, model_id="claude-opus-4-6"))

    return gateway


def init_vault(config, registry: Registry):
    """Initialize vault with company and topic profiles from registry."""
    vault = VaultManager(config.vault_path)
    profile_writer = ProfileWriter(vault)

    for company in registry.companies:
        path = vault.companies_dir / f"{company.name}.md"
        if not path.exists():
            profile_writer.create_company(company.name, company.aliases)
            logger.info(f"Created company profile: {company.name}")

    for keyword in registry.keywords:
        path = vault.topics_dir / f"{keyword.name}.md"
        if not path.exists():
            profile_writer.create_topic(keyword.name, keyword.aliases)
            logger.info(f"Created topic profile: {keyword.name}")


def main():
    parser = argparse.ArgumentParser(description="Physical AI Market Intelligence System")
    parser.add_argument("command", choices=["collect", "refine", "schedule", "init"],
                        help="collect: run one collection cycle, refine: run weekly refinement, schedule: start scheduler, init: initialize vault")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    parser.add_argument("--week", help="Week identifier for refinement (e.g., 2026-W15)")
    parser.add_argument("--date-range", help="Date range for refinement (e.g., 2026-04-06 ~ 2026-04-12)")
    args = parser.parse_args()

    config = load_config(Path(args.config))
    registry = Registry(config.vault_path / "registry")
    vault = VaultManager(config.vault_path)

    if args.command == "init":
        init_vault(config, registry)
        logger.info("Vault initialized")
        return

    gateway = setup_gateway(config)
    dedup = UrlDedup(Path("dedup.db"))
    raw_writer = RawWriter(vault)

    if args.command == "collect":
        pipeline = CollectionPipeline(
            gateway=gateway, tagging_model="gemini",
            registry=registry, dedup=dedup, raw_writer=raw_writer,
        )
        scheduler = IntelScheduler(config=config, registry=registry, pipeline=pipeline)
        scheduler.run_once()

    elif args.command == "refine":
        if not args.week or not args.date_range:
            parser.error("--week and --date-range are required for refine command")
        pipeline = RefinementPipeline(
            gateway=gateway,
            consolidation_model="gpt5-pro",
            summarization_model="claude-opus",
            review_model="gpt5-pro",
            vault=vault,
            registry=registry,
        )
        pipeline.run(week=args.week, date_range=args.date_range)

    elif args.command == "schedule":
        collection_pipeline = CollectionPipeline(
            gateway=gateway, tagging_model="gemini",
            registry=registry, dedup=dedup, raw_writer=raw_writer,
        )
        scheduler = IntelScheduler(config=config, registry=registry, pipeline=collection_pipeline)
        scheduler.start()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add src/main.py
git commit -m "feat: main entry point with CLI commands (collect, refine, schedule, init)"
```

---

## Usage

```bash
# 1. Vault 초기화 (Registry에서 회사/주제 프로필 자동 생성)
python -m src.main init --config config.yaml

# 2. 수집 1회 실행
python -m src.main collect --config config.yaml

# 3. 주간 정제 실행
python -m src.main refine --config config.yaml --week 2026-W15 --date-range "2026-04-06 ~ 2026-04-12"

# 4. 스케줄러 시작 (백그라운드 수집)
python -m src.main schedule --config config.yaml
```
