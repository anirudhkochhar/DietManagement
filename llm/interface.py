from enum import StrEnum
from typing import Any, Generic, Literal, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class LLMParseError(Exception):
    pass


class TaskClass(StrEnum):
    TRIVIAL = "trivial"
    STANDARD = "standard"
    REASONING = "reasoning"


class TaskSpec(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    task_class: TaskClass
    requires_vision: bool = False


class TextContent(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["text"] = "text"
    text: str


class ImageContent(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["image"] = "image"
    base64_data: str
    media_type: str  # e.g. "image/jpeg"


MessagePart = TextContent | ImageContent


class Message(BaseModel):
    model_config = ConfigDict(frozen=True)
    role: Literal["system", "user", "assistant"]
    content: str | list[MessagePart]
    cache: bool = False


class Usage(BaseModel):
    model_config = ConfigDict(frozen=True)
    input_tokens: int
    output_tokens: int
    cached_tokens: int = 0
    latency_ms: int
    cost_usd: float
    model: str
    provider: str


class LLMResult(BaseModel, Generic[T]):
    content: str
    parsed: T | None = None
    usage: Usage


class RawResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    content: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int = 0
    model: str


@runtime_checkable
class LLMClient(Protocol):
    async def complete(
        self,
        task: TaskSpec,
        messages: list[Message],
        *,
        response_model: type[Any] | None = None,
        user_id: int | None = None,
    ) -> LLMResult[Any]: ...


@runtime_checkable
class Provider(Protocol):
    async def call(
        self,
        model: str,
        messages: list[Message],
        *,
        response_schema: dict[str, Any] | None = None,
    ) -> RawResult: ...


@runtime_checkable
class TranscriptionClient(Protocol):
    async def transcribe(self, audio_bytes: bytes, filename: str) -> str: ...
