# 핵심 설계 포인트 (로컬 패치 I2):
# Checkpoint는 client-side deepcopy 기반입니다. Session.checkpoint()는
# copy.deepcopy(history)로 메시지 스냅샷을 만들고, Session.branch(checkpoint)는
# 그 스냅샷으로 새 Session을 초기화합니다.
# provider native checkpoint API (예: OpenAI `previous_response_id`,
# Anthropic conversation cache)가 아닙니다 — 모든 메시지는 매 호출마다
# 재전송되며 캐싱은 프로바이더 자동 prompt cache에만 의존합니다.
# 향후 provider-native checkpoint로 교체할 때는 Session/Checkpoint 인터페이스가
# 그대로 유지되도록 해야 Reviewer/RefinementPipeline이 깨지지 않습니다.
from __future__ import annotations

import copy
from dataclasses import dataclass

from src.gateway.base_adapter import LLMResponse
from src.gateway.gateway import LLMGateway


@dataclass
class Checkpoint:
    history: list[dict]
    system: str | None


class Session:
    def __init__(self, gateway: LLMGateway, model: str, system: str | None = None):
        self._gateway = gateway
        self._model = model
        self._system = system
        self.history: list[dict] = []

    def send(self, message: str) -> LLMResponse:
        """Send a message and append both user message and response to history."""
        self.history.append({"role": "user", "content": message})

        response = self._gateway.call_with_history(
            model=self._model,
            messages=self.history,
            system=self._system,
        )

        self.history.append({"role": "assistant", "content": response.content})
        return response

    def checkpoint(self) -> Checkpoint:
        """Save current history as a checkpoint for later branching."""
        return Checkpoint(
            history=copy.deepcopy(self.history),
            system=self._system,
        )

    def branch(
        self,
        checkpoint: Checkpoint,
        system_override: str | None = None,
    ) -> Session:
        """Create a new session branching from a checkpoint.

        로컬 패치 I4: system_override를 추가. Context Branching은 대화 기록(= Step 1
        raw 데이터 기억)을 공유하는 것이 목적이므로, role 지시(system prompt)는
        분기 시점에서 교체할 수 있어야 합니다. 예를 들어 Consolidator의 checkpoint
        에서 Reviewer로 분기할 때, history는 그대로 유지하되 "You are a reviewer"
        같은 별개 system을 주입해서 role mismatch를 방지합니다. `system_override`
        가 None이면 기존 동작(checkpoint.system 유지)과 동일.
        """
        system = system_override if system_override is not None else checkpoint.system
        new_session = Session(
            gateway=self._gateway,
            model=self._model,
            system=system,
        )
        new_session.history = copy.deepcopy(checkpoint.history)
        return new_session
