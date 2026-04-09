from __future__ import annotations

from pathlib import Path

from src.writer.frontmatter import generate_frontmatter, parse_document
from src.writer.vault import VaultManager

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
