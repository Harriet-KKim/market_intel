# 06. Source Modules — 구현 계획

> 이 파일은 전체 구현 플랜의 일부입니다.
> 인덱스: [README.md](./README.md) · 원본 통합본: [../superpowers/plans/2026-04-09-market-intel-implementation.md](../superpowers/plans/2026-04-09-market-intel-implementation.md) · 설계 스펙: [../superpowers/specs/2026-04-09-market-intel-system-design.md](../superpowers/specs/2026-04-09-market-intel-system-design.md)

**모듈:** `src/sources/` (base, rss, web, sns, youtube)
**역할:** 플러그인 구조의 소스별 수집 모듈. 각 소스는 `BaseSource`를 상속하고 `CollectedItem` 리스트를 반환.
**핵심 설계 포인트:**
- **역할 분담**: RSS/SNS/YouTube는 Script가 fetch·파싱·메타데이터까지 처리하고 태깅만 Agent에 위임. Web은 HTML 구조가 다양하므로 Script가 raw HTML만 가져오고 본문 추출·태깅을 Agent가 한 번에 처리 (`content_type: "raw_html"`로 표시).
- **확장**: 새 소스 추가 시 `src/sources/` 하위에 새 파일 + config 등록만 필요.
- YouTube는 기본 Transcript 수집, Multimodal 분석은 Agent가 "시각 분석 필요" 판단 시 키프레임 추출 후 수행 (선택적).

**선행 의존:** 없음 (LLM Gateway와 독립적으로 작동하며, 태깅은 [07-collector.md](./07-collector.md)에서 결합)
**다음 단계:** [07-collector.md](./07-collector.md)

> ✅ **K1 해결 (로컬 패치):** 원본 플랜은 `RssSource.fetch_from_url()`에서 `source_name=feed_url`로 세팅해 `CollectionPipeline._tag_item`의 `registry.get_reputation_score(source_name)`가 항상 fallback(=None)을 반환했습니다. 이제 `feed.feed.get("title")` → `urlparse(feed_url).netloc` → `feed_url` 순서로 폴백합니다. Reuters/TechCrunch 같은 평판 tier가 정상 매칭되도록 feed title이 1순위이고, title이 없는 피드는 도메인(예: `blogs.nvidia.com`)으로 기록됩니다. `source_reputation.yaml`을 운영할 때는 tier 항목도 title 또는 netloc 기준으로 채우세요. 테스트: `test_rss_source_parses_feed`가 `source_name == "NVIDIA Blog"`를 확인합니다.
>
> ⚠️ **알려진 이슈 P2 (해결):** 원본 플랜의 `extract_transcript`는 `yt-dlp --print "%(subtitles)j"`로 자막 메타데이터 JSON만 출력해서 실제 transcript 텍스트를 얻지 못하는 버그가 있었습니다. VTT 다운로드 + 파싱 헬퍼(`_parse_vtt`)로 재작성되었습니다. 테스트는 VTT 파싱 로직을 직접 검증합니다.

포함 태스크:
- [Task 10: Source Base Class](#task-10-source-base-class)
- [Task 11: RSS Source Module](#task-11-rss-source-module)
- [Task 12: Web Page, SNS, YouTube Source Modules](#task-12-web-page-sns-youtube-source-modules)

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

    # feedparser.parse는 FeedParserDict를 반환. `.feed` 어트리뷰트와 `.get`을
    # 둘 다 지원해야 해서 간단한 mock 클래스로 흉내냅니다.
    class MockFeedResult:
        feed = {"title": "NVIDIA Blog"}
        _entries = [
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
        def get(self, key, default=None):
            if key == "entries":
                return self._entries
            return default

    import feedparser
    monkeypatch.setattr(feedparser, "parse", lambda url: MockFeedResult())

    source = RssSource()
    items = source.fetch_from_url("https://blogs.nvidia.com/feed/")

    assert len(items) == 2
    assert items[0].title == "NVIDIA GR00T 2.0 Launch"
    assert items[0].source_type == "news"
    assert items[0].url == "https://blogs.nvidia.com/groot-2"
    # 로컬 패치 K1 해결: source_name이 feed title로 세팅되어야 함 (URL이 아님).
    # 이 값이 registry.get_reputation_score()로 tier 점수를 조회하는 키가 됩니다.
    assert items[0].source_name == "NVIDIA Blog"


def test_rss_source_fallback_to_domain(monkeypatch):
    """feed.title이 없으면 도메인으로 폴백해야 한다."""
    from src.sources.rss import RssSource

    class NoTitleFeed:
        feed = {}  # title 없음
        _entries = [{"title": "X", "link": "https://example.com/a", "summary": ""}]
        def get(self, key, default=None):
            return self._entries if key == "entries" else default

    import feedparser
    monkeypatch.setattr(feedparser, "parse", lambda url: NoTitleFeed())

    items = RssSource().fetch_from_url("https://example.com/feed.xml")
    assert items[0].source_name == "example.com"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_source_rss.py -v`
Expected: FAIL

- [ ] **Step 3: Implement RSS source**

```python
# src/sources/rss.py
from __future__ import annotations

from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import feedparser

from src.sources.base import BaseSource, CollectedItem


class RssSource(BaseSource):
    source_type = "news"

    def fetch(self, company_id: str, keywords: list[str]) -> list[CollectedItem]:
        """Not used directly — use fetch_from_url for RSS sources."""
        return []

    def fetch_from_url(self, feed_url: str) -> list[CollectedItem]:
        """Fetch and parse an RSS feed URL."""
        feed = feedparser.parse(feed_url)

        # 로컬 패치 K1 해결: source_name을 feed title로 폴백.
        # 원본 플랜은 source_name=feed_url로 저장해서 registry.get_reputation_score()
        # 가 항상 fallback(None)을 반환했습니다. feed.feed.title이 1순위,
        # 없으면 도메인(netloc), 최후 fallback은 feed_url 그대로.
        feed_meta = getattr(feed, "feed", {}) or {}
        feed_title = feed_meta.get("title") if hasattr(feed_meta, "get") else None
        source_name = feed_title or urlparse(feed_url).netloc or feed_url

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
                    source_name=source_name,
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
Expected: 2 passed

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


def test_parse_vtt_extracts_cue_text():
    """로컬 패치 P2: VTT 파싱 로직을 직접 검증.
    기존 플랜은 extract_transcript 전체를 monkeypatch로 대체해서 VTT 파싱이
    실제로 동작하는지 검증하지 못했고, 구현도 --print 플래그로 메타데이터만
    출력하는 버그가 있었습니다. 새 _parse_vtt 헬퍼는 단위 테스트로 고정합니다."""
    from src.sources.youtube import _parse_vtt

    vtt = """WEBVTT
Kind: captions
Language: en

00:00:00.000 --> 00:00:03.000
Hello everyone.

00:00:03.000 --> 00:00:06.000
Today we're announcing <c>GR00T 2.0</c>.

00:00:06.000 --> 00:00:09.000
It's a humanoid platform.
"""
    result = _parse_vtt(vtt)
    assert "Hello everyone." in result
    assert "GR00T 2.0" in result
    assert "humanoid platform" in result
    # 헤더/메타데이터/타이밍/HTML 태그는 모두 제거되어야 한다
    assert "WEBVTT" not in result
    assert "Kind:" not in result
    assert "Language:" not in result
    assert "-->" not in result
    assert "<c>" not in result
    assert "</c>" not in result
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

import re
import subprocess
import tempfile
from pathlib import Path

from src.sources.base import BaseSource, CollectedItem


def extract_transcript(video_url: str) -> str:
    """Download auto-generated subtitles via yt-dlp and return transcript text.

    로컬 패치 P2: 원본 플랜은 `--print "%(subtitles)j"`로 자막 *메타데이터* JSON만
    출력하고 실제 큐 텍스트를 얻지 못했습니다. 수정본은 임시 디렉터리에 VTT
    파일을 내려받고 `_parse_vtt`로 본문만 추출합니다. 실패 시 빈 문자열 반환.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [
                "yt-dlp",
                "--write-auto-sub",
                "--sub-lang", "en",
                "--sub-format", "vtt",
                "--skip-download",
                "-o", f"{tmpdir}/%(id)s",
                video_url,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return ""

        vtt_files = sorted(Path(tmpdir).glob("*.vtt"))
        if not vtt_files:
            return ""

        return _parse_vtt(vtt_files[0].read_text(encoding="utf-8"))


_INLINE_TAG_RE = re.compile(r"<[^>]+>")


def _parse_vtt(vtt_content: str) -> str:
    """Extract cue text from WebVTT, skipping header/timestamps/metadata/styles.

    VTT 포맷:
      WEBVTT
      Kind: captions               <- 헤더 메타데이터 (무시)
      Language: en
      (빈 줄)
      00:00:00.000 --> 00:00:03.000  <- 타이밍 (무시)
      cue text line 1                <- 본문 (수집)
      cue text line 2                <- 본문 (수집)
      (빈 줄 = cue 끝)
      ...

    첫 번째 타이밍 라인을 만나기 전까지는 모두 헤더로 간주. 이후 '-->'가 있는
    라인은 타이밍으로 skip, 빈 줄은 cue 경계로 사용, 나머지는 큐 텍스트로 수집
    (인라인 태그 `<c>`, `</c>` 등은 제거).
    """
    lines: list[str] = []
    seen_first_cue_timing = False
    in_cue = False

    for raw_line in vtt_content.splitlines():
        line = raw_line.strip()
        if not line:
            in_cue = False
            continue
        if not seen_first_cue_timing:
            if "-->" in line:
                seen_first_cue_timing = True
                in_cue = True
            # 헤더/메타데이터/NOTE 블록 등은 전부 무시
            continue
        if "-->" in line:
            in_cue = True
            continue
        if not in_cue:
            continue
        cleaned = _INLINE_TAG_RE.sub("", line)
        if cleaned:
            lines.append(cleaned)

    return "\n".join(lines)


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
Expected: 4 passed

- [ ] **Step 9: Commit**

```bash
git add src/sources/web.py src/sources/sns.py src/sources/youtube.py tests/test_source_web.py tests/test_source_sns.py tests/test_source_youtube.py
git commit -m "feat: web, SNS, and YouTube source modules"
```
