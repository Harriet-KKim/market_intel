from __future__ import annotations

import logging
import re
import subprocess
import tempfile
from pathlib import Path

import feedparser

from src.sources.base import BaseSource, CollectedItem

logger = logging.getLogger(__name__)


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


class YoutubeSource(BaseSource):
    source_type = "video"

    def fetch(self, company_id: str, keywords: list[str]) -> list[CollectedItem]:
        return []

    def fetch_from_url(self, video_url: str, channel: str | None = None) -> list[CollectedItem]:
        """Fetch transcript from a YouTube video URL."""
        try:
            transcript = extract_transcript(video_url)
        except (subprocess.TimeoutExpired, OSError):
            logger.warning(f"YouTube fetch failed for {video_url}", exc_info=True)
            return []

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
