# 04. LLM Gateway — 구현 계획

> 이 파일은 전체 구현 플랜의 일부입니다.
> 인덱스: [README.md](./README.md) · 원본 통합본: [../superpowers/plans/2026-04-09-market-intel-implementation.md](../superpowers/plans/2026-04-09-market-intel-implementation.md) · 설계 스펙: [../superpowers/specs/2026-04-09-market-intel-system-design.md](../superpowers/specs/2026-04-09-market-intel-system-design.md)

**모듈:** `src/gateway/` (base_adapter, gateway, session, adapters/{gemini,openai,anthropic})
**역할:** 모델 종류에 무관한 통합 LLM 호출 인터페이스, 모델별 Adapter, 세션/Checkpoint/Branching 관리
**핵심 설계 포인트:**
- **Context Branching**: Step 1(Consolidator)에서 저장한 Checkpoint로부터 Step 3(Reviewer)가 분기. 피드백 루프가 누적되지 않도록 원본 세션을 건드리지 않고 새 Session을 생성.
- **Checkpoint는 client-side deepcopy 기반** (로컬 패치 I2 주석): `Session.checkpoint()`는 `copy.deepcopy(history)`로 메시지 스냅샷을 만들고, `Session.branch(checkpoint)`는 그 스냅샷으로 새 Session을 초기화합니다. **provider native checkpoint API (예: OpenAI `previous_response_id`, Anthropic conversation cache)가 아닙니다** — 모든 메시지는 매 호출마다 재전송되며 캐싱은 프로바이더 자동 prompt cache에만 의존합니다. 향후 provider-native checkpoint로 교체할 때는 `Session`/`Checkpoint` 인터페이스가 그대로 유지되도록 해야 `Reviewer`/`RefinementPipeline`이 깨지지 않습니다.
- **`Session.branch(system_override=...)`** (로컬 패치 I4): 분기 시 system prompt만 교체할 수 있는 옵션. Context Branching은 *대화 기록(= Step 1의 raw 데이터 기억)*을 공유하는 것이 목적이지 role 지시까지 이어받을 이유는 없습니다. Reviewer는 Consolidator와 동일 모델(GPT5 Pro)을 쓰지만 수행 역할이 다르므로 system prompt는 별도 주입이 자연스럽습니다. `system_override=None`이면 기존 동작(checkpoint.system 유지)과 동일.
- Gateway는 얇은 라우팅 레이어 — 모델 추가 시 `BaseAdapter` 서브클래스 + `register_adapter()`만 필요.

**선행 의존:** [01-config.md](./01-config.md), [03-dedup.md](./03-dedup.md)
**다음 단계:** [05-writer.md](./05-writer.md)

포함 태스크:
- [Task 4: Base Adapter & Gateway Interface](#task-4-base-adapter--gateway-interface)
- [Task 5: Model Adapters (Gemini, OpenAI, Anthropic)](#task-5-model-adapters-gemini-openai-anthropic)
- [Task 6: Session Management (Context Branching)](#task-6-session-management-context-branching)

---

## Phase 2: LLM Gateway

### Task 4: Base Adapter & Gateway Interface

**Files:**
- Create: `src/gateway/__init__.py`
- Create: `src/gateway/base_adapter.py`
- Create: `src/gateway/gateway.py`
- Create: `src/gateway/adapters/__init__.py`
- Create: `tests/test_gateway.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_gateway.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_gateway.py -v`
Expected: FAIL

- [ ] **Step 3: Implement base adapter and gateway**

```python
# src/gateway/__init__.py
```

```python
# src/gateway/adapters/__init__.py
```

```python
# src/gateway/base_adapter.py
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
```

```python
# src/gateway/gateway.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_gateway.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/gateway/ tests/test_gateway.py
git commit -m "feat: LLM Gateway with base adapter interface"
```

---

### Task 5: Model Adapters (Gemini, OpenAI, Anthropic)

**Files:**
- Create: `src/gateway/adapters/gemini.py`
- Create: `src/gateway/adapters/openai.py`
- Create: `src/gateway/adapters/anthropic.py`

Each adapter wraps the respective SDK. Tests use monkeypatching to avoid real API calls.

- [ ] **Step 1: Write failing test for Gemini adapter**

```python
# tests/test_gateway.py (append to existing file)


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

    adapter = GeminiAdapter(client=MockClient(), model_id="gemini-2.0-flash")
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_gateway.py -v -k "adapter"`
Expected: FAIL

- [ ] **Step 3: Implement Gemini adapter**

```python
# src/gateway/adapters/gemini.py
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
        # Gemini uses contents list format
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
```

- [ ] **Step 4: Implement OpenAI adapter**

```python
# src/gateway/adapters/openai.py
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
```

- [ ] **Step 5: Implement Anthropic adapter**

```python
# src/gateway/adapters/anthropic.py
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
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_gateway.py -v`
Expected: 6 passed

- [ ] **Step 7: Commit**

```bash
git add src/gateway/adapters/
git commit -m "feat: Gemini, OpenAI, and Anthropic adapters for LLM Gateway"
```

---

### Task 6: Session Management (Context Branching)

**Files:**
- Create: `src/gateway/session.py`
- Create: `tests/test_session.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_session.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_session.py -v`
Expected: FAIL

- [ ] **Step 3: Implement session management**

```python
# src/gateway/session.py
from __future__ import annotations

import copy
from dataclasses import dataclass, field

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

    def branch(
        self,
        checkpoint: Checkpoint,
        system_override: str | None = None,
    ) -> Session:
        """Create a new session branching from a checkpoint.

        로컬 패치 I4: system_override를 추가. Context Branching은 대화 기록(= Step 1
        raw 데이터 기억)을 공유하는 것이 목적이므로, role 지시(system prompt)는
        분기 시점에서 교체할 수 있어야 합니다. 예를 들어 Consolidator의 checkpoint
        에서 Reviewer로 분기할 때, history는 그대로 유지하되 "You are a reviewer"
        같은 별개 system을 주입해서 role mismatch를 방지합니다. `system_override`
        가 None이면 기존 동작(checkpoint.system 유지)과 동일.
        """
        system = system_override if system_override is not None else checkpoint.system
        new_session = Session(
            gateway=self._gateway,
            model=self._model,
            system=system,
        )
        new_session.history = copy.deepcopy(checkpoint.history)
        return new_session
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_session.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/gateway/session.py tests/test_session.py
git commit -m "feat: session management with checkpoint and context branching"
```
