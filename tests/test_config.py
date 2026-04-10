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


def test_load_config_dedup_db_path_defaults_to_vault(tmp_path):
    """L3: config.yaml에 dedup 섹션이 없으면 `vault_path/.dedup.db` 사용."""
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
  gemini: "k1"
  openai: "k2"
  anthropic: "k3"
budget:
  enabled: false
  daily_limit_usd: 10.0
""")
    from src.config import load_config

    config = load_config(config_file)
    assert config.dedup_db_path == Path("./vault") / ".dedup.db"


def test_load_config_dedup_db_path_from_yaml(tmp_path):
    """L3: config.yaml의 dedup.db_path가 우선한다."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
vault_path: "./vault"
dedup:
  db_path: "/var/lib/market-intel/dedup.db"
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
  gemini: "k1"
  openai: "k2"
  anthropic: "k3"
budget:
  enabled: false
  daily_limit_usd: 10.0
""")
    from src.config import load_config

    config = load_config(config_file)
    assert config.dedup_db_path == Path("/var/lib/market-intel/dedup.db")


def test_load_config_collection_timezone_default(tmp_path):
    """L5: collection.timezone이 없으면 기본값 Asia/Seoul."""
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
  gemini: "k1"
  openai: "k2"
  anthropic: "k3"
budget:
  enabled: false
  daily_limit_usd: 10.0
""")
    from src.config import load_config

    config = load_config(config_file)
    assert config.collection.timezone == "Asia/Seoul"


def test_load_config_collection_timezone_override(tmp_path):
    """L5: collection.timezone이 명시되면 그 값 사용."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
vault_path: "./vault"
collection:
  interval_hours: 6
  timezone: "America/New_York"
  sources:
    rss: true
    web: true
    sns: true
    youtube: true
refinery:
  schedule_day: "monday"
  schedule_hour: 9
api_keys:
  gemini: "k1"
  openai: "k2"
  anthropic: "k3"
budget:
  enabled: false
  daily_limit_usd: 10.0
""")
    from src.config import load_config

    config = load_config(config_file)
    assert config.collection.timezone == "America/New_York"


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
