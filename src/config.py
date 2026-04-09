from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class SourcesConfig:
    rss: bool
    web: bool
    sns: bool
    youtube: bool


@dataclass
class CollectionConfig:
    interval_hours: int
    sources: SourcesConfig


@dataclass
class RefineryConfig:
    schedule_day: str
    schedule_hour: int


@dataclass
class ApiKeysConfig:
    gemini: str
    openai: str
    anthropic: str


@dataclass
class BudgetConfig:
    enabled: bool
    daily_limit_usd: float


@dataclass
class AppConfig:
    vault_path: Path
    collection: CollectionConfig
    refinery: RefineryConfig
    api_keys: ApiKeysConfig
    budget: BudgetConfig


def _substitute_env_vars(value: str) -> str:
    """Replace ${VAR_NAME} with environment variable value."""
    def replacer(match):
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))
    return re.sub(r"\$\{(\w+)\}", replacer, value)


def _process_env_vars(data: dict) -> dict:
    """Recursively substitute environment variables in string values."""
    result = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = _process_env_vars(value)
        elif isinstance(value, str):
            result[key] = _substitute_env_vars(value)
        else:
            result[key] = value
    return result


def load_config(path: Path) -> AppConfig:
    """Load and parse config from a YAML file."""
    with open(path) as f:
        raw = yaml.safe_load(f)

    data = _process_env_vars(raw)

    return AppConfig(
        vault_path=Path(data["vault_path"]),
        collection=CollectionConfig(
            interval_hours=data["collection"]["interval_hours"],
            sources=SourcesConfig(**data["collection"]["sources"]),
        ),
        refinery=RefineryConfig(
            schedule_day=data["refinery"]["schedule_day"],
            schedule_hour=data["refinery"]["schedule_hour"],
        ),
        api_keys=ApiKeysConfig(
            gemini=data["api_keys"]["gemini"],
            openai=data["api_keys"]["openai"],
            anthropic=data["api_keys"]["anthropic"],
        ),
        budget=BudgetConfig(
            enabled=data["budget"]["enabled"],
            daily_limit_usd=data["budget"]["daily_limit_usd"],
        ),
    )
