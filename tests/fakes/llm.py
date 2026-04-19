from collections import defaultdict
from typing import Any

from llm.interface import LLMResult, Message, TaskSpec, Usage

_DUMMY_USAGE = Usage(
    input_tokens=10,
    output_tokens=20,
    cached_tokens=0,
    latency_ms=50,
    cost_usd=0.0001,
    model="fake-model",
    provider="fake",
)


class FakeLLMClient:
    """Scripted LLM client for tests. Raises if an unscripted call is made."""

    def __init__(self) -> None:
        self._scripts: dict[str, list[tuple[str, Any]]] = defaultdict(list)
        self.calls: list[tuple[TaskSpec, list[Message]]] = []

    def script(self, task_name: str, *, content: str = "", parsed: Any = None) -> None:
        self._scripts[task_name].append((content, parsed))

    async def complete(
        self,
        task: TaskSpec,
        messages: list[Message],
        *,
        response_model: type[Any] | None = None,
        user_id: int | None = None,
    ) -> LLMResult[Any]:
        self.calls.append((task, messages))

        queue = self._scripts.get(task.name)
        if not queue:
            raise AssertionError(
                f"FakeLLMClient: unexpected call to task {task.name!r}. "
                "Script it with fake.script(task_name, content=..., parsed=...)"
            )

        content, parsed = queue.pop(0)
        return LLMResult(content=content, parsed=parsed, usage=_DUMMY_USAGE)


class FakeTranscriptionClient:
    def __init__(self, result: str = "") -> None:
        self._result = result
        self.calls: list[tuple[bytes, str]] = []

    async def transcribe(self, audio_bytes: bytes, filename: str) -> str:
        self.calls.append((audio_bytes, filename))
        return self._result
