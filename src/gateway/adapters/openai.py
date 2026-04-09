from __future__ import annotations

from src.gateway.base_adapter import BaseAdapter, LLMResponse


class OpenAIAdapter(BaseAdapter):
    def __init__(self, client, model_id: str):
        self._client = client
        self._model_id = model_id

    def call(self, prompt: str, system: str | None = None, **kwargs) -> LLMResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self._client.chat.completions.create(
            model=self._model_id,
            messages=messages,
            **kwargs,
        )

        return LLMResponse(
            content=response.choices[0].message.content,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )

    def call_with_history(self, messages: list[dict], system: str | None = None, **kwargs) -> LLMResponse:
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        response = self._client.chat.completions.create(
            model=self._model_id,
            messages=full_messages,
            **kwargs,
        )

        return LLMResponse(
            content=response.choices[0].message.content,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )
