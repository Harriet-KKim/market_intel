from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
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
    # 로컬 패치 L5: Scheduler가 명시적인 timezone으로 실행되도록 선언. 컨테이너/서버의
    # 시스템 TZ에 의존하면 배포 환경마다 실제 실행 시각이 달라지는 문제를 막기 위함.
    timezone: str = "Asia/Seoul"


@dataclass
class RefineryConfig:
    schedule_day: str
    schedule_hour: int
    enabled: bool = True
    schedule_minute: int = 0


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
    # 로컬 패치 L3: dedup.db를 CWD 상대경로가 아니라 절대 경로로 보관. 기본값은
    # `vault_path / ".dedup.db"`(vault 안 숨김 파일)이며, config.yaml의 `dedup.db_path`로
    # 오버라이드 가능. main.py가 다른 디렉터리에서 실행돼도 dedup 상태가 보존됩니다.
    dedup_db_path: Path = field(default_factory=lambda: Path("dedup.db"))


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
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    data = _process_env_vars(raw)

    vault_path = Path(data["vault_path"])

    # 로컬 패치 L3: dedup.db 경로는 config 우선, 없으면 vault 내부 숨김 파일.
    dedup_section = data.get("dedup") or {}
    dedup_raw = dedup_section.get("db_path")
    dedup_db_path = Path(dedup_raw) if dedup_raw else vault_path / ".dedup.db"

    return AppConfig(
        vault_path=vault_path,
        collection=CollectionConfig(
            interval_hours=data["collection"]["interval_hours"],
            sources=SourcesConfig(**data["collection"]["sources"]),
            # 로컬 패치 L5: timezone은 선택 필드, 기본 Asia/Seoul.
            timezone=data["collection"].get("timezone", "Asia/Seoul"),
        ),
        refinery=RefineryConfig(
            schedule_day=data["refinery"]["schedule_day"],
            schedule_hour=data["refinery"]["schedule_hour"],
            enabled=data["refinery"].get("enabled", True),
            schedule_minute=data["refinery"].get("schedule_minute", 0),
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
        dedup_db_path=dedup_db_path,
    )
