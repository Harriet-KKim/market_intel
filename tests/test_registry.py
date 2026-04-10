def test_load_companies(sample_registry_dir):
    from src.registry import Registry

    registry = Registry(sample_registry_dir)

    assert len(registry.companies) == 2
    nvidia = registry.get_company("nvidia")
    assert nvidia.name == "NVIDIA"
    assert "Jensen Huang" in nvidia.aliases
    assert "world-model" in nvidia.topics


def test_load_keywords(sample_registry_dir):
    from src.registry import Registry

    registry = Registry(sample_registry_dir)

    assert len(registry.keywords) == 2
    wm = registry.get_keyword("world-model")
    assert wm.name == "World Models"
    assert "월드 모델" in wm.aliases


def test_get_reputation_score(sample_registry_dir):
    from src.registry import Registry

    registry = Registry(sample_registry_dir)

    assert registry.get_reputation_score("Reuters") == 0.9
    assert registry.get_reputation_score("TechCrunch") == 0.7
    assert registry.get_reputation_score("Unknown Source") is None


def test_match_companies_from_text(sample_registry_dir):
    from src.registry import Registry

    registry = Registry(sample_registry_dir)
    text = "Jensen Huang unveiled NVIDIA's new robotics platform. Figure AI also announced partnership."

    matches = registry.match_companies(text)

    assert "nvidia" in matches
    assert "figure-ai" in matches


def test_match_keywords_from_text(sample_registry_dir):
    from src.registry import Registry

    registry = Registry(sample_registry_dir)
    text = "New advances in world model research for humanoid robots."

    matches = registry.match_keywords(text)

    assert "world-model" in matches
    assert "humanoid-robot" in matches


def test_resolve_company_by_id(sample_registry_dir):
    """L9: id로 회사를 찾을 수 있다."""
    from src.registry import Registry

    registry = Registry(sample_registry_dir)
    company = registry.resolve_company("nvidia")
    assert company is not None
    assert company.name == "NVIDIA"


def test_resolve_company_by_name(sample_registry_dir):
    """L9: name(대소문자 무관)으로 회사를 찾을 수 있다."""
    from src.registry import Registry

    registry = Registry(sample_registry_dir)
    company = registry.resolve_company("NVIDIA")
    assert company is not None
    assert company.id == "nvidia"

    lower = registry.resolve_company("nvidia")
    assert lower is not None
    assert lower.id == "nvidia"


def test_resolve_company_by_alias(sample_registry_dir):
    """L9: alias로 회사를 찾을 수 있다."""
    from src.registry import Registry

    registry = Registry(sample_registry_dir)
    company = registry.resolve_company("엔비디아")
    assert company is not None
    assert company.id == "nvidia"

    fig = registry.resolve_company("Figure 02")
    assert fig is not None
    assert fig.id == "figure-ai"


def test_resolve_company_not_found(sample_registry_dir):
    """L9: 존재하지 않는 식별자는 None."""
    from src.registry import Registry

    registry = Registry(sample_registry_dir)
    assert registry.resolve_company("nonexistent") is None


def test_resolve_keyword_by_id_name_alias(sample_registry_dir):
    """L9: keyword도 id/name/alias 세 표기 모두 해석된다."""
    from src.registry import Registry

    registry = Registry(sample_registry_dir)

    by_id = registry.resolve_keyword("world-model")
    assert by_id is not None and by_id.name == "World Models"

    by_name = registry.resolve_keyword("World Models")
    assert by_name is not None and by_name.id == "world-model"

    by_alias = registry.resolve_keyword("월드 모델")
    assert by_alias is not None and by_alias.id == "world-model"

    assert registry.resolve_keyword("nonexistent") is None
