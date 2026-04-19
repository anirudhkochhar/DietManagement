# Diet Management — Claude Code Project Guide

A Telegram bot for diet management: meal logging, calorie/macro tracking, and nutrition guidance. The bot is LLM-powered but the provider is pluggable — DeepSeek by default for cost, swappable to Claude Sonnet/Haiku or any OpenAI-compatible provider per task.

## Tech stack (locked)

- **Language:** Python 3.11+
- **Bot framework:** `python-telegram-bot` v21+ (async)
- **LLM providers:** DeepSeek (default), Anthropic Claude, any OpenAI-compatible API — behind a single `LLMClient` interface
- **Data models:** Pydantic v2
- **Config:** `pydantic-settings`, `.env` files. Never commit secrets.
- **Storage:** SQLAlchemy async — SQLite in dev, Postgres-ready for prod
- **Logging:** `structlog` (JSON in prod, console in dev)
- **Testing:** `pytest` + `pytest-asyncio` + `respx`/`httpx-mock`
- **Lint/format:** `ruff` (both)
- **Type checking:** `mypy --strict`
- **Deps:** `uv` with `pyproject.toml` + `uv.lock`

Target repo layout:

```
bot/           # Telegram handlers, conversation flows (thin)
llm/           # Provider-agnostic LLM interface + router + providers/
diet/          # Domain logic: meals, nutrition, planning, suggestions
storage/       # DB models, migrations, repositories
config/        # Settings, secrets loading
tests/         # Mirrors source tree
```

## Non-negotiable standards

Full detail in `.claude/skills/python-standards/SKILL.md`. The rules that most often get missed: types strict (`mypy --strict`), async everywhere on request paths, Pydantic at every boundary, no LLM SDK imports outside `llm/`, no secrets in code, `structlog` only (no `print`).

## LLM cost discipline

Cost control is architectural, not per-call. All LLM calls route through `llm/router.py`, which picks a model based on a declared task class (`trivial` / `standard` / `reasoning`). Model-per-class is configured via env, so swapping DeepSeek ↔ Claude ↔ any OpenAI-compatible provider is not a code change. Every call is logged with tokens and cost; per-user daily spend is bounded by middleware. Tests always mock LLM calls. See `.claude/skills/llm-router/SKILL.md` for the contract.

## Workflow for every change

1. **Plan** — for anything non-trivial, invoke the `architect` agent first.
2. **Implement** — invoke `bot-developer`. Consult skills as needed.
3. **Test** — `test-engineer` adds/updates tests. Mock LLM and Telegram.
4. **Review** — `code-reviewer` runs on the diff. Fix every blocking item.
5. **Commit** — small, focused commits. Conventional Commits style.

The pre-commit loop is spelled out in `.claude/skills/commit-review/SKILL.md`.

## How to trigger

Orchestrate inline; spawn subagents sparingly. Sonnet 4.6 is strong enough to plan, implement, and test in a single session — extra subagents cost tokens on context reloads without improving output.

- **Kickoff prompt.** Start a Claude Code session in this directory and give one high-level instruction referencing `CLAUDE.md`, e.g. *"Read `CLAUDE.md` and build the initial scaffolding plus the `llm/` layer. Small commits."* Main Claude takes it from there.
- **Role-spec files are checklists, not subagent boundaries.** `architect.md`, `bot-developer.md`, and `test-engineer.md` describe modes main Claude shifts into — it reads them inline when it enters that phase. Do not spawn a subagent for each.
- **Spawn `code-reviewer` as a subagent before every commit.** An independent context reviews better than the one that wrote the code. This is the only agent that meaningfully benefits from isolation in the normal dev loop.
- **Spawn other agents only when there's real parallel or isolation value.** Examples: two independent `llm/providers/*.py` adapters built concurrently by two `bot-developer` subagents; a feature whose diff would crowd the main context window; a focused test pass by `test-engineer` while main Claude moves on.
- **Do not wire all four agents into a default pipeline.** A four-stage chain on every change is orchestration theater — it burns tokens without improving the work.

## Why one reviewer agent, not a separate cost-optimizer

Sonnet 4.6 (building this repo) is strong enough to reason about cost during review; splitting that into a second agent adds orchestration overhead without improving outcomes. Instead:

- Cost awareness lives in the **runtime** — router, task classes, per-call logging, budget middleware.
- The `code-reviewer` agent has an explicit checklist item for cost impact.

The real savings are in the bot's runtime token spend, not the dev loop.

## Agents (in `.claude/agents/`)

- `architect` — plans before coding, flags LLM cost implications.
- `bot-developer` — implements features against the standards.
- `test-engineer` — tests with mocked LLM/Telegram, real in-memory SQLite.
- `code-reviewer` — gatekeeper before every commit.

## Skills (in `.claude/skills/`)

- `python-standards` — the coding bar.
- `llm-router` — the LLM abstraction contract.
- `telegram-bot` — handler, conversation, error patterns.
- `commit-review` — the pre-commit loop.

## For the agent building this repo

You are Sonnet 4.6. You are capable of doing this end-to-end. Before writing a single file:

1. Read this file, then `.claude/skills/python-standards/SKILL.md`, then the skill relevant to the layer you're building.
2. Set up `pyproject.toml` with `uv`, ruff + mypy configs, and the initial package layout before writing any logic.
3. Build the `llm/` layer (interface, router, fake client, one real provider adapter) before the bot layer depends on it.
4. Land work in small commits, each passing the pre-commit loop.
