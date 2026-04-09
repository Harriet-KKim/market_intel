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

    def branch(self, checkpoint: Checkpoint) -> Session:
        """Create a new session branching from a checkpoint."""
        new_session = Session(
            gateway=self._gateway,
            model=self._model,
            system=checkpoint.system,
        )
        new_session.history = copy.deepcopy(checkpoint.history)
        return new_session
