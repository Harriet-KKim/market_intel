from __future__ import annotations

from src.gateway.base_adapter import BaseAdapter, LLMResponse


class AnthropicAdapter(BaseAdapter):
    def __init__(self, client, model_id: str):
        self._client = client
        self._model_id = model_id

    def call(self, prompt: str, system: str | None = None, **kwargs) -> LLMResponse:
        params = {
            "model": self._model_id,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": kwargs.pop("max_tokens", 4096),
            **kwargs,
        }
        if system:
            params["system"] = system

        response = self._client.messages.create(**params)

        return LLMResponse(
            content=response.content[0].text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    def call_with_history(self, messages: list[dict], system: str | None = None, **kwargs) -> LLMResponse:
        params = {
            "model": self._model_id,
            "messages": messages,
            "max_tokens": kwargs.pop("max_tokens", 4096),
            **kwargs,
        }
        if system:
            params["system"] = system

        response = self._client.messages.create(**params)

        return LLMResponse(
            content=response.content[0].text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
