---
name: python-standards
description: The coding bar for the Diet Management repo. Read before writing or reviewing Python. Covers typing, async, Pydantic, logging, testing, tooling, and what is banned.
---

# Python standards — Diet Management

These apply to every file in the repo, including tests and scripts.

## Version & tooling

- **Python 3.11+**. Use `match`, `Self`, `ExceptionGroup`, `asyncio.TaskGroup` freely.
- **Deps:** `uv` with `pyproject.toml` + committed `uv.lock`.
- **Lint + format:** `ruff`. Line length 100. Import sorting on.
- **Type check:** `mypy --strict`. No `# type: ignore` without an adjacent `# reason: ...` comment.
- **Tests:** `pytest` + `pytest-asyncio`.

All four (`ruff format`, `ruff check`, `mypy --strict`, `pytest -x`) must pass before commit.

## Typing

- Every function signature is fully typed — parameters and return.
- Prefer `X | None` over `Optional[X]`. Built-in generics (`list[int]`, `dict[str, int]`).
- `TypedDict` or Pydantic models for structured dicts. Never `dict[str, Any]` in a public API.
- `Protocol` for duck-typed interfaces (e.g., `LLMClient`, `Provider`).
- `Final` for module-level constants.
- `Literal` for enumerated string choices when an `Enum` is overkill.

## Async

- All I/O is async: Telegram, LLM HTTP, DB (SQLAlchemy async).
- `asyncio.run` only at the top-level entrypoint, never inside library code.
- No `time.sleep`, no sync `requests`, no sync file I/O inside `async def` on request paths.
- Use `asyncio.gather` for independent concurrent work, `asyncio.TaskGroup` for structured concurrency.

## Data models

- Pydantic v2 everywhere data crosses a boundary (network, DB, LLM, Telegram).
- Domain models (what business logic uses) are distinct from wire models (what goes to/from Telegram and LLMs). Translate at the boundary.
- Value objects: `model_config = ConfigDict(frozen=True)`.
- Validators live on the model, not in handlers.

## Configuration

- `pydantic-settings` reads env + `.env`.
- One `Settings` class exported via `@lru_cache`d `get_settings()`.
- Secrets never logged, never committed. `.env` in `.gitignore`. `.env.example` committed with placeholders.

## Logging

- `structlog`. JSON renderer in prod, console in dev. No `print`.
- Every LLM call logs: `task_name`, `task_class`, `model`, `provider`, `input_tokens`, `output_tokens`, `cached_tokens`, `latency_ms`, `cost_usd`.
- Every Telegram handler logs a start and an end event.
- Log user IDs freely; do not log message bodies or PII by default.

## Errors

- Raise specific exceptions. No bare `except`.
- Wrap external calls in `try`/`except` only when you handle the failure. Don't swallow.
- Telegram handlers have one global error handler that logs and replies with a friendly generic message; domain code raises typed exceptions.

## Testing

- `tests/` mirrors the source tree.
- Fixtures in nearest-useful `conftest.py`.
- `FakeLLMClient` for LLM mocking; real in-memory SQLite for storage.
- `pytest-socket` disables real sockets by default.
- Name tests after behavior: `test_router_picks_cheapest_for_trivial`, not `test_router_1`.

## File and function size

- Modules roughly ≤ 300 lines. If it's growing past that, the module is doing too much.
- Functions roughly ≤ 50 lines. If it's growing past that, extract.

## Comments

- Default to none. Good names carry the meaning.
- Write a comment only when the *why* is non-obvious: a workaround, a constraint, an invariant that isn't visible from the code.
- No docstrings that restate the signature.
- No references to tickets, callers, or "added for X" — that belongs in commits.

## Banned

- `print`.
- `eval`, `exec`, `pickle.loads` on untrusted input.
- `from X import *`.
- Circular imports — refactor.
- Global mutable state outside the settings singleton.
- Direct LLM provider SDK imports outside `llm/`.
- `requirements.txt` — use `pyproject.toml`.
- f-string SQL. Parameterize.
