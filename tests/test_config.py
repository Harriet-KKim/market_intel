import os
from pathlib import Path


def test_load_config_from_yaml(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
vault_path: "./vault"
collection:
  interval_hours: 6
  sources:
    rss: true
    web: true
    sns: false
    youtube: true
refinery:
  schedule_day: "monday"
  schedule_hour: 9
api_keys:
  gemini: "test-gemini-key"
  openai: "test-openai-key"
  anthropic: "test-anthropic-key"
budget:
  enabled: false
  daily_limit_usd: 10.0
""")
    from src.config import load_config

    config = load_config(config_file)

    assert config.vault_path == Path("./vault")
    assert config.collection.interval_hours == 6
    assert config.collection.sources.rss is True
    assert config.collection.sources.sns is False
    assert config.refinery.schedule_day == "monday"
    assert config.api_keys.gemini == "test-gemini-key"
    assert config.budget.enabled is False


def test_load_config_env_var_substitution(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "env-gemini-key")
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
vault_path: "./vault"
collection:
  interval_hours: 6
  sources:
    rss: true
    web: true
    sns: true
    youtube: true
refinery:
  schedule_day: "monday"
  schedule_hour: 9
api_keys:
  gemini: "${GEMINI_API_KEY}"
  openai: "direct-key"
  anthropic: "direct-key"
budget:
  enabled: false
  daily_limit_usd: 10.0
""")
    from src.config import load_config

    config = load_config(config_file)

    assert config.api_keys.gemini == "env-gemini-key"
    assert config.api_keys.openai == "direct-key"
