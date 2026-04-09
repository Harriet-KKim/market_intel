from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    content: str
    input_tokens: int
    output_tokens: int


class BaseAdapter(ABC):
    @abstractmethod
    def call(self, prompt: str, system: str | None = None, **kwargs) -> LLMResponse:
        """Single prompt call."""
        ...

    @abstractmethod
    def call_with_history(self, messages: list[dict], system: str | None = None, **kwargs) -> LLMResponse:
        """Call with conversation history for session continuity."""
        ...
