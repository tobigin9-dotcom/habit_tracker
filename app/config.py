from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Load service settings from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://habits_user:password@localhost:5432/habits"
    jwt_secret_key: str = "development-only-change-this-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    bot_token: str = ""
    bot_api_token: str = "development-only-internal-token"
    api_base_url: str = "http://localhost:8000"
    default_reminder_time: str = "20:00"
    habit_target_completions: int = 21
    timezone: str = "Europe/Amsterdam"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
