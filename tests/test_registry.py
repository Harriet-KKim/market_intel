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
