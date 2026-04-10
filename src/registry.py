from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Company:
    id: str
    name: str
    aliases: list[str]
    sources: dict[str, list[str]]
    topics: list[str]


@dataclass
class Keyword:
    id: str
    name: str
    aliases: list[str]


@dataclass
class ReputationTier:
    score: float
    sources: list[str]


class Registry:
    def __init__(self, registry_dir: Path):
        self.registry_dir = registry_dir
        self.companies: list[Company] = []
        self.keywords: list[Keyword] = []
        self.reputation_tiers: list[ReputationTier] = []
        self._company_map: dict[str, Company] = {}
        self._keyword_map: dict[str, Keyword] = {}
        self._reputation_map: dict[str, float] = {}
        self._load()

    def _load(self):
        self._load_companies()
        self._load_keywords()
        self._load_reputation()

    def _load_companies(self):
        path = self.registry_dir / "companies.yaml"
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        for entry in data.get("companies", []):
            company = Company(
                id=entry["id"],
                name=entry["name"],
                aliases=entry.get("aliases", []),
                sources=entry.get("sources", {}),
                topics=entry.get("topics", []),
            )
            self.companies.append(company)
            self._company_map[company.id] = company

    def _load_keywords(self):
        path = self.registry_dir / "keywords.yaml"
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        for entry in data.get("keywords", []):
            keyword = Keyword(
                id=entry["id"],
                name=entry["name"],
                aliases=entry.get("aliases", []),
            )
            self.keywords.append(keyword)
            self._keyword_map[keyword.id] = keyword

    def _load_reputation(self):
        path = self.registry_dir / "source_reputation.yaml"
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        for tier_name, tier_data in data.get("tiers", {}).items():
            tier = ReputationTier(
                score=tier_data["score"],
                sources=tier_data["sources"],
            )
            self.reputation_tiers.append(tier)
            for source_name in tier.sources:
                self._reputation_map[source_name.lower()] = tier.score

    def get_company(self, company_id: str) -> Company | None:
        return self._company_map.get(company_id)

    def get_keyword(self, keyword_id: str) -> Keyword | None:
        return self._keyword_map.get(keyword_id)

    def get_reputation_score(self, source_name: str) -> float | None:
        return self._reputation_map.get(source_name.lower())

    def resolve_company(self, identifier: str) -> Company | None:
        """Resolve a company by id, name, or alias (case-insensitive).

        로컬 패치 L9: Summarizer는 LLM 출력에 따라 id/name/alias 중 어느 것이든 사용할 수
        있습니다. ProfileWriter가 파일 경로를 `{company.name}.md`로 고정하기 때문에, 호출자가
        canonical name이 아닌 식별자를 보내면 프로필 파일을 찾지 못했습니다. 이 메서드로
        세 표기 모두를 Company 객체로 단일화합니다.
        """
        if identifier in self._company_map:
            return self._company_map[identifier]
        id_lower = identifier.lower()
        for company in self.companies:
            if company.name.lower() == id_lower:
                return company
        for company in self.companies:
            if any(alias.lower() == id_lower for alias in company.aliases):
                return company
        return None

    def resolve_keyword(self, identifier: str) -> Keyword | None:
        """Resolve a keyword by id, name, or alias (case-insensitive). 로컬 패치 L9."""
        if identifier in self._keyword_map:
            return self._keyword_map[identifier]
        id_lower = identifier.lower()
        for keyword in self.keywords:
            if keyword.name.lower() == id_lower:
                return keyword
        for keyword in self.keywords:
            if any(alias.lower() == id_lower for alias in keyword.aliases):
                return keyword
        return None

    def match_companies(self, text: str) -> list[str]:
        """Return list of company IDs whose name or aliases appear in text."""
        text_lower = text.lower()
        matched = []
        for company in self.companies:
            search_terms = [company.name.lower()] + [a.lower() for a in company.aliases]
            if any(term in text_lower for term in search_terms):
                matched.append(company.id)
        return matched

    def match_keywords(self, text: str) -> list[str]:
        """Return list of keyword IDs whose name or aliases appear in text."""
        text_lower = text.lower()
        matched = []
        for keyword in self.keywords:
            search_terms = [keyword.name.lower()] + [a.lower() for a in keyword.aliases]
            if any(term in text_lower for term in search_terms):
                matched.append(keyword.id)
        return matched
