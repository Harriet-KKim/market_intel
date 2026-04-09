# 01. Config & Project Setup — 구현 계획

> 이 파일은 전체 구현 플랜의 일부입니다.
> 인덱스: [README.md](./README.md) · 원본 통합본: [../superpowers/plans/2026-04-09-market-intel-implementation.md](../superpowers/plans/2026-04-09-market-intel-implementation.md) · 설계 스펙: [../superpowers/specs/2026-04-09-market-intel-system-design.md](../superpowers/specs/2026-04-09-market-intel-system-design.md)

**모듈:** `src/config.py` (+ `pyproject.toml`, `config.yaml`)
**역할:** YAML 기반 전역 설정 로딩, `${ENV_VAR}` 치환, 프로젝트 부트스트랩
**선행 의존:** 없음 (첫 번째 태스크)
**다음 단계:** [02-registry.md](./02-registry.md)

---

## Phase 1: Foundation

### Task 1: Project Setup & Config

**Files:**
- Create: `pyproject.toml`
- Create: `config.yaml`
- Create: `src/__init__.py`
- Create: `src/config.py`
- Create: `tests/__init__.py`
- Create: `tests/test_config.py`

> 📝 **로컬 패치 C3:** 원본 플랜에는 이 목록에 `tests/conftest.py`도 포함돼 있었으나, 실제 `conftest.py` 생성·`sample_registry_dir` fixture 정의는 **Task 2(`02-registry.md`)** 에서 이뤄집니다. 중복·순서 혼란을 피하기 위해 여기선 제외했습니다. Task 2 이전에는 `tests/conftest.py`를 만들지 마세요.

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
# 로컬 패치 C1: 원본 플랜은 "setuptools.backends._legacy:_Backend"로 지정돼 있어
# `pip install -e .`이 ModuleNotFoundError로 실패했습니다. 공식 backend로 교체.
build-backend = "setuptools.build_meta"

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
