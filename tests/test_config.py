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


def test_load_config_refinery_enabled_defaults_to_true(tmp_path):
    """L20: refinery.enabled defaults to True when omitted."""
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
    assert config.refinery.enabled is True
    assert config.refinery.schedule_minute == 0


def test_load_config_refinery_enabled_explicit_false(tmp_path):
    """L20: refinery.enabled can be disabled explicitly."""
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
  enabled: false
  schedule_day: "monday"
  schedule_hour: 9
  schedule_minute: 30
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
    assert config.refinery.enabled is False
    assert config.refinery.schedule_minute == 30


def test_load_config_refinery_passthrough_day_string(tmp_path):
    """L20: schedule_day is passed through and normalized later by the scheduler."""
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
  schedule_day: "wed"
  schedule_hour: 14
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
    assert config.refinery.schedule_day == "wed"
    assert config.refinery.schedule_hour == 14
