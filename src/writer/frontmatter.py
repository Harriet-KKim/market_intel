from __future__ import annotations

import io

import frontmatter
import yaml


def generate_frontmatter(metadata: dict) -> str:
    """Generate YAML frontmatter string from a dict."""
    stream = io.StringIO()
    yaml.dump(metadata, stream, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return f"---\n{stream.getvalue()}---\n"


def parse_document(text: str) -> tuple[dict, str]:
    """Parse a Markdown document with YAML frontmatter. Returns (metadata, body)."""
    post = frontmatter.loads(text)
    return dict(post.metadata), post.content


def update_field(text: str, field: str, value) -> str:
    """Update a single frontmatter field in a document string."""
    metadata, body = parse_document(text)
    metadata[field] = value
    return generate_frontmatter(metadata) + "\n" + body
