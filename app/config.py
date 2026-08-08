"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Financial Assistant"
    ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    API_V1_STR: str = "/api/v1"

    # Database
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "financial_assistant"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/financial_assistant"

    # Gemini API
    GEMINI_API_KEY: str = "mock-key"
    GEMINI_MODEL: str = "gemini-3.6-flash"
    EMBEDDING_MODEL: str = "gemini-embedding-2"

    # Telegram API
    TELEGRAM_BOT_TOKEN: str = "mock-token"
    TELEGRAM_WEBHOOK_URL: str = "http://localhost:8000/webhook"
    TELEGRAM_WEBHOOK_SECRET_TOKEN: str = ""

    # News API
    NEWS_API_KEY: str = ""

    # Scheduler
    ENABLE_SCHEDULER: bool = True
    DEFAULT_BRIEFING_TIME: str = "08:00"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
