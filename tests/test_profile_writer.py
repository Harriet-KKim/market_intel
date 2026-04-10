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


def test_profile_writer_resolve_company_name(tmp_path, sample_registry_dir):
    """L9: id/name/alias 어느 표기로든 canonical name을 해석할 수 있다."""
    from src.registry import Registry
    from src.writer.profile_writer import ProfileWriter
    from src.writer.vault import VaultManager

    vault = VaultManager(tmp_path / "vault")
    registry = Registry(sample_registry_dir)
    writer = ProfileWriter(vault)

    assert writer.resolve_company_name("nvidia", registry) == "NVIDIA"
    assert writer.resolve_company_name("NVIDIA", registry) == "NVIDIA"
    assert writer.resolve_company_name("엔비디아", registry) == "NVIDIA"
    assert writer.resolve_company_name("Figure 02", registry) == "Figure AI"
    assert writer.resolve_company_name("nonexistent", registry) is None


def test_profile_writer_resolve_topic_name(tmp_path, sample_registry_dir):
    """L9: topic도 id/name/alias로 canonical name을 얻는다."""
    from src.registry import Registry
    from src.writer.profile_writer import ProfileWriter
    from src.writer.vault import VaultManager

    vault = VaultManager(tmp_path / "vault")
    registry = Registry(sample_registry_dir)
    writer = ProfileWriter(vault)

    assert writer.resolve_topic_name("world-model", registry) == "World Models"
    assert writer.resolve_topic_name("월드 모델", registry) == "World Models"
    assert writer.resolve_topic_name("휴머노이드", registry) == "Humanoid Robot"
    assert writer.resolve_topic_name("unknown-topic", registry) is None


def test_profile_writer_company_path_uses_canonical_name(tmp_path, sample_registry_dir):
    """L9: company_path는 alias로 호출해도 canonical 파일 경로를 반환한다."""
    from src.registry import Registry
    from src.writer.profile_writer import ProfileWriter
    from src.writer.vault import VaultManager

    vault = VaultManager(tmp_path / "vault")
    registry = Registry(sample_registry_dir)
    writer = ProfileWriter(vault)

    expected = vault.companies_dir / "NVIDIA.md"
    assert writer.company_path("nvidia", registry) == expected
    assert writer.company_path("엔비디아", registry) == expected
    assert writer.company_path("NVIDIA", registry) == expected
    assert writer.company_path("missing", registry) is None
