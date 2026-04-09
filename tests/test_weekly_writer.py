def test_write_consolidated(tmp_path):
    from src.writer.vault import VaultManager
    from src.writer.weekly_writer import WeeklyWriter

    vault = VaultManager(tmp_path / "vault")
    writer = WeeklyWriter(vault)

    writer.write_consolidated(
        week="2026-W15",
        date_range="2026-04-06 ~ 2026-04-12",
        content="## NVIDIA\n- GR00T 2.0 발표\n\n## Figure AI\n- 시리즈 B 유치",
    )

    path = vault.weekly_dir / "2026-W15-consolidated.md"
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "period: 2026-W15" in content
    assert "GR00T 2.0" in content


def test_write_snapshot(tmp_path):
    from src.writer.vault import VaultManager
    from src.writer.weekly_writer import WeeklyWriter

    vault = VaultManager(tmp_path / "vault")
    writer = WeeklyWriter(vault)

    writer.write_snapshot(
        week="2026-W15",
        date_range="2026-04-06 ~ 2026-04-12",
        content="## 주요 하이라이트\n- GR00T 2.0 발표",
    )

    path = vault.weekly_dir / "2026-W15.md"
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "weekly" in content
    assert "주요 하이라이트" in content


def test_append_review_comment(tmp_path):
    from src.writer.vault import VaultManager
    from src.writer.weekly_writer import WeeklyWriter

    vault = VaultManager(tmp_path / "vault")
    writer = WeeklyWriter(vault)
    writer.write_snapshot(
        week="2026-W15",
        date_range="2026-04-06 ~ 2026-04-12",
        content="## 주요 하이라이트\n- Test",
    )

    writer.append_review("2026-W15", "검토 결과: 누락 사항 없음")

    content = (vault.weekly_dir / "2026-W15.md").read_text(encoding="utf-8")
    assert "검토 결과: 누락 사항 없음" in content
