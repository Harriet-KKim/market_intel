import pytest
from pathlib import Path


@pytest.fixture
def sample_registry_dir(tmp_path):
    """Create a temporary registry directory with sample YAML files."""
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir()

    (registry_dir / "companies.yaml").write_text("""
companies:
  - id: nvidia
    name: "NVIDIA"
    aliases: ["엔비디아", "Jensen Huang", "Cosmos", "Isaac"]
    sources:
      rss: ["https://blogs.nvidia.com/feed/"]
      youtube: ["@NVIDIA"]
      official: ["https://nvidianews.nvidia.com/"]
    topics: ["world-model", "sim-to-real"]
  - id: figure-ai
    name: "Figure AI"
    aliases: ["Figure", "Figure 01", "Figure 02"]
    sources:
      youtube: ["@figureai"]
      official: ["https://www.figure.ai/news"]
    topics: ["humanoid-robot", "manipulation"]
""", encoding="utf-8")

    (registry_dir / "keywords.yaml").write_text("""
keywords:
  - id: world-model
    name: "World Models"
    aliases: ["world model", "월드 모델", "world simulator"]
  - id: humanoid-robot
    name: "Humanoid Robot"
    aliases: ["humanoid", "휴머노이드"]
""", encoding="utf-8")

    (registry_dir / "source_reputation.yaml").write_text("""
tiers:
  tier_1:
    score: 0.9
    sources: ["Reuters", "IEEE Spectrum", "Nature"]
  tier_2:
    score: 0.7
    sources: ["TechCrunch", "The Robot Report"]
  tier_3:
    score: 0.5
    sources: ["Reddit", "HackerNews"]
  tier_4:
    score: 0.3
    sources: ["X/Twitter"]
""", encoding="utf-8")

    return registry_dir
