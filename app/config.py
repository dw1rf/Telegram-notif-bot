from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./data/bot.db"


class Settings(BaseSettings):
    bot_token: str = Field(alias="BOT_TOKEN")
    database_url: str = Field(default=DEFAULT_DATABASE_URL, alias="DATABASE_URL")
    default_timezone: str = Field(default="Europe/Moscow", alias="DEFAULT_TIMEZONE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("bot_token")
    @classmethod
    def validate_bot_token(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("BOT_TOKEN is required")
        return value

    @field_validator("database_url", mode="before")
    @classmethod
    def use_default_database_url(cls, value: str | None) -> str:
        if value is None or not str(value).strip():
            return DEFAULT_DATABASE_URL
        return str(value)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
