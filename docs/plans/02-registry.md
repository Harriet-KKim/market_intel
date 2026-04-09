# 02. Registry — 구현 계획

> 이 파일은 전체 구현 플랜의 일부입니다.
> 인덱스: [README.md](./README.md) · 원본 통합본: [../superpowers/plans/2026-04-09-market-intel-implementation.md](../superpowers/plans/2026-04-09-market-intel-implementation.md) · 설계 스펙: [../superpowers/specs/2026-04-09-market-intel-system-design.md](../superpowers/specs/2026-04-09-market-intel-system-design.md)

**모듈:** `src/registry.py`
**역할:** 회사/키워드/소스 평판 레지스트리 로딩, 텍스트 매칭(회사/키워드 ID 추출)
**레지스트리 파일 위치:** `vault/registry/{companies,keywords,source_reputation}.yaml`
**선행 의존:** [01-config.md](./01-config.md)
**다음 단계:** [03-dedup.md](./03-dedup.md)

---

## Phase 1: Foundation

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
