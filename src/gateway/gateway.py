from __future__ import annotations

from src.gateway.base_adapter import BaseAdapter, LLMResponse


class LLMGateway:
    def __init__(self):
        self._adapters: dict[str, BaseAdapter] = {}

    def register_adapter(self, model_name: str, adapter: BaseAdapter) -> None:
        self._adapters[model_name] = adapter

    def call(self, model: str, prompt: str, system: str | None = None, **kwargs) -> LLMResponse:
        adapter = self._get_adapter(model)
        return adapter.call(prompt=prompt, system=system, **kwargs)

    def call_with_history(self, model: str, messages: list[dict], system: str | None = None, **kwargs) -> LLMResponse:
        adapter = self._get_adapter(model)
        return adapter.call_with_history(messages=messages, system=system, **kwargs)

    def _get_adapter(self, model: str) -> BaseAdapter:
        if model not in self._adapters:
            raise KeyError(f"No adapter registered for model: {model}")
        return self._adapters[model]
