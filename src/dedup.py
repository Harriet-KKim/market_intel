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
