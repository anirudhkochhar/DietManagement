from enum import IntEnum

import structlog
from telegram import Message as TgMessage
from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.deps import profile_service
from bot.formatters import format_profile
from bot.keyboards import goal_keyboard, skip_keyboard
from diet.models import ProfileUpdate, UserGoal

logger = structlog.get_logger()


class SetupState(IntEnum):
    ASK_GOAL = 0
    ASK_HEIGHT = 1
    ASK_WEIGHT = 2
    ASK_AGE = 3
    ASK_RESTRICTIONS = 4


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_user and update.message
    user_id = update.effective_user.id
    username = update.effective_user.username
    logger.info("handler.start", user_id=user_id)

    async with profile_service(context) as svc:
        await svc.get_or_create(user_id, username)

    await update.message.reply_text(
        "👋 Welcome to Diet Bot!\n\n"
        "I help you track meals via text, photos, barcodes, or voice.\n\n"
        "Use /setup to set your goals, or /log to start logging right away.\n"
        "Type /help for all commands."
    )


async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_user and update.message
    user_id = update.effective_user.id
    logger.info("handler.profile.start", user_id=user_id)

    async with profile_service(context) as svc:
        user_profile = await svc.get_or_create(user_id)
    await update.message.reply_text(format_profile(user_profile))
    logger.info("handler.profile.done", user_id=user_id)


# --- Onboarding conversation ---


async def setup_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.message
    await update.message.reply_text(
        "Let's set up your profile! What's your goal?",
        reply_markup=goal_keyboard(),
    )
    return SetupState.ASK_GOAL


async def got_goal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.callback_query
    query = update.callback_query
    await query.answer()
    goal_str = query.data.split(":")[1] if query.data else "maintenance"
    if context.user_data is not None:
        context.user_data["goal"] = goal_str
    goal_label = goal_str.replace("_", " ").title()
    await query.edit_message_text(
        f"Goal set to: {goal_label}\n\nWhat's your height in cm? (e.g. 175)",
        reply_markup=skip_keyboard(),
    )
    return SetupState.ASK_HEIGHT


async def got_height(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.message
    text = (update.message.text or "").strip()
    if text.lower() != "skip":
        try:
            height = float(text)
            if context.user_data is not None:
                context.user_data["height_cm"] = height
        except ValueError:
            await update.message.reply_text("Please enter a number (e.g. 175) or Skip.")
            return SetupState.ASK_HEIGHT
    await update.message.reply_text(
        "What's your weight in kg? (e.g. 70)", reply_markup=skip_keyboard()
    )
    return SetupState.ASK_WEIGHT


async def got_weight(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.message
    text = (update.message.text or "").strip()
    if text.lower() != "skip":
        try:
            weight = float(text)
            if context.user_data is not None:
                context.user_data["weight_kg"] = weight
        except ValueError:
            await update.message.reply_text("Please enter a number (e.g. 70) or Skip.")
            return SetupState.ASK_WEIGHT
    await update.message.reply_text("What's your age?", reply_markup=skip_keyboard())
    return SetupState.ASK_AGE


async def got_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.message
    text = (update.message.text or "").strip()
    if text.lower() != "skip":
        try:
            age = int(text)
            if context.user_data is not None:
                context.user_data["age"] = age
        except ValueError:
            await update.message.reply_text("Please enter a whole number (e.g. 28) or Skip.")
            return SetupState.ASK_AGE
    await update.message.reply_text(
        "Any dietary restrictions? (e.g. vegetarian, gluten-free, nut allergy)\n"
        "Type them separated by commas, or Skip.",
        reply_markup=skip_keyboard(),
    )
    return SetupState.ASK_RESTRICTIONS


async def got_restrictions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_user and update.message
    user_id = update.effective_user.id
    text = (update.message.text or "").strip()
    restrictions: list[str] = []
    if text.lower() not in ("skip", "none", ""):
        restrictions = [r.strip() for r in text.split(",") if r.strip()]

    data = context.user_data or {}
    goal_val = data.get("goal", "maintenance")
    try:
        goal = UserGoal(goal_val)
    except ValueError:
        goal = UserGoal.MAINTENANCE

    update_data = ProfileUpdate(
        goal=goal,
        height_cm=data.get("height_cm"),
        weight_kg=data.get("weight_kg"),
        age=data.get("age"),
        dietary_restrictions=restrictions if restrictions else None,
    )

    async with profile_service(context) as svc:
        saved_profile = await svc.update(user_id, update_data)

    if context.user_data is not None:
        context.user_data.clear()

    await update.message.reply_text(
        "✅ Profile saved!\n\n"
        + format_profile(saved_profile)
        + "\n\nUse /log to start logging meals!"
    )
    logger.info("handler.setup.done", user_id=user_id)
    return ConversationHandler.END


async def cancel_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message:
        await update.message.reply_text("Setup cancelled. Use /setup to try again.")
    if context.user_data is not None:
        context.user_data.clear()
    return ConversationHandler.END


async def skip_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.callback_query
    await update.callback_query.answer()
    msg = update.callback_query.message
    if isinstance(msg, TgMessage):
        await msg.edit_reply_markup(reply_markup=None)
    return ConversationHandler.END


def build_setup_conversation() -> ConversationHandler:  # type: ignore[type-arg]
    # NOTE: conversation state is in-memory only (bot_data) for this version.
    # For production: configure python-telegram-bot Persistence to persist state across restarts.
    return ConversationHandler(
        entry_points=[CommandHandler("setup", setup_start)],
        states={
            SetupState.ASK_GOAL: [CallbackQueryHandler(got_goal, pattern="^goal:")],
            SetupState.ASK_HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_height)],
            SetupState.ASK_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_weight)],
            SetupState.ASK_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_age)],
            SetupState.ASK_RESTRICTIONS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, got_restrictions)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_setup)],
        conversation_timeout=600,
    )
