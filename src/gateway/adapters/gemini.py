from __future__ import annotations

from src.gateway.base_adapter import BaseAdapter, LLMResponse


class GeminiAdapter(BaseAdapter):
    def __init__(self, client, model_id: str):
        self._client = client
        self._model_id = model_id

    def call(self, prompt: str, system: str | None = None, **kwargs) -> LLMResponse:
        contents = prompt
        if system:
            contents = f"{system}\n\n{prompt}"

        response = self._client.models.generate_content(
            contents=contents,
            model=self._model_id,
            **kwargs,
        )

        return LLMResponse(
            content=response.text,
            input_tokens=response.usage_metadata.prompt_token_count,
            output_tokens=response.usage_metadata.candidates_token_count,
        )

    def call_with_history(self, messages: list[dict], system: str | None = None, **kwargs) -> LLMResponse:
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        response = self._client.models.generate_content(
            contents=contents,
            model=self._model_id,
            **kwargs,
        )

        return LLMResponse(
            content=response.text,
            input_tokens=response.usage_metadata.prompt_token_count,
            output_tokens=response.usage_metadata.candidates_token_count,
        )
