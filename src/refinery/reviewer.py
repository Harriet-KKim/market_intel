from __future__ import annotations

from src.gateway.gateway import LLMGateway
from src.gateway.session import Session, Checkpoint
from src.writer.frontmatter import parse_document
from src.writer.vault import VaultManager
from src.writer.weekly_writer import WeeklyWriter


# 로컬 패치 I4: Reviewer 전용 system prompt.
# 원본 플랜은 Step 1 checkpoint를 그대로 branch해 Consolidator의 "너는 통합자다"
# system prompt를 물려받았습니다. 역할이 "검토"가 아닌 "재통합"으로 편향될 위험이
# 있어 `Session.branch(..., system_override=REVIEWER_SYSTEM)`으로 덮어씁니다.
# history(원본 raw 기억)는 유지되므로 "원본을 아는 검토자"라는 설계 의도는 그대로.
REVIEWER_SYSTEM = """You are a senior Physical AI market strategist acting as a reviewer.
You previously saw the raw data during Step 1 consolidation (it is present in the conversation
history above). Use that memory to audit the weekly snapshot that follows.
Focus on: factual omissions vs. the raw corpus, overstatements, reliability calls, and
cross-company / cross-topic relationship accuracy. Do NOT re-consolidate. Do NOT rewrite
the snapshot. Produce a concise reviewer's note only."""

REVIEW_PROMPT = """다음은 Claude Opus가 생성한 주간 요약본입니다.
당신은 Step 1에서 원본 raw 데이터를 직접 읽었으므로, 그 기억을 기반으로 이 요약을 검토하세요.

## 주간 스냅샷
{snapshot}

## 검토 기준
1. 원본 데이터 대비 누락된 중요 정보가 있는가?
2. 사실이 왜곡되거나 과장된 부분이 있는가?
3. 신뢰도 판정이 적절한가?
4. 회사/주제 간 관계가 올바르게 반영되었는가?

검토 결과를 간결하게 작성하세요."""


class Reviewer:
    def __init__(
        self,
        gateway: LLMGateway,
        model: str,
        vault: VaultManager,
        weekly_writer: WeeklyWriter,
    ):
        self._gateway = gateway
        self._model = model
        self._vault = vault
        self._weekly_writer = weekly_writer

    def run(self, week: str, checkpoint: Checkpoint) -> str:
        """Run review by branching from the consolidation checkpoint."""
        # 1. Read snapshot
        snapshot_path = self._vault.weekly_dir / f"{week}.md"
        _, snapshot_body = parse_document(snapshot_path.read_text(encoding="utf-8"))

        # 2. Branch from the Step 1 checkpoint via Session.branch().
        #    (로컬 패치 I1) 원본 플랜은 Session 객체를 수동 생성한 뒤
        #    `session.history = list(checkpoint.history)`로 내부 상태를 인라인 복원했습니다.
        #    이 방식은 Session/Checkpoint 추상화를 우회하고, `copy.deepcopy`로 얻는
        #    격리성을 잃게 합니다. `Session.branch(checkpoint, ...)`를 사용해 일관된
        #    Context Branching API로 정렬합니다 — 이 분기는 Step 1(원본 데이터 통합)
        #    컨텍스트는 유지하지만 Step 2(Claude Opus summarization) 산출물은
        #    포함하지 않습니다.
        #    (로컬 패치 I4) system prompt는 `REVIEWER_SYSTEM`으로 덮어씁니다. Step 1의
        #    Consolidator system ("너는 통합자다")을 그대로 상속하면 reviewer가 다시
        #    통합 응답을 생성할 수 있습니다. history는 유지되므로 "원본을 아는 검토자"
        #    라는 설계 의도는 지켜집니다.
        seed = Session(gateway=self._gateway, model=self._model)
        session = seed.branch(checkpoint, system_override=REVIEWER_SYSTEM)

        # 3. Send review request
        prompt = REVIEW_PROMPT.format(snapshot=snapshot_body)
        response = session.send(prompt)

        # 4. Append review as comment
        self._weekly_writer.append_review(week, response.content)

        return response.content
