import pytest


def test_gateway_call_routes_to_adapter():
    from src.gateway.gateway import LLMGateway
    from src.gateway.base_adapter import BaseAdapter, LLMResponse

    class MockAdapter(BaseAdapter):
        def call(self, prompt: str, system: str | None = None, **kwargs) -> LLMResponse:
            return LLMResponse(content=f"mock: {prompt}", input_tokens=10, output_tokens=5)

        def call_with_history(self, messages: list[dict], system: str | None = None, **kwargs) -> LLMResponse:
            return LLMResponse(content="mock history", input_tokens=10, output_tokens=5)

    gateway = LLMGateway()
    gateway.register_adapter("mock-model", MockAdapter())

    response = gateway.call("mock-model", prompt="hello")

    assert response.content == "mock: hello"
    assert response.input_tokens == 10


def test_gateway_unknown_model_raises():
    from src.gateway.gateway import LLMGateway

    gateway = LLMGateway()

    with pytest.raises(KeyError, match="no-such-model"):
        gateway.call("no-such-model", prompt="hello")


def test_gateway_call_with_history():
    from src.gateway.gateway import LLMGateway
    from src.gateway.base_adapter import BaseAdapter, LLMResponse

    class MockAdapter(BaseAdapter):
        def call(self, prompt: str, system: str | None = None, **kwargs) -> LLMResponse:
            return LLMResponse(content="mock", input_tokens=0, output_tokens=0)

        def call_with_history(self, messages: list[dict], system: str | None = None, **kwargs) -> LLMResponse:
            last_msg = messages[-1]["content"]
            return LLMResponse(content=f"history: {last_msg}", input_tokens=20, output_tokens=10)

    gateway = LLMGateway()
    gateway.register_adapter("mock-model", MockAdapter())

    messages = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "response"},
        {"role": "user", "content": "second"},
    ]
    response = gateway.call_with_history("mock-model", messages=messages)

    assert response.content == "history: second"
