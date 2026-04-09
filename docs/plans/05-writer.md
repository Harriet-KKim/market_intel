# 05. Obsidian Writer — 구현 계획

> 이 파일은 전체 구현 플랜의 일부입니다.
> 인덱스: [README.md](./README.md) · 원본 통합본: [../superpowers/plans/2026-04-09-market-intel-implementation.md](../superpowers/plans/2026-04-09-market-intel-implementation.md) · 설계 스펙: [../superpowers/specs/2026-04-09-market-intel-system-design.md](../superpowers/specs/2026-04-09-market-intel-system-design.md)

**모듈:** `src/writer/` (frontmatter, wikilink, vault, raw_writer, profile_writer, weekly_writer)
**역할:** Obsidian Vault 파일 CRUD, frontmatter/wikilink 유틸, 회사·주제·주간 문서 템플릿 적용
**핵심 설계 포인트:**
- `inject_wikilinks`는 registry alias 기반으로 가장 긴 문자열부터 치환 (부분 매칭 방지). 이미 `[[ ]]`로 감싸진 토큰은 재치환하지 않음.
- `ProfileWriter.update_*`는 기존 frontmatter를 보존하고 body만 교체. 고정 섹션 구조(`## 회사 개요`, `## 최근 동향`, ...)는 호출자(= Summarizer)가 책임짐.
- `WeeklyWriter.append_review`는 주간 스냅샷 하단에 `## GPT5 Pro 검토` 섹션을 덧붙임.

**선행 의존:** [02-registry.md](./02-registry.md) (wikilink에서 사용)
**공용 fixture:** `sample_registry_dir` — `tests/conftest.py` (Task 2에서 생성). Task 7의 `test_inject_wikilinks`가 이 fixture를 사용합니다. Task 2를 먼저 완료해야 이 파일의 테스트를 돌릴 수 있습니다.
**다음 단계:** [06-sources.md](./06-sources.md)

포함 태스크:
- [Task 7: Frontmatter & WikiLink Handlers](#task-7-frontmatter--wikilink-handlers)
- [Task 8: Vault Manager & Raw Writer](#task-8-vault-manager--raw-writer)
- [Task 9: Profile Writer & Weekly Writer](#task-9-profile-writer--weekly-writer)

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
