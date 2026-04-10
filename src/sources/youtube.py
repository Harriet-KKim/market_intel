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
