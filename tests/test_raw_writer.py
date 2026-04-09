def test_write_raw_article(tmp_path):
    from src.writer.raw_writer import RawWriter
    from src.writer.vault import VaultManager

    vault = VaultManager(tmp_path / "vault")
    writer = RawWriter(vault)

    article = {
        "id": "article-001",
        "title": "Test Article",
        "source": {
            "type": "news",
            "name": "TechCrunch",
            "url": "https://example.com/article",
            "author": "John Doe",
        },
        "collected_at": "2026-04-08T14:30:00Z",
        "published_at": "2026-04-08T12:00:00Z",
        "language": "en",
        "companies": ["[[NVIDIA]]"],
        "tags": ["world-model"],
        "reliability": 0.7,
        "content_type": "article",
        "body": "NVIDIA announced a new platform for [[World Models]].",
    }

    path = writer.write(article, date="2026-04-08")

    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "title: Test Article" in content
    assert "[[NVIDIA]]" in content
    assert "[[World Models]]" in content
    assert "id: article-001" in content
