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
