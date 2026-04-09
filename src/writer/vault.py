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
