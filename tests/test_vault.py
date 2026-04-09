def test_vault_ensures_directories(tmp_path):
    from src.writer.vault import VaultManager

    VaultManager(tmp_path / "vault")

    assert (tmp_path / "vault" / "companies").is_dir()
    assert (tmp_path / "vault" / "topics").is_dir()
    assert (tmp_path / "vault" / "raw").is_dir()
    assert (tmp_path / "vault" / "weekly").is_dir()
    assert (tmp_path / "vault" / "assets").is_dir()
    assert (tmp_path / "vault" / "registry").is_dir()


def test_vault_raw_dir_for_date(tmp_path):
    from src.writer.vault import VaultManager

    vault = VaultManager(tmp_path / "vault")
    raw_dir = vault.raw_dir_for_date("2026-04-08")

    assert raw_dir == tmp_path / "vault" / "raw" / "2026-04-08"
    assert raw_dir.is_dir()
