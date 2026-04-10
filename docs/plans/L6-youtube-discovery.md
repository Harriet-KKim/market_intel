# L6 — YouTube Channel Discovery via RSS 구현 플랜

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `docs/plans/README.md`의 백로그 **L6**(스케줄러 YouTube 분기가 `logger.info`만 찍는 스텁) 를 해소한다. `YoutubeSource`가 공개 Atom 피드(`https://www.youtube.com/feeds/videos.xml?channel_id=...`)를 파싱하여 실제 비디오를 discovery 하고, 스케줄러가 이 결과를 `CollectionPipeline.process_item`에 흘려보내도록 배선한다.

**Architecture:** feedparser(이미 `rss.py`에서 사용 중)로 YouTube의 공개 채널 Atom 피드를 파싱해 최신 ~15개 비디오의 메타데이터(title, description, link, author, published)를 `CollectedItem`으로 방출한다. 본문은 transcript가 아닌 **Atom entry의 description**을 사용한다 — transcript는 yt-dlp subprocess 당 10~30초가 들고 자막 없는 비디오도 많기 때문에, 기존 `extract_transcript`/`fetch_from_url` 경로를 opt-in으로 보존하고 discovery는 description만으로 태깅한다. 핸들(`@NvidiaAI`) 해석은 HTML 스크래핑이 필요하므로 의도적으로 미지원 — 사용자는 채널 페이지 소스의 `channelId` 값(UC로 시작하는 24자) 또는 완성된 feed URL을 입력한다. 스케줄러 배선은 기존 RSS 분기(`scheduler.py:40-52`)와 동일한 outer/inner try 패턴(L15 계보)을 따른다.

**Tech Stack:** Python 3.12+, feedparser (기존 의존성), pytest + monkeypatch, unittest.mock.MagicMock

---

## 작업 순서 개요

| Task | 파일 | 스코프 | 커밋 |
|------|------|--------|------|
| 1 | `src/sources/youtube.py` + `tests/test_source_youtube.py` | `_normalize_channel_to_feed_url` 헬퍼 + `fetch_channel_videos` 메서드 + 7개 유닛 테스트 | `feat: add YouTube channel discovery via Atom feed (L6 part 1)` |
| 2 | `src/scheduler/scheduler.py` + `src/main.py` + `tests/test_scheduler.py` | 스케줄러 스텁 교체 + Registry 템플릿 주석 업데이트 + 2개 스케줄러 테스트 | `feat: wire YouTube channel discovery into collection cycle (L6 part 2)` |
| 3 | `docs/plans/README.md` | L6 을 "알려진 한계" 에서 "Resolved" 표로 이동 | `docs: mark L6 resolved in backlog index` |

작업은 프로젝트 루트 (`C:\Users\Harriet\Desktop\SST\AX Strategy\Research System\market_intel`)에서 실행한다. Windows 에서는 `python` 대신 `py -m pytest` 를 사용한다 (CLAUDE.md 지침).

---

## Task 1: Add YouTube channel discovery to YoutubeSource

**Files:**
- Modify: `src/sources/youtube.py` (add `import feedparser` + `_normalize_channel_to_feed_url` helper + `YoutubeSource.fetch_channel_videos` method)
- Modify: `tests/test_source_youtube.py` (append 7 new tests)

- [ ] **Step 1: Write the failing tests**

`tests/test_source_youtube.py` 의 **파일 하단에** 다음 7개 테스트를 추가한다 (기존 3개 테스트 — `test_youtube_source_fetches_transcript`, `test_parse_vtt_extracts_cue_text`, `test_youtube_source_returns_empty_on_extract_error` — 는 그대로 둔다):

```python
# ---------- L6: channel discovery via Atom feed ----------


def test_normalize_channel_id_to_feed_url():
    """UC로 시작하는 24자 channel_id는 Atom feed URL로 조립된다."""
    from src.sources.youtube import _normalize_channel_to_feed_url

    result = _normalize_channel_to_feed_url("UCHuFmzwsYryg1kUV0IMzEag")
    assert result == (
        "https://www.youtube.com/feeds/videos.xml?"
        "channel_id=UCHuFmzwsYryg1kUV0IMzEag"
    )


def test_normalize_full_feed_url_passthrough():
    """완전한 feeds.xml URL은 변형 없이 그대로 반환된다."""
    from src.sources.youtube import _normalize_channel_to_feed_url

    url = (
        "https://www.youtube.com/feeds/videos.xml?"
        "channel_id=UCHuFmzwsYryg1kUV0IMzEag"
    )
    assert _normalize_channel_to_feed_url(url) == url


def test_normalize_unsupported_handle_returns_none():
    """@handle 과 plain username 은 MVP 범위 밖이라 None을 반환한다."""
    from src.sources.youtube import _normalize_channel_to_feed_url

    assert _normalize_channel_to_feed_url("@NvidiaAI") is None
    assert _normalize_channel_to_feed_url("NvidiaAI") is None
    # UC로 시작하지만 길이가 틀린 경우도 None
    assert _normalize_channel_to_feed_url("UCtooShort") is None


def test_fetch_channel_videos_from_channel_id(monkeypatch):
    """UC channel_id → feedparser로 Atom 피드 파싱 → CollectedItem 리스트."""
    import feedparser
    from src.sources.youtube import YoutubeSource

    fake_feed = feedparser.FeedParserDict(
        {
            "feed": feedparser.FeedParserDict({"title": "NVIDIA Developer"}),
            "entries": [
                feedparser.FeedParserDict(
                    {
                        "title": "GR00T 2.0 Launch Demo",
                        "link": "https://www.youtube.com/watch?v=abc123",
                        "summary": "NVIDIA unveils GR00T 2.0 for humanoid robots.",
                        "author": "NVIDIA Developer",
                        "published": "2026-04-08T12:00:00+00:00",
                    }
                ),
                feedparser.FeedParserDict(
                    {
                        "title": "Isaac Sim Tutorial",
                        "link": "https://www.youtube.com/watch?v=def456",
                        "summary": "Walkthrough of the Isaac Sim workflow.",
                        "author": "NVIDIA Developer",
                        "published": "2026-04-07T09:00:00+00:00",
                    }
                ),
            ],
        }
    )

    captured_url: dict[str, str] = {}

    def fake_parse(url):
        captured_url["url"] = url
        return fake_feed

    monkeypatch.setattr("src.sources.youtube.feedparser.parse", fake_parse)

    source = YoutubeSource()
    items = source.fetch_channel_videos("UCHuFmzwsYryg1kUV0IMzEag")

    assert captured_url["url"] == (
        "https://www.youtube.com/feeds/videos.xml?"
        "channel_id=UCHuFmzwsYryg1kUV0IMzEag"
    )
    assert len(items) == 2

    first = items[0]
    assert first.title == "GR00T 2.0 Launch Demo"
    assert first.url == "https://www.youtube.com/watch?v=abc123"
    assert first.body == "NVIDIA unveils GR00T 2.0 for humanoid robots."
    assert first.source_type == "video"
    assert first.source_name == "YouTube"
    assert first.channel == "NVIDIA Developer"
    assert first.content_type == "video"
    assert first.author == "NVIDIA Developer"
    assert first.published_at == "2026-04-08T12:00:00+00:00"

    assert items[1].url == "https://www.youtube.com/watch?v=def456"


def test_fetch_channel_videos_accepts_full_feed_url(monkeypatch):
    """full feeds.xml URL은 prefix 중복 없이 그대로 feedparser에 전달된다."""
    import feedparser
    from src.sources.youtube import YoutubeSource

    empty_feed = feedparser.FeedParserDict(
        {
            "feed": feedparser.FeedParserDict({"title": ""}),
            "entries": [],
        }
    )
    captured: dict[str, str] = {}

    def fake_parse(url):
        captured["url"] = url
        return empty_feed

    monkeypatch.setattr("src.sources.youtube.feedparser.parse", fake_parse)

    full_url = (
        "https://www.youtube.com/feeds/videos.xml?"
        "channel_id=UCHuFmzwsYryg1kUV0IMzEag"
    )
    YoutubeSource().fetch_channel_videos(full_url)
    assert captured["url"] == full_url


def test_fetch_channel_videos_unsupported_handle_returns_empty(monkeypatch, caplog):
    """@handle은 feedparser 호출 없이 즉시 빈 리스트 + 경고 로그."""
    import logging
    from src.sources.youtube import YoutubeSource

    def should_not_be_called(url):
        raise AssertionError(f"feedparser.parse should not be called, got {url}")

    monkeypatch.setattr(
        "src.sources.youtube.feedparser.parse", should_not_be_called
    )

    with caplog.at_level(logging.WARNING, logger="src.sources.youtube"):
        items = YoutubeSource().fetch_channel_videos("@NvidiaAI")

    assert items == []
    assert any("not supported" in rec.message for rec in caplog.records)


def test_fetch_channel_videos_returns_empty_on_parse_error(monkeypatch):
    """L13 parity: feedparser가 예외를 던지면 빈 리스트 반환 (crash 없음)."""
    from src.sources.youtube import YoutubeSource

    def raise_error(url):
        raise OSError("network unreachable")

    monkeypatch.setattr("src.sources.youtube.feedparser.parse", raise_error)

    items = YoutubeSource().fetch_channel_videos("UCHuFmzwsYryg1kUV0IMzEag")
    assert items == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
py -m pytest tests/test_source_youtube.py -v
```
Expected: 기존 3개 테스트는 PASS, 새 7개 테스트 중 최소 3개는 `ImportError: cannot import name '_normalize_channel_to_feed_url'`, 나머지 4개는 `AttributeError: 'YoutubeSource' object has no attribute 'fetch_channel_videos'` 로 FAIL.

- [ ] **Step 3: Implement in `src/sources/youtube.py`**

파일 상단 import 블록에 `import feedparser`를 추가한다 (기존 imports `logging, re, subprocess, tempfile, pathlib.Path` 아래):

```python
from __future__ import annotations

import logging
import re
import subprocess
import tempfile
from pathlib import Path

import feedparser

from src.sources.base import BaseSource, CollectedItem

logger = logging.getLogger(__name__)
```

`_parse_vtt` 정의 **바로 다음** (즉 `class YoutubeSource:` 선언 **직전**) 에 helper 함수를 추가한다:

```python
def _normalize_channel_to_feed_url(channel: str) -> str | None:
    """Normalize a YouTube channel identifier to an Atom feed URL.

    Accepts:
      - Full feed URL starting with ``https://www.youtube.com/feeds/videos.xml``
      - Bare channel_id: 24 chars total, starting with ``UC``

    Returns ``None`` for unsupported forms such as ``@handle`` or plain
    usernames. Handle resolution would require scraping the channel HTML for
    its embedded ``channelId`` field — brittle and out of scope for MVP (L6).
    Users must supply a channel_id (find it in the channel page source under
    ``"channelId"``) or a pre-built feed URL.
    """
    if channel.startswith("https://www.youtube.com/feeds/videos.xml"):
        return channel
    if channel.startswith("UC") and len(channel) == 24:
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel}"
    return None
```

그리고 `YoutubeSource` 클래스 안, 기존 `fetch_from_url` 메서드 **다음**에 새 메서드를 추가한다 (기존 `fetch` 와 `fetch_from_url` 은 손대지 않는다):

```python
    def fetch_channel_videos(self, channel: str) -> list[CollectedItem]:
        """Discover recent videos from a YouTube channel via its public Atom feed.

        ``channel`` accepts either:
          - A bare channel_id starting with ``UC`` (24 chars total), or
          - A full ``https://www.youtube.com/feeds/videos.xml?...`` URL.

        YouTube exposes the latest ~15 videos per channel in this feed, no
        API key required. Handle resolution (``@NvidiaAI`` → channel_id) is
        out of scope — see :func:`_normalize_channel_to_feed_url`.

        The returned ``CollectedItem.body`` is the Atom entry description,
        **not the transcript**. Transcript extraction via yt-dlp remains an
        opt-in path (``fetch_from_url`` / ``extract_transcript``) because
        transcripts are slow (10-30s/video through a subprocess) and many
        videos lack captions. Description is sufficient input for Gemini
        tagging in the collection pipeline.
        """
        feed_url = _normalize_channel_to_feed_url(channel)
        if feed_url is None:
            logger.warning(
                "YouTube channel identifier not supported: %r. "
                "Expected channel_id (UC...) or full feeds.xml URL.",
                channel,
            )
            return []

        try:
            feed = feedparser.parse(feed_url)
        except Exception:
            logger.warning(
                f"YouTube channel fetch failed for {channel}", exc_info=True
            )
            return []

        feed_meta = getattr(feed, "feed", {}) or {}
        raw_title = feed_meta.get("title") if hasattr(feed_meta, "get") else None
        channel_name = raw_title if raw_title else channel

        items: list[CollectedItem] = []
        for entry in feed.get("entries", []):
            items.append(
                CollectedItem(
                    title=entry.get("title", ""),
                    url=entry.get("link", ""),
                    body=entry.get("summary", ""),
                    source_type=self.source_type,  # "video"
                    source_name="YouTube",
                    author=entry.get("author"),
                    published_at=entry.get("published"),
                    language=None,
                    content_type="video",
                    channel=channel_name,
                )
            )
        return items
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
py -m pytest tests/test_source_youtube.py -v
```
Expected: 10 passed (기존 3개 + 신규 7개).

회귀 확인을 위해 전체 suite도 돌린다:
```bash
py -m pytest tests/ -v
```
Expected: 전부 passed (이전 baseline 을 넘지 않아야 함).

- [ ] **Step 5: Commit**

```bash
git add src/sources/youtube.py tests/test_source_youtube.py
git commit -m "feat: add YouTube channel discovery via Atom feed (L6 part 1)"
```

---

## Task 2: Wire YouTube discovery into scheduler cycle

**Files:**
- Modify: `src/scheduler/scheduler.py:79-83` (YouTube 분기 교체)
- Modify: `src/main.py` (`REGISTRY_TEMPLATES["companies.yaml"]` 주석 업데이트)
- Modify: `tests/test_scheduler.py` (2개 테스트 추가)

- [ ] **Step 1: Write the failing tests**

`tests/test_scheduler.py` 의 **파일 하단에** 다음 두 테스트를 추가한다:

```python
def test_scheduler_discovers_youtube_videos():
    """L6: sources.youtube=True일 때 fetch_channel_videos 호출 결과가 pipeline.process_item 으로 흐른다."""
    config = _make_config(
        sources=SourcesConfig(rss=False, web=False, sns=False, youtube=True)
    )

    registry = MagicMock()
    company = MagicMock()
    company.name = "NVIDIA"
    company.sources = {"youtube": ["UCHuFmzwsYryg1kUV0IMzEag"]}
    registry.companies = [company]

    pipeline = MagicMock()
    pipeline.process_item.return_value = Path("/tmp/out.md")

    scheduler = _make_scheduler(config=config, registry=registry, pipeline=pipeline)

    mock_youtube = MagicMock()
    item1 = MagicMock()
    item1.url = "https://www.youtube.com/watch?v=abc123"
    item2 = MagicMock()
    item2.url = "https://www.youtube.com/watch?v=def456"
    mock_youtube.fetch_channel_videos.return_value = [item1, item2]
    scheduler._youtube = mock_youtube

    scheduler.run_once()

    mock_youtube.fetch_channel_videos.assert_called_once_with(
        "UCHuFmzwsYryg1kUV0IMzEag"
    )
    assert pipeline.process_item.call_count == 2
    pipeline.process_item.assert_any_call(item1)
    pipeline.process_item.assert_any_call(item2)


def test_scheduler_skips_youtube_discovery_when_disabled():
    """sources.youtube=False일 때 fetch_channel_videos 는 호출되지 않는다."""
    config = _make_config(
        sources=SourcesConfig(rss=False, web=False, sns=False, youtube=False)
    )

    registry = MagicMock()
    company = MagicMock()
    company.name = "NVIDIA"
    company.sources = {"youtube": ["UCHuFmzwsYryg1kUV0IMzEag"]}
    registry.companies = [company]

    pipeline = MagicMock()
    scheduler = _make_scheduler(config=config, registry=registry, pipeline=pipeline)
    mock_youtube = MagicMock()
    scheduler._youtube = mock_youtube

    scheduler.run_once()

    mock_youtube.fetch_channel_videos.assert_not_called()
    pipeline.process_item.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
py -m pytest tests/test_scheduler.py::test_scheduler_discovers_youtube_videos tests/test_scheduler.py::test_scheduler_skips_youtube_discovery_when_disabled -v
```
Expected:
- `test_scheduler_discovers_youtube_videos` FAIL — 현재 스케줄러는 `logger.info(f"YouTube channel check: {channel}")` 만 찍으므로 `fetch_channel_videos` 가 호출되지 않아 `assert_called_once_with` 가 실패한다.
- `test_scheduler_skips_youtube_discovery_when_disabled` 는 PASS 할 수 있다 (현재도 호출 안 됨). 그대로 둔다 — 구현 이후 회귀 방지용.

- [ ] **Step 3: Implement scheduler wiring**

`src/scheduler/scheduler.py` 의 **기존 YouTube 분기** (현재 `_run_collection_cycle` 안, SNS 분기 바로 다음 블록):

```python
            # YouTube channels (discovery stub — L6)
            if self._config.collection.sources.youtube:
                for channel in company.sources.get("youtube", []):
                    logger.info(f"YouTube channel check: {channel}")
```

을 다음과 같이 교체한다:

```python
            # YouTube channels — L6 resolved: discovery via public Atom feed.
            # fetch_channel_videos returns items whose body is the Atom entry
            # description (not the transcript). Transcript extraction remains
            # an opt-in path via YoutubeSource.fetch_from_url; see
            # src/sources/youtube.py::fetch_channel_videos for rationale.
            if self._config.collection.sources.youtube:
                for channel in company.sources.get("youtube", []):
                    try:
                        items = self._youtube.fetch_channel_videos(channel)
                    except Exception:
                        logger.exception(f"YouTube fetch failed for {channel}")
                        continue
                    for item in items:
                        try:
                            self._pipeline.process_item(item)
                        except Exception:
                            logger.exception(
                                f"YouTube process_item failed for {item.url}"
                            )
```

이 패턴은 같은 함수의 RSS 분기(`scheduler.py:40-52`)·Web 분기(`scheduler.py:55-67`)와 동일한 outer/inner try 구조(L15 계보) 이다.

- [ ] **Step 4: Update Registry template comment in `src/main.py`**

`REGISTRY_TEMPLATES` dict 의 `"companies.yaml"` 값 **상단 주석 블록**을 다음과 같이 보강한다. 현재는:

```python
    "companies.yaml": """# Physical AI 관심 회사 레지스트리.
# 자유롭게 추가/편집하세요. Obsidian에서 이 파일을 열어 수정할 수 있습니다.
companies:
```

이것을 아래로 교체한다 (주석 3줄 추가):

```python
    "companies.yaml": """# Physical AI 관심 회사 레지스트리.
# 자유롭게 추가/편집하세요. Obsidian에서 이 파일을 열어 수정할 수 있습니다.
#
# sources.youtube 형식: channel_id (UC로 시작하는 24자) 또는 완성된
# https://www.youtube.com/feeds/videos.xml?channel_id=... URL 리스트.
# @handle 형식은 미지원 — 채널 페이지 소스(Ctrl+U)에서 "channelId" 값을 복사해 입력.
companies:
```

나머지 `keywords.yaml`, `source_reputation.yaml` 템플릿은 손대지 않는다.

- [ ] **Step 5: Run tests to verify they pass**

Run:
```bash
py -m pytest tests/test_scheduler.py -v
```
Expected: 7 passed (기존 5개 + 신규 2개).

회귀 확인:
```bash
py -m pytest tests/ -v
```
Expected: 전부 passed.

- [ ] **Step 6: Commit**

```bash
git add src/scheduler/scheduler.py src/main.py tests/test_scheduler.py
git commit -m "feat: wire YouTube channel discovery into collection cycle (L6 part 2)"
```

---

## Task 3: Mark L6 as Resolved in backlog index

**Files:**
- Modify: `docs/plans/README.md` (L6 행을 "알려진 한계 (Not Fixed)" 표에서 제거하고 "Resolved" 표로 이동)

이 태스크는 **순수 문서 업데이트** 이므로 TDD 사이클이 없다. 테스트 추가 없음.

- [ ] **Step 1: Remove L6 row from "알려진 한계 (Not Fixed)" table**

`docs/plans/README.md` 의 `### 알려진 한계 (Not Fixed — 구현·운영 중 주의)` 섹션 표에서 **L6 행 전체**를 삭제한다. 지워야 할 정확한 행은:

```
| L6 | `08-scheduler.md` Task 14 YouTube 분기 | 현재는 `logger.info(f"YouTube channel check: {channel}")`만 찍고 실제 비디오 discovery 없음 — `sources.youtube`를 켜도 채널 수집은 동작하지 않음 | YouTube 채널을 실제 수집 소스로 운영할 때 | yt-dlp `--flat-playlist` 또는 RSS(`feeds/videos.xml?channel_id=...`) 기반 discovery 구현 |
```

표의 다른 행(L1·L2·L8·L10·L11) 은 그대로 둔다.

- [ ] **Step 2: Add L6 row to "Resolved" table**

`### Resolved (이전에 "미수정"으로 남아있다 이번 리뷰에서 해결된 항목)` 섹션 표의 **마지막 L14 행 다음**에 L6 행을 추가한다 (표의 기존 순서는 ID 순이 아니라 해결 순이므로, 단순히 끝에 붙인다):

```
| L6 | `src/sources/youtube.py` + `src/scheduler/scheduler.py` | `YoutubeSource.fetch_channel_videos` 신설 — YouTube 공개 Atom 피드(`feeds/videos.xml?channel_id=...`)를 feedparser로 파싱해 최신 ~15개 비디오의 title/description/link 를 `CollectedItem` 으로 방출. `_normalize_channel_to_feed_url` 이 UC 24자 channel_id 와 full feed URL 두 형태를 수용, `@handle`은 의도적 미지원(MVP). 스케줄러 YouTube 분기를 RSS/Web 과 동일한 outer/inner try 패턴으로 재작성해 fetch 결과를 `CollectionPipeline.process_item`에 흘려보냄. Transcript 추출은 기존 `fetch_from_url` opt-in 경로로 보존. 유닛 테스트 7개 + 스케줄러 통합 테스트 2개 추가 |
```

- [ ] **Step 3: Commit**

```bash
git add docs/plans/README.md
git commit -m "docs: mark L6 resolved in backlog index"
```

---

## Self-Review 체크리스트 (플랜 작성자 기준)

- [x] **Spec coverage:** L6 의 트리거("YouTube 채널을 실제 수집 소스로 운영할 때") 와 계획된 대응("RSS 기반 discovery 구현") 이 Task 1·2 에 각각 매핑됨.
- [x] **Placeholder scan:** TBD/TODO/"implement later"/"add error handling" 같은 표현 없음. 모든 코드 블록이 실제 구현 내용 포함.
- [x] **Type consistency:**
  - `_normalize_channel_to_feed_url(channel: str) -> str | None` — Task 1 에서 정의, Task 1 의 `fetch_channel_videos` 에서만 호출됨. 시그니처 일치.
  - `YoutubeSource.fetch_channel_videos(channel: str) -> list[CollectedItem]` — Task 1 에서 정의, Task 2 의 스케줄러에서 `self._youtube.fetch_channel_videos(channel)` 로 호출. 시그니처 일치.
  - `CollectedItem` 필드 — `src/sources/base.py` 의 실제 dataclass 필드(`title, url, body, source_type, source_name, author, published_at, language, content_type, channel, has_visual_analysis`) 와 정확히 일치. `has_visual_analysis` 는 기본값(False) 사용.
- [x] **기존 파일 무변경 보장:** Task 1 은 `extract_transcript`, `_parse_vtt`, `YoutubeSource.fetch`, `YoutubeSource.fetch_from_url` 에 손대지 않는다 (기존 3개 테스트가 PASS 유지되도록).
- [x] **스케줄러 패턴 일관성:** Task 2 의 try/except 블록 구조가 `scheduler.py` 의 RSS(L40-52)·Web(L55-67) 분기와 동일.
- [x] **Windows 커맨드:** 모든 pytest 명령어가 `py -m pytest` 형식 사용 (CLAUDE.md 지침).

---

## 실행 완료 시점의 최종 상태 요약

- `src/sources/youtube.py` 에 `_normalize_channel_to_feed_url` 헬퍼 + `YoutubeSource.fetch_channel_videos` 메서드 추가. `import feedparser` 1줄 추가. `extract_transcript` / `_parse_vtt` / `fetch` / `fetch_from_url` 은 건드리지 않음.
- `src/scheduler/scheduler.py` 의 YouTube 분기가 `logger.info` 스텁에서 `fetch_channel_videos` → `pipeline.process_item` 으로 교체됨. RSS/Web 과 동일한 outer/inner try 구조.
- `src/main.py` 의 `REGISTRY_TEMPLATES["companies.yaml"]` 주석에 `sources.youtube` 입력 형식(UC channel_id 또는 full feed URL, `@handle` 미지원) 이 문서화됨.
- `tests/test_source_youtube.py` 에 신규 테스트 7개 추가 → 총 10개 테스트 PASS.
- `tests/test_scheduler.py` 에 신규 테스트 2개 추가 → 총 7개 테스트 PASS.
- `docs/plans/README.md` 에서 L6 이 "알려진 한계" → "Resolved" 로 이동. 백로그 정본이 현재 코드 상태와 일치.
- 전체 pytest suite 는 이전 baseline(24개 collector 관련 + 다른 모듈들) 을 유지한 채 신규 9개가 추가되어 PASS.

운영 측면에서 사용자가 L6 해소 효과를 보려면:

1. 관심 YouTube 채널의 `channelId` (UC로 시작 24자) 를 `vault/registry/companies.yaml` 의 해당 회사 `sources.youtube:` 리스트에 추가.
2. `config.yaml` 에서 `collection.sources.youtube: true` 로 활성화.
3. `py -m src.main collect` 또는 `py -m src.main schedule` 실행 → 스케줄러가 각 회사의 등록된 채널에서 최신 비디오를 discovery → Gemini 태깅 후 `vault/raw/{date}/` 에 비디오 메타데이터 기반 노트 누적.
