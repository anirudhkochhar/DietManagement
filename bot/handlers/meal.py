import io

import structlog
from telegram import Update
from telegram.ext import ContextTypes

from bot.deps import meal_service
from bot.formatters import format_meal_log

logger = structlog.get_logger()

_MAX_TEXT_LEN = 2000


async def log_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_user and update.message
    user_id = update.effective_user.id
    logger.info("handler.log_text.start", user_id=user_id)

    args = context.args or []
    text = " ".join(args).strip()
    if not text and update.message.text:
        text = update.message.text.removeprefix("/log").strip()
    if not text:
        await update.message.reply_text(
            "Usage: /log <food description>\nExample: /log 2 eggs and toast"
        )
        return

    text = text[:_MAX_TEXT_LEN]
    async with meal_service(context) as svc:
        logged_meal = await svc.log_from_text(user_id, text)
    await update.message.reply_text(format_meal_log(logged_meal))
    logger.info("handler.log_text.done", user_id=user_id)


async def handle_free_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_user and update.message and update.message.text
    user_id = update.effective_user.id
    text = update.message.text.strip()[:_MAX_TEXT_LEN]

    if len(text) < 5 or text.endswith("?"):
        await update.message.reply_text(
            "Send /log <food> to log a meal, or /help for all commands."
        )
        return

    logger.info("handler.free_text.start", user_id=user_id)
    async with meal_service(context) as svc:
        logged_meal = await svc.log_from_text(user_id, text)
    await update.message.reply_text(format_meal_log(logged_meal))
    logger.info("handler.free_text.done", user_id=user_id)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_user and update.message
    user_id = update.effective_user.id
    logger.info("handler.photo.start", user_id=user_id)

    photos = update.message.photo
    if not photos:
        return

    await update.message.reply_text("🔍 Analyzing image...")

    photo = photos[-1]
    tg_file = await context.bot.get_file(photo.file_id)
    buf = io.BytesIO()
    await tg_file.download_to_memory(buf)
    image_bytes = buf.getvalue()

    async with meal_service(context) as svc:
        logged_meal = await svc.log_from_image(user_id, image_bytes, "image/jpeg")

    if not logged_meal.entries:
        await update.message.reply_text(
            "I couldn't identify any food or barcode in that image.\n"
            "Try a clearer photo or use /log to type your meal."
        )
        return

    await update.message.reply_text(format_meal_log(logged_meal))
    logger.info("handler.photo.done", user_id=user_id, source=logged_meal.source)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_user and update.message
    user_id = update.effective_user.id
    logger.info("handler.voice.start", user_id=user_id)

    voice = update.message.voice
    if not voice:
        return

    await update.message.reply_text("🎤 Transcribing your voice message...")

    tg_file = await context.bot.get_file(voice.file_id)
    buf = io.BytesIO()
    await tg_file.download_to_memory(buf)
    audio_bytes = buf.getvalue()

    async with meal_service(context) as svc:
        logged_meal = await svc.log_from_audio(user_id, audio_bytes)

    if logged_meal is None:
        await update.message.reply_text(
            "I couldn't transcribe your voice message. "
            "Please try again or use /log to type your meal."
        )
        return

    await update.message.reply_text(format_meal_log(logged_meal))
    logger.info("handler.voice.done", user_id=user_id)
