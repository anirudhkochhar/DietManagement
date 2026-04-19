---
name: llm-router
description: The LLM provider abstraction and cost-aware routing contract. Read before adding or modifying any LLM call in the bot. Defines the interface, task classes, provider adapters, logging, and mocking approach.
---

# LLM router

The bot never talks to an LLM SDK directly. It talks to `LLMClient`, backed by a router that picks a model based on a declared task class. Swapping DeepSeek ↔ Claude ↔ anything OpenAI-compatible is a config change, not a code change.

## The interface (target shape)

```python
# llm/interface.py
class TaskClass(StrEnum):
    TRIVIAL = "trivial"
    STANDARD = "standard"
    REASONING = "reasoning"

class TaskSpec(BaseModel):
    name: str                    # stable identifier for logs and metrics
    task_class: TaskClass

class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str
    cache: bool = False          # hint to the provider adapter

class Usage(BaseModel):
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

class LLMClient(Protocol):
    async def complete(
        self,
        task: TaskSpec,
        messages: list[Message],
        *,
        response_model: type[T] | None = None,
    ) -> LLMResult[T]: ...
```

Callers import `LLMClient`, `TaskSpec`, `TaskClass`, `Message` — nothing else from `llm/`.

## Task class → model mapping

Defined in `config/settings.py`, overridable by env:

| Task class | Default (budget) | Default (quality) | Typical use |
|---|---|---|---|
| `trivial` | `deepseek-chat` | `claude-haiku-4-5-20251001` | classification, keyword extraction, short routing decisions |
| `standard` | `deepseek-chat` | `claude-sonnet-4-6` | meal parsing, friendly replies, summaries |
| `reasoning` | `claude-sonnet-4-6` | `claude-opus-4-7` | multi-day plans, nutrition critique, chain-of-thought tasks |

Env overrides: `LLM_MODEL_TRIVIAL`, `LLM_MODEL_STANDARD`, `LLM_MODEL_REASONING`, `LLM_PROVIDER_<MODEL>` for provider binding.

## Providers

Each provider is an adapter in `llm/providers/` implementing:

```python
class Provider(Protocol):
    async def call(
        self,
        model: str,
        messages: list[Message],
        *,
        response_schema: dict[str, Any] | None = None,
    ) -> RawResult: ...
```

Ship with:
- `anthropic.py` — wraps `anthropic` SDK. Supports `cache_control` for prompt caching.
- `deepseek.py` — wraps an OpenAI-compatible client pointed at DeepSeek's base URL. Reuse the same adapter for any OpenAI-compatible provider by changing the base URL.

Add a new provider by implementing the protocol and registering it in `llm/providers/__init__.py`. No other file changes.

## Structured output

When a caller passes `response_model=SomeModel`:

1. The router appends a JSON-schema instruction to the system prompt.
2. Calls the provider, receives raw text.
3. Parses into the Pydantic model.
4. On parse failure: retry once, optionally at one class higher (configurable, off by default — retrying costs money).

Callers don't parse JSON themselves.

## Logging and cost accounting

Every call emits a `structlog` event `llm.call` with the full `Usage` payload plus `task_name`, `task_class`.

Cost comes from a price table keyed by model:

```python
# llm/pricing.py
PRICES: Final[dict[str, ModelPrice]] = {
    "deepseek-chat": ModelPrice(input=0.14, output=0.28, cached=0.014),  # $/MTok — verify before shipping
    "claude-haiku-4-5-20251001": ModelPrice(...),
    "claude-sonnet-4-6": ModelPrice(...),
    ...
}
```

Prices are approximate and must be reviewed against current provider docs before shipping to prod. Out-of-date prices make budget enforcement wrong.

## Budget middleware

A `BudgetGuard` wraps `LLMClient` and enforces:
- Per-user daily USD ceiling.
- Global hourly ceiling (cheap safety net against runaway loops).

When a ceiling is hit, the guard can either reject the call or downgrade its task class one step — configurable.

## Mocking

`tests/fakes/llm.py` provides `FakeLLMClient`:

- Queue scripted responses per `task.name` via `fake.script("log_meal", content="...", parsed=MealInputModel(...))`.
- Records every call for later assertion.
- Raises if any call is made without a scripted response — this catches accidental real API usage.

Every unit test uses `FakeLLMClient`. Tests never import provider adapters.

## Rules for callers

- Import only `LLMClient`, `TaskSpec`, `TaskClass`, `Message` from `llm/`.
- Declare task class honestly. Don't upsell to `reasoning` because "it'll be better" — ship it at a lower class, measure, then justify the upgrade if needed.
- Always pass `response_model=...` when you need structured output.
- Never concatenate raw user input into system prompts without length caps and escaping.
- Always pass a stable `task.name` — logs and metrics key on it.
