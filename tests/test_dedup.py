def test_url_not_seen_initially(tmp_path):
    from src.dedup import UrlDedup

    dedup = UrlDedup(tmp_path / "dedup.db")

    assert dedup.is_seen("https://example.com/article-1") is False


def test_mark_url_as_seen(tmp_path):
    from src.dedup import UrlDedup

    dedup = UrlDedup(tmp_path / "dedup.db")
    dedup.mark_seen("https://example.com/article-1")

    assert dedup.is_seen("https://example.com/article-1") is True
    assert dedup.is_seen("https://example.com/article-2") is False


def test_persistence_across_instances(tmp_path):
    from src.dedup import UrlDedup

    db_path = tmp_path / "dedup.db"
    dedup1 = UrlDedup(db_path)
    dedup1.mark_seen("https://example.com/article-1")
    dedup1.close()

    dedup2 = UrlDedup(db_path)
    assert dedup2.is_seen("https://example.com/article-1") is True
    dedup2.close()
