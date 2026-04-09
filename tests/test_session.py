from src.gateway.base_adapter import LLMResponse


def make_mock_gateway():
    from src.gateway.gateway import LLMGateway
    from src.gateway.base_adapter import BaseAdapter

    class MockAdapter(BaseAdapter):
        def call(self, prompt: str, system: str | None = None, **kwargs) -> LLMResponse:
            return LLMResponse(content=f"response to: {prompt}", input_tokens=10, output_tokens=5)

        def call_with_history(self, messages: list[dict], system: str | None = None, **kwargs) -> LLMResponse:
            last = messages[-1]["content"]
            return LLMResponse(content=f"history response to: {last}", input_tokens=20, output_tokens=10)

    gw = LLMGateway()
    gw.register_adapter("test-model", MockAdapter())
    return gw


def test_session_tracks_history():
    from src.gateway.session import Session

    gateway = make_mock_gateway()
    session = Session(gateway=gateway, model="test-model", system="You are helpful.")

    response = session.send("hello")

    assert response.content == "history response to: hello"
    assert len(session.history) == 2  # user + assistant


def test_session_checkpoint_and_branch():
    from src.gateway.session import Session

    gateway = make_mock_gateway()
    session = Session(gateway=gateway, model="test-model")

    session.send("step 1 input")
    checkpoint = session.checkpoint()

    session.send("step 3 attempt 1")
    assert len(session.history) == 4  # 2 from step1 + 2 from step3

    branched = session.branch(checkpoint)
    assert len(branched.history) == 2  # only step 1 history

    branched.send("step 3 attempt 2")
    assert len(branched.history) == 4  # step1 + new step3
    assert len(session.history) == 4  # original unchanged
