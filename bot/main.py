import structlog
import structlog.dev
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from bot.handlers import error, meal, nutrition, profile
from config.settings import Settings, get_settings
from llm.interface import Provider, TaskClass, TranscriptionClient
from llm.providers import AnthropicProvider, DeepSeekProvider, WhisperTranscriber
from llm.router import BudgetGuard, Router
from storage.database import build_engine, create_tables

logger = structlog.get_logger()


def _configure_logging(is_prod: bool) -> None:
    renderer = structlog.processors.JSONRenderer() if is_prod else structlog.dev.ConsoleRenderer()
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ]
    )


def _build_llm(settings: Settings) -> tuple[BudgetGuard, TranscriptionClient | None]:
    providers: dict[str, Provider] = {}
    if settings.anthropic_api_key:
        providers["anthropic"] = AnthropicProvider(settings.anthropic_api_key)
    if settings.deepseek_api_key:
        providers["deepseek"] = DeepSeekProvider(settings.deepseek_api_key)

    model_for_class = {
        TaskClass.TRIVIAL: settings.llm_model_trivial,
        TaskClass.STANDARD: settings.llm_model_standard,
        TaskClass.REASONING: settings.llm_model_reasoning,
    }

    router = Router(
        providers=providers,
        model_for_class=model_for_class,
        vision_model=settings.llm_model_vision,
    )
    guard = BudgetGuard(
        inner=router,
        per_user_daily_usd=settings.budget_per_user_daily_usd,
        global_hourly_usd=settings.budget_global_hourly_usd,
    )

    transcriber: TranscriptionClient | None = None
    if settings.openai_api_key:
        transcriber = WhisperTranscriber(settings.openai_api_key)

    return guard, transcriber


async def _post_init(application: Application) -> None:  # type: ignore[type-arg]
    settings = get_settings()
    await create_tables(settings.database_url)

    session_factory, _ = build_engine(settings.database_url)
    llm, transcriber = _build_llm(settings)

    application.bot_data["session_factory"] = session_factory
    application.bot_data["llm"] = llm
    application.bot_data["transcriber"] = transcriber

    logger.info("bot.initialized")


def build_application() -> Application:  # type: ignore[type-arg]
    settings = get_settings()
    _configure_logging(settings.is_production)

    app = Application.builder().token(settings.telegram_bot_token).post_init(_post_init).build()

    # Commands
    app.add_handler(CommandHandler("start", profile.start))
    app.add_handler(CommandHandler("help", nutrition.show_help))
    app.add_handler(CommandHandler("log", meal.log_text))
    app.add_handler(CommandHandler("summary", nutrition.daily_summary))
    app.add_handler(CommandHandler("weekly", nutrition.weekly_summary))
    app.add_handler(CommandHandler("profile", profile.show_profile))

    # Onboarding conversation
    app.add_handler(profile.build_setup_conversation())

    # Media
    app.add_handler(MessageHandler(filters.PHOTO, meal.handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, meal.handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, meal.handle_free_text))

    # Error handler
    app.add_error_handler(error.handle_error)

    return app


def main() -> None:
    app = build_application()
    logger.info("bot.starting")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
