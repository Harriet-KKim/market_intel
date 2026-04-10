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


def test_session_branch_system_override():
    """로컬 패치 I4: branch 시 system prompt만 교체할 수 있어야 한다.
    history(= Step 1 raw 데이터 기억)는 유지하고 role 지시만 분리한다."""
    from src.gateway.session import Session

    gateway = make_mock_gateway()
    session = Session(
        gateway=gateway,
        model="test-model",
        system="You are a consolidator.",
    )
    session.send("step 1 input")
    checkpoint = session.checkpoint()

    # 기본 동작: checkpoint.system을 그대로 이어받음
    default_branch = session.branch(checkpoint)
    assert default_branch._system == "You are a consolidator."
    assert len(default_branch.history) == 2

    # system_override: history는 유지, system만 교체
    reviewer_branch = session.branch(checkpoint, system_override="You are a reviewer.")
    assert reviewer_branch._system == "You are a reviewer."
    assert len(reviewer_branch.history) == 2
    # 원본 checkpoint는 영향 없음 (deepcopy 격리)
    assert checkpoint.system == "You are a consolidator."
