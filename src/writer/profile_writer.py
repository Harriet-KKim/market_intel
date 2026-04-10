from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from src.writer.frontmatter import generate_frontmatter, parse_document
from src.writer.vault import VaultManager

if TYPE_CHECKING:
    from src.registry import Registry

COMPANY_TEMPLATE = """## 회사 개요


## 최근 동향


## 기술 스택


## 파트너십 / 생태계


## 전망 / 시사점


---

## 기타 노트
"""

TOPIC_TEMPLATE = """## 개요


## 주요 플레이어


## 최근 동향


## 핵심 논문 / 레퍼런스


## 시사점


---

## 기타 노트
"""


class ProfileWriter:
    def __init__(self, vault: VaultManager):
        self._vault = vault

    def create_company(self, name: str, aliases: list[str]) -> Path:
        metadata = {"aliases": [name] + aliases, "tags": ["company"]}
        content = generate_frontmatter(metadata) + "\n" + COMPANY_TEMPLATE
        path = self._vault.companies_dir / f"{name}.md"
        path.write_text(content, encoding="utf-8")
        return path

    def create_topic(self, name: str, aliases: list[str]) -> Path:
        metadata = {"aliases": [name] + aliases, "tags": ["topic"]}
        content = generate_frontmatter(metadata) + "\n" + TOPIC_TEMPLATE
        path = self._vault.topics_dir / f"{name}.md"
        path.write_text(content, encoding="utf-8")
        return path

    def read_company(self, name: str) -> tuple[dict, str]:
        path = self._vault.companies_dir / f"{name}.md"
        return parse_document(path.read_text(encoding="utf-8"))

    def read_topic(self, name: str) -> tuple[dict, str]:
        path = self._vault.topics_dir / f"{name}.md"
        return parse_document(path.read_text(encoding="utf-8"))

    def resolve_company_name(self, identifier: str, registry: "Registry") -> str | None:
        """Resolve id/name/alias → canonical `company.name` used for the profile path.

        로컬 패치 L9: Summarizer가 내려보내는 `company_updates[key]`의 key가 id나
        alias일 수 있습니다. 이 헬퍼로 `companies/{name}.md` 파일 경로를 안전하게 계산합니다.
        """
        company = registry.resolve_company(identifier)
        return company.name if company else None

    def resolve_topic_name(self, identifier: str, registry: "Registry") -> str | None:
        """Resolve id/name/alias → canonical `keyword.name` used for the topic path. 로컬 패치 L9."""
        keyword = registry.resolve_keyword(identifier)
        return keyword.name if keyword else None

    def company_path(self, identifier: str, registry: "Registry") -> Path | None:
        """Return the profile file path for any identifier, or None if unresolved. 로컬 패치 L9."""
        name = self.resolve_company_name(identifier, registry)
        return self._vault.companies_dir / f"{name}.md" if name else None

    def topic_path(self, identifier: str, registry: "Registry") -> Path | None:
        """Return the topic profile file path for any identifier, or None if unresolved. 로컬 패치 L9."""
        name = self.resolve_topic_name(identifier, registry)
        return self._vault.topics_dir / f"{name}.md" if name else None

    def update_company(self, name: str, new_body: str) -> None:
        path = self._vault.companies_dir / f"{name}.md"
        metadata, _ = parse_document(path.read_text(encoding="utf-8"))
        content = generate_frontmatter(metadata) + "\n" + new_body
        path.write_text(content, encoding="utf-8")

    def update_topic(self, name: str, new_body: str) -> None:
        path = self._vault.topics_dir / f"{name}.md"
        metadata, _ = parse_document(path.read_text(encoding="utf-8"))
        content = generate_frontmatter(metadata) + "\n" + new_body
        path.write_text(content, encoding="utf-8")
