def test_generate_frontmatter():
    from src.writer.frontmatter import generate_frontmatter

    metadata = {
        "id": "article-001",
        "title": "Test Article",
        "tags": ["world-model", "robotics"],
        "companies": ['[[NVIDIA]]', '[[Tesla]]'],
    }
    result = generate_frontmatter(metadata)

    assert result.startswith("---\n")
    assert result.endswith("---\n")
    assert "id: article-001" in result
    assert "- world-model" in result
    assert "- '[[NVIDIA]]'" in result


def test_parse_frontmatter():
    from src.writer.frontmatter import parse_document

    doc = """---
id: article-001
title: Test Article
tags:
  - world-model
---

This is the body content."""

    metadata, body = parse_document(doc)

    assert metadata["id"] == "article-001"
    assert "world-model" in metadata["tags"]
    assert body.strip() == "This is the body content."


def test_update_frontmatter_field():
    from src.writer.frontmatter import update_field

    doc = """---
id: article-001
reliability: null
---

Body."""

    result = update_field(doc, "reliability", 0.7)

    assert "reliability: 0.7" in result
    assert "Body." in result
