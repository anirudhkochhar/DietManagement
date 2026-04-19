import structlog
from telegram import Update
from telegram.ext import ContextTypes

from llm.router import BudgetExceeded

logger = structlog.get_logger()

_USER_MESSAGES: dict[type[Exception], str] = {
    BudgetExceeded: "You've reached your daily usage limit. Try again tomorrow!",
}

_GENERIC = "Sorry, something went wrong. Please try again in a moment."


async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    exc = context.error
    user_id = None
    if isinstance(update, Update) and update.effective_user:
        user_id = update.effective_user.id

    logger.exception(
        "bot.error",
        user_id=user_id,
        update_id=update.update_id if isinstance(update, Update) else None,
        exc_info=exc,
    )

    if not isinstance(update, Update) or not update.effective_message:
        return

    reply = _USER_MESSAGES.get(type(exc), _GENERIC) if exc else _GENERIC
    await update.effective_message.reply_text(reply)
