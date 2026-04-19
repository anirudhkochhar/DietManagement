from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str = ""

    # LLM API keys
    anthropic_api_key: str = ""
    deepseek_api_key: str = ""
    openai_api_key: str = ""  # Whisper audio transcription

    # Model selection per task class
    llm_model_trivial: str = "deepseek-chat"
    llm_model_standard: str = "deepseek-chat"
    llm_model_reasoning: str = "claude-sonnet-4-6"
    llm_model_vision: str = "claude-sonnet-4-6"  # multimodal capable

    # Budget
    budget_per_user_daily_usd: float = 0.10
    budget_global_hourly_usd: float = 1.00

    # Database
    database_url: str = "sqlite+aiosqlite:///./diet.db"

    # Environment
    env: str = "dev"

    @property
    def is_production(self) -> bool:
        return self.env == "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()
