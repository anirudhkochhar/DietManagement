from datetime import date

import structlog
from telegram import Update
from telegram.ext import ContextTypes

from bot.deps import meal_service, nutrition_service
from bot.formatters import HELP_TEXT, format_daily_summary, format_weekly_summary

logger = structlog.get_logger()


async def daily_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_user and update.message
    user_id = update.effective_user.id
    logger.info("handler.summary.start", user_id=user_id)

    async with meal_service(context) as svc:
        summary = await svc.get_daily_summary(user_id, date.today())
    await update.message.reply_text(format_daily_summary(summary))
    logger.info("handler.summary.done", user_id=user_id)


async def weekly_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_user and update.message
    user_id = update.effective_user.id
    logger.info("handler.weekly.start", user_id=user_id)

    async with nutrition_service(context) as svc:
        summaries = await svc.weekly_summary(user_id)
    await update.message.reply_text(format_weekly_summary(summaries))
    logger.info("handler.weekly.done", user_id=user_id)


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
    await update.message.reply_text(HELP_TEXT, parse_mode="MarkdownV2")
