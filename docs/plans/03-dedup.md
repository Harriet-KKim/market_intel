# 03. URL Dedup Store — 구현 계획

> 이 파일은 전체 구현 플랜의 일부입니다.
> 인덱스: [README.md](./README.md) · 원본 통합본: [../superpowers/plans/2026-04-09-market-intel-implementation.md](../superpowers/plans/2026-04-09-market-intel-implementation.md) · 설계 스펙: [../superpowers/specs/2026-04-09-market-intel-system-design.md](../superpowers/specs/2026-04-09-market-intel-system-design.md)

**모듈:** `src/dedup.py`
**역할:** SQLite 기반 URL 중복 체크 (수집 파이프라인에서 사용)
**설계 원칙:** URL 일치만 체크. 내용 기반 dedup은 주간 정제 모델이 담당.
**선행 의존:** [01-config.md](./01-config.md)
**다음 단계:** [04-gateway.md](./04-gateway.md)

---

## Phase 1: Foundation

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
