import pytest

from llm.interface import Message, TaskClass, TaskSpec
from llm.pricing import calculate_cost, get_price
from llm.router import BudgetExceeded, BudgetGuard
from tests.fakes.llm import FakeLLMClient


def test_price_lookup_known_model() -> None:
    price = get_price("deepseek-chat")
    assert price.input == 0.14
    assert price.output == 0.28


def test_calculate_cost_zero_tokens() -> None:
    cost = calculate_cost("deepseek-chat", 0, 0)
    assert cost == 0.0


def test_calculate_cost_with_cache() -> None:
    cost_no_cache = calculate_cost("claude-sonnet-4-6", 1_000_000, 0, cached_tokens=0)
    cost_cached = calculate_cost("claude-sonnet-4-6", 1_000_000, 0, cached_tokens=1_000_000)
    assert cost_cached < cost_no_cache


@pytest.mark.asyncio
async def test_budget_guard_allows_call_under_limit() -> None:
    fake = FakeLLMClient()
    fake.script("test_task", content="ok")
    guard = BudgetGuard(inner=fake, per_user_daily_usd=1.0, global_hourly_usd=10.0)

    task = TaskSpec(name="test_task", task_class=TaskClass.TRIVIAL)
    result = await guard.complete(task, [Message(role="user", content="hello")], user_id=42)
    assert result.content == "ok"


@pytest.mark.asyncio
async def test_budget_guard_blocks_user_over_daily_limit() -> None:
    fake = FakeLLMClient()
    guard = BudgetGuard(inner=fake, per_user_daily_usd=0.0, global_hourly_usd=10.0)

    task = TaskSpec(name="blocked_task", task_class=TaskClass.TRIVIAL)
    with pytest.raises(BudgetExceeded):
        await guard.complete(task, [Message(role="user", content="hi")], user_id=1)


@pytest.mark.asyncio
async def test_budget_guard_blocks_global_hourly() -> None:
    fake = FakeLLMClient()
    guard = BudgetGuard(inner=fake, per_user_daily_usd=100.0, global_hourly_usd=0.0)

    task = TaskSpec(name="blocked_global", task_class=TaskClass.TRIVIAL)
    with pytest.raises(BudgetExceeded):
        await guard.complete(task, [Message(role="user", content="hi")])
