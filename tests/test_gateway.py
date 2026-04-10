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


def test_gemini_adapter_call(monkeypatch):
    from src.gateway.adapters.gemini import GeminiAdapter

    class MockResponse:
        text = "gemini response"
        usage_metadata = type("Usage", (), {"prompt_token_count": 15, "candidates_token_count": 8})()

    class MockModel:
        def generate_content(self, contents, **kwargs):
            return MockResponse()

    class MockClient:
        models = type("Models", (), {"generate_content": MockModel().generate_content})()

    adapter = GeminiAdapter(client=MockClient(), model_id="gemini-3.1-flash-lite-preview")
    response = adapter.call("test prompt")

    assert response.content == "gemini response"
    assert response.input_tokens == 15
    assert response.output_tokens == 8


def test_openai_adapter_call():
    from src.gateway.adapters.openai import OpenAIAdapter

    class MockMessage:
        content = "gpt response"

    class MockChoice:
        message = MockMessage()

    class MockUsage:
        prompt_tokens = 20
        completion_tokens = 12

    class MockCompletion:
        choices = [MockChoice()]
        usage = MockUsage()

    class MockChat:
        class completions:
            @staticmethod
            def create(**kwargs):
                return MockCompletion()

    class MockClient:
        chat = MockChat()

    adapter = OpenAIAdapter(client=MockClient(), model_id="gpt-5-pro")
    response = adapter.call("test prompt")

    assert response.content == "gpt response"
    assert response.input_tokens == 20
    assert response.output_tokens == 12


def test_anthropic_adapter_call():
    from src.gateway.adapters.anthropic import AnthropicAdapter

    class MockContentBlock:
        text = "claude response"

    class MockUsage:
        input_tokens = 25
        output_tokens = 15

    class MockResponse:
        content = [MockContentBlock()]
        usage = MockUsage()

    class MockMessages:
        def create(self, **kwargs):
            return MockResponse()

    class MockClient:
        messages = MockMessages()

    adapter = AnthropicAdapter(client=MockClient(), model_id="claude-opus-4-6")
    response = adapter.call("test prompt")

    assert response.content == "claude response"
    assert response.input_tokens == 25
    assert response.output_tokens == 15
