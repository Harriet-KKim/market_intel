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
