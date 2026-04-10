from __future__ import annotations

import re

from src.registry import Registry


def inject_wikilinks(text: str, registry: Registry) -> str:
    """Replace company/keyword names in text with [[wikilinks]]."""
    # Collect all replacement targets: (search_term, link_name)
    replacements: list[tuple[str, str]] = []

    for company in registry.companies:
        replacements.append((company.name, company.name))
        for alias in company.aliases:
            replacements.append((alias, company.name))

    for keyword in registry.keywords:
        replacements.append((keyword.name, keyword.name))
        for alias in keyword.aliases:
            replacements.append((alias, keyword.name))

    # Sort by length descending to match longer terms first
    replacements.sort(key=lambda x: len(x[0]), reverse=True)

    for search_term, link_name in replacements:
        # Skip if already wrapped in [[ ]]
        # 로컬 패치 L4: \b 단어 경계를 추가해 alias substring 오매칭을 방지.
        # 예: alias "humanoid" → "superhumanoid" 내부에 매칭되지 않음. 한글 alias는
        # \b가 한글-ASCII 경계에서 동작하므로 "엔비디아가" 같은 조사 앞에서도 매칭됨.
        pattern = re.compile(
            r"(?<!\[\[)\b" + re.escape(search_term) + r"\b(?!\]\])",
            re.IGNORECASE,
        )
        text = pattern.sub(f"[[{link_name}]]", text, count=0)

    return text
