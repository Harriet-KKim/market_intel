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
        pattern = re.compile(
            r"(?<!\[\[)" + re.escape(search_term) + r"(?!\]\])",
            re.IGNORECASE,
        )
        text = pattern.sub(f"[[{link_name}]]", text, count=0)

    return text
