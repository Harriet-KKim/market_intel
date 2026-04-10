from __future__ import annotations

import argparse
import logging
from pathlib import Path

from src.config import load_config
from src.registry import Registry
from src.dedup import UrlDedup
from src.gateway.gateway import LLMGateway
from src.writer.vault import VaultManager
from src.writer.raw_writer import RawWriter
from src.writer.profile_writer import ProfileWriter
from src.collector.pipeline import CollectionPipeline
from src.refinery.pipeline import RefinementPipeline
from src.scheduler.scheduler import IntelScheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# 로컬 패치 I3: `init` 커맨드가 Registry YAML 파일을 자동 생성하도록 템플릿 추가.
# 원본 플랜은 사용자가 이 파일들을 수동으로 먼저 만들어야 `init`이 동작했습니다.
REGISTRY_TEMPLATES: dict[str, str] = {
    "companies.yaml": """# Physical AI 관심 회사 레지스트리.
# 자유롭게 추가/편집하세요. Obsidian에서 이 파일을 열어 수정할 수 있습니다.
companies:
  - id: nvidia
    name: NVIDIA
    aliases: [엔비디아, Nvidia]
    sources:
      rss: []
      official: []
      youtube: []
  - id: tesla
    name: Tesla
    aliases: [테슬라]
    sources:
      rss: []
      official: []
      youtube: []
""",
    "keywords.yaml": """# 추적할 Physical AI 기술/주제 키워드.
keywords:
  - id: humanoid-robot
    name: humanoid-robot
    aliases: [휴머노이드, humanoid]
  - id: world-model
    name: world-model
    aliases: [월드모델, "world model"]
  - id: autonomous-driving
    name: autonomous-driving
    aliases: [자율주행, autonomous]
  - id: embodied-ai
    name: embodied-ai
    aliases: [embodied, 체화지능]
""",
    # 로컬 패치 C4: 원본 플랜의 템플릿은 `tier_1: 0.9` 같은 float value만 가진 평면
    # 구조였습니다. 그러나 `src/registry.py::Registry._load_reputation`는 각 tier에서
    # `tier_data["score"]`와 `tier_data["sources"]`를 꺼내므로, 평면 템플릿을 그대로
    # 두면 `init` 직후 첫 `collect`/`refine` 호출이 `TypeError: 'float' object is not
    # subscriptable`로 크래시합니다. 02-registry.md의 `test_get_reputation_score`가
    # 기대하는 nested `{score, sources}` 스키마와 일치시키고, 기본 tier 예시도 채워
    # 사용자가 바로 참고/편집할 수 있도록 합니다.
    "source_reputation.yaml": """# 소스별 신뢰도 tier. Obsidian에서 이 파일을 편집하면 됩니다.
# tier_1=0.9 / tier_2=0.7 / tier_3=0.5 / tier_4=0.3 (주간 정제 단계가 교차 검증 후 덮어쓸 수 있음)
tiers:
  tier_1:
    score: 0.9
    sources:
      - Reuters
      - IEEE Spectrum
      - Nature
      - Science Robotics
  tier_2:
    score: 0.7
    sources:
      - TechCrunch
      - The Robot Report
      - The Verge
  tier_3:
    score: 0.5
    sources:
      - Reddit
      - HackerNews
  tier_4:
    score: 0.3
    sources:
      - "X/Twitter"
""",
}


def setup_gateway(config) -> LLMGateway:
    """Initialize LLM Gateway with configured adapters."""
    gateway = LLMGateway()

    # Gemini (collection tagging)
    from google import genai
    from src.gateway.adapters.gemini import GeminiAdapter
    gemini_client = genai.Client(api_key=config.api_keys.gemini)
    gateway.register_adapter("gemini", GeminiAdapter(client=gemini_client, model_id="gemini-3.1-flash-lite-preview"))

    # OpenAI GPT5 Pro (consolidation + review)
    from openai import OpenAI
    from src.gateway.adapters.openai import OpenAIAdapter
    openai_client = OpenAI(api_key=config.api_keys.openai)
    gateway.register_adapter("gpt5-pro", OpenAIAdapter(client=openai_client, model_id="gpt-5-pro"))

    # Anthropic Claude (summarization)
    from anthropic import Anthropic
    from src.gateway.adapters.anthropic import AnthropicAdapter
    anthropic_client = Anthropic(api_key=config.api_keys.anthropic)
    gateway.register_adapter("claude-opus", AnthropicAdapter(client=anthropic_client, model_id="claude-opus-4-6"))

    return gateway


def init_vault(config) -> None:
    """Initialize vault: directory structure → registry YAML templates → profile stubs.

    로컬 패치 C2·I3: 원본 플랜은 Registry가 이미 로드된 상태를 전제로 프로필만 생성했으나,
    최초 실행 시 `vault/registry/*.yaml` 파일이 존재하지 않으면 `Registry(...)` 생성 자체가
    실패합니다. 이 함수는 (1) Vault 골격 생성 → (2) Registry YAML 템플릿 씨드 → (3) Registry
    로드 후 회사/키워드 프로필 생성의 순서를 보장합니다.
    """
    # 1) Vault 디렉터리 생성 (companies/, topics/, raw/, weekly/, registry/)
    vault = VaultManager(config.vault_path)

    # 2) Registry YAML 템플릿 씨드 (이미 존재하면 건너뜀)
    registry_dir = config.vault_path / "registry"
    registry_dir.mkdir(parents=True, exist_ok=True)
    for filename, template_body in REGISTRY_TEMPLATES.items():
        target = registry_dir / filename
        if target.exists():
            logger.info(f"Registry file exists, skipping: {target.name}")
            continue
        target.write_text(template_body, encoding="utf-8")
        logger.info(f"Created registry template: {target.name}")

    # 3) 템플릿이 자리잡은 뒤 Registry 로드 → 프로필 생성
    registry = Registry(registry_dir)
    profile_writer = ProfileWriter(vault)

    for company in registry.companies:
        path = vault.companies_dir / f"{company.name}.md"
        if not path.exists():
            profile_writer.create_company(company.name, company.aliases)
            logger.info(f"Created company profile: {company.name}")

    for keyword in registry.keywords:
        path = vault.topics_dir / f"{keyword.name}.md"
        if not path.exists():
            profile_writer.create_topic(keyword.name, keyword.aliases)
            logger.info(f"Created topic profile: {keyword.name}")


def main():
    parser = argparse.ArgumentParser(description="Physical AI Market Intelligence System")
    parser.add_argument("command", choices=["collect", "refine", "schedule", "init"],
                        help="collect: run one collection cycle, refine: run weekly refinement, schedule: start scheduler, init: initialize vault")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    parser.add_argument("--week", help="Week identifier for refinement (e.g., 2026-W15)")
    parser.add_argument("--date-range", help="Date range for refinement (e.g., 2026-04-06 ~ 2026-04-12)")
    args = parser.parse_args()

    config = load_config(Path(args.config))

    # 로컬 패치 C2: `init` 분기는 Registry 로딩 *전*에 처리. init 자체가 Registry YAML을
    # 생성하는 임무를 맡고 있으므로, 전역에서 `Registry(...)`를 먼저 호출하면 최초 실행 시
    # FileNotFoundError로 크래시합니다.
    if args.command == "init":
        init_vault(config)
        logger.info("Vault initialized")
        return

    # init이 아닌 나머지 분기는 Registry가 이미 존재한다고 가정.
    vault = VaultManager(config.vault_path)
    registry = Registry(config.vault_path / "registry")
    gateway = setup_gateway(config)
    # 로컬 패치 L3: dedup.db는 CWD 상대경로가 아닌 config 기반 절대 경로 사용.
    # 기본값은 `vault_path / ".dedup.db"`로 설정되며, `src/config.py::load_config`에서
    # `dedup.db_path` 키로 오버라이드할 수 있다. 부모 디렉터리가 없으면 만들어 준다.
    config.dedup_db_path.parent.mkdir(parents=True, exist_ok=True)
    dedup = UrlDedup(config.dedup_db_path)
    raw_writer = RawWriter(vault)

    if args.command == "collect":
        pipeline = CollectionPipeline(
            gateway=gateway, tagging_model="gemini",
            registry=registry, dedup=dedup, raw_writer=raw_writer,
        )
        scheduler = IntelScheduler(config=config, registry=registry, pipeline=pipeline)
        scheduler.run_once()

    elif args.command == "refine":
        if not args.week or not args.date_range:
            parser.error("--week and --date-range are required for refine command")
        pipeline = RefinementPipeline(
            gateway=gateway,
            consolidation_model="gpt5-pro",
            summarization_model="claude-opus",
            review_model="gpt5-pro",
            vault=vault,
            registry=registry,
        )
        pipeline.run(week=args.week, date_range=args.date_range)

    elif args.command == "schedule":
        collection_pipeline = CollectionPipeline(
            gateway=gateway, tagging_model="gemini",
            registry=registry, dedup=dedup, raw_writer=raw_writer,
        )
        scheduler = IntelScheduler(config=config, registry=registry, pipeline=collection_pipeline)
        scheduler.start()


if __name__ == "__main__":
    main()
