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
