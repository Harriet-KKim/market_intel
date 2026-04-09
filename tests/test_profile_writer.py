def test_create_company_profile(tmp_path):
    from src.writer.profile_writer import ProfileWriter
    from src.writer.vault import VaultManager

    vault = VaultManager(tmp_path / "vault")
    writer = ProfileWriter(vault)

    writer.create_company(
        name="NVIDIA",
        aliases=["엔비디아", "Jensen Huang"],
    )

    path = vault.companies_dir / "NVIDIA.md"
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "aliases:" in content
    assert "엔비디아" in content
    assert "## 회사 개요" in content
    assert "## 최근 동향" in content


def test_create_topic_profile(tmp_path):
    from src.writer.profile_writer import ProfileWriter
    from src.writer.vault import VaultManager

    vault = VaultManager(tmp_path / "vault")
    writer = ProfileWriter(vault)

    writer.create_topic(
        name="World Models",
        aliases=["world model", "월드 모델"],
    )

    path = vault.topics_dir / "World Models.md"
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "## 개요" in content
    assert "## 주요 플레이어" in content


def test_read_profile(tmp_path):
    from src.writer.profile_writer import ProfileWriter
    from src.writer.vault import VaultManager

    vault = VaultManager(tmp_path / "vault")
    writer = ProfileWriter(vault)
    writer.create_company(name="NVIDIA", aliases=["엔비디아"])

    metadata, body = writer.read_company("NVIDIA")

    assert "엔비디아" in metadata["aliases"]
    assert "## 회사 개요" in body


def test_update_profile(tmp_path):
    from src.writer.profile_writer import ProfileWriter
    from src.writer.vault import VaultManager

    vault = VaultManager(tmp_path / "vault")
    writer = ProfileWriter(vault)
    writer.create_company(name="NVIDIA", aliases=["엔비디아"])

    new_body = """## 회사 개요
GPU 및 AI 컴퓨팅 플랫폼 기업.

## 최근 동향
- 2026-W15: GR00T 2.0 발표

## 기술 스택
Cosmos, Isaac, GR00T

## 파트너십 / 생태계
[[Boston Dynamics]]와 협력

## 전망 / 시사점
로보틱스 생태계 핵심 인프라 역할 강화

---

## 기타 노트
"""

    writer.update_company("NVIDIA", new_body)
    _, body = writer.read_company("NVIDIA")

    assert "GR00T 2.0 발표" in body
    assert "[[Boston Dynamics]]" in body
