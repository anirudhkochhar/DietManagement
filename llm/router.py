import asyncio
import json
import time
from collections import defaultdict
from typing import Any

import pydantic
import structlog

from llm.interface import (
    LLMClient,
    LLMParseError,
    LLMResult,
    Message,
    Provider,
    RawResult,
    TaskClass,
    TaskSpec,
    Usage,
)
from llm.pricing import calculate_cost

logger = structlog.get_logger()


class BudgetExceeded(Exception):
    pass


class Router:
    """Picks a provider+model based on task class, logs cost, and routes the call."""

    def __init__(
        self,
        providers: dict[str, Provider],
        model_for_class: dict[TaskClass, str],
        vision_model: str,
    ) -> None:
        self._providers = providers
        self._model_for_class = model_for_class
        self._vision_model = vision_model

    def _resolve_model(self, task: TaskSpec) -> str:
        if task.requires_vision:
            return self._vision_model
        return self._model_for_class[task.task_class]

    def _pick_provider(self, model: str) -> Provider:
        # anthropic models → anthropic adapter; everything else → deepseek/OpenAI-compat adapter
        if model.startswith("claude-"):
            provider = self._providers.get("anthropic")
        else:
            provider = self._providers.get("deepseek")
        if provider is None:
            raise RuntimeError(f"No provider configured for model {model!r}")
        return provider

    async def complete(
        self,
        task: TaskSpec,
        messages: list[Message],
        *,
        response_model: type[Any] | None = None,
        user_id: int | None = None,
    ) -> LLMResult[Any]:
        model = self._resolve_model(task)
        provider = self._pick_provider(model)
        schema = response_model.model_json_schema() if response_model is not None else None

        t0 = time.monotonic()
        raw: RawResult = await provider.call(model, messages, response_schema=schema)
        latency_ms = int((time.monotonic() - t0) * 1000)

        cost = calculate_cost(model, raw.input_tokens, raw.output_tokens, raw.cached_tokens)
        usage = Usage(
            input_tokens=raw.input_tokens,
            output_tokens=raw.output_tokens,
            cached_tokens=raw.cached_tokens,
            latency_ms=latency_ms,
            cost_usd=cost,
            model=model,
            provider="anthropic" if model.startswith("claude-") else "deepseek",
        )

        logger.info(
            "llm.call",
            task_name=task.name,
            task_class=task.task_class,
            model=model,
            provider=usage.provider,
            input_tokens=raw.input_tokens,
            output_tokens=raw.output_tokens,
            cached_tokens=raw.cached_tokens,
            latency_ms=latency_ms,
            cost_usd=round(cost, 6),
        )

        parsed: Any = None
        if response_model is not None:
            content = raw.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            try:
                parsed = response_model.model_validate(json.loads(content))
            except (json.JSONDecodeError, pydantic.ValidationError) as exc:
                logger.warning(
                    "llm.parse_failed",
                    task_name=task.name,
                    content_preview=content[:200],
                    exc_info=exc,
                )
                raise LLMParseError(f"Failed to parse LLM response for task {task.name!r}") from exc

        return LLMResult(content=raw.content, parsed=parsed, usage=usage)


class BudgetGuard:
    """Wraps an LLMClient to enforce per-user daily and global hourly spend limits."""

    def __init__(
        self,
        inner: LLMClient,
        per_user_daily_usd: float,
        global_hourly_usd: float,
    ) -> None:
        self._inner = inner
        self._per_user_daily_usd = per_user_daily_usd
        self._global_hourly_usd = global_hourly_usd
        self._user_day_spend: dict[tuple[int, str], float] = defaultdict(float)
        self._hour_spend: dict[str, float] = defaultdict(float)
        self._lock = asyncio.Lock()

    def _day_key(self) -> str:
        return time.strftime("%Y-%m-%d", time.gmtime())

    def _hour_key(self) -> str:
        return time.strftime("%Y-%m-%dT%H", time.gmtime())

    async def complete(
        self,
        task: TaskSpec,
        messages: list[Message],
        *,
        response_model: type[Any] | None = None,
        user_id: int | None = None,
    ) -> LLMResult[Any]:
        async with self._lock:
            hour_key = self._hour_key()
            if self._hour_spend[hour_key] >= self._global_hourly_usd:
                raise BudgetExceeded("Global hourly budget exceeded")

            if user_id is not None:
                day_key = self._day_key()
                user_key = (user_id, day_key)
                if self._user_day_spend[user_key] >= self._per_user_daily_usd:
                    raise BudgetExceeded(f"Daily budget exceeded for user {user_id}")

        result = await self._inner.complete(task, messages, response_model=response_model)

        async with self._lock:
            cost = result.usage.cost_usd
            self._hour_spend[self._hour_key()] += cost
            if user_id is not None:
                self._user_day_spend[(user_id, self._day_key())] += cost

        return result
