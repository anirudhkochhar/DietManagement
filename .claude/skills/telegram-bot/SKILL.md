---
name: telegram-bot
description: Patterns for Telegram bot handlers, conversations, state, error handling, and rate limiting. Read before adding or modifying bot handlers in the Diet Management repo.
---

# Telegram bot patterns

Library: `python-telegram-bot` v21+ (async). The bot layer is thin — it parses input, delegates to domain, formats a reply. No business logic in handlers.

## Handler shape

```python
async def log_meal(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    cmd = MealInput.model_validate({
        "user_id": update.effective_user.id,
        "text": update.message.text,
    })
    result = await meal_service.log(cmd)
    await update.message.reply_text(format_meal_reply(result))
```

Three steps, always:

1. **Parse** — extract and validate input into a Pydantic model. Invalid input raises, global error handler catches.
2. **Delegate** — call a function in `diet/` or `llm/`. The handler does not decide *how*.
3. **Reply** — format and send. Use a dedicated formatter function; keep strings out of handlers.

## Conversations

- `ConversationHandler` for multi-step flows (onboarding, meal correction, weekly planning).
- One state enum per conversation, defined once.
- Persist conversation state to the DB, not just in-memory — the bot will restart.
- Timeouts configured; stale conversations end cleanly.

## Error handling

- One global error handler registered via `application.add_error_handler`.
- It logs the exception with `structlog` (include `update.update_id` and `effective_user.id`) and replies with a generic friendly message.
- Domain code raises typed exceptions (e.g., `MealParseError`, `BudgetExceeded`, `UnknownFood`).
- Each typed exception maps to a specific user-facing message — maintain a single mapping table.

## Rate limiting and cost control

- Use `AIORateLimiter` from the library for API-level rate limits.
- Per-user LLM spend ceiling is enforced inside the domain layer via `BudgetGuard` (see `llm-router` skill). Rate limits alone do not bound cost — a user could hit you with cheap spammy messages that each trigger an expensive LLM call.

## State and storage

- No global dicts for user state. Everything persists via SQLAlchemy-backed repositories.
- Load user context once at the start of a handler; pass it to domain; write back if it changed.
- `bot_data` and `user_data` are for transient per-run state only — never secrets, never anything that must survive a restart.

## Formatting replies

- Keep replies short. Long outputs paginate or send as a file.
- Telegram MarkdownV2 needs escaping — use a `escape_markdown_v2()` helper, never hand-format.
- Never dump raw LLM output directly to the user. Validate, truncate, and sanitize — LLMs occasionally emit prompt-injection-style content.

## What NOT to do in handlers

- Call LLM provider SDKs directly. Go through `LLMClient`.
- Access the DB directly. Go through a repository.
- Block the event loop with sync calls.
- Store secrets in `bot_data` or `user_data`.
- Put branching business logic in the handler — push it into `diet/`.
