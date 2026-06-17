from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./data/bot.db"


class Settings(BaseSettings):
    bot_token: str = Field(alias="BOT_TOKEN")
    database_url: str = Field(default=DEFAULT_DATABASE_URL, alias="DATABASE_URL")
    default_timezone: str = Field(default="Europe/Moscow", alias="DEFAULT_TIMEZONE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    uptime_enabled: bool = Field(default=True, alias="UPTIME_ENABLED")
    uptime_http_enabled: bool = Field(default=False, alias="UPTIME_HTTP_ENABLED")
    uptime_host: str = Field(default="0.0.0.0", alias="UPTIME_HOST")
    uptime_port: int = Field(default=8080, ge=1, le=65535, alias="UPTIME_PORT")
    uptime_path: str = Field(default="/healthz", alias="UPTIME_PATH")
    uptime_push_url: str = Field(default="", alias="UPTIME_PUSH_URL")
    uptime_push_interval_seconds: int = Field(
        default=60,
        ge=10,
        le=3600,
        alias="UPTIME_PUSH_INTERVAL_SECONDS",
    )

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

    @field_validator("uptime_path")
    @classmethod
    def validate_uptime_path(cls, value: str) -> str:
        value = value.strip()
        if not value.startswith("/"):
            value = f"/{value}"
        return value

    @field_validator("uptime_push_url")
    @classmethod
    def validate_uptime_push_url(cls, value: str) -> str:
        return value.strip()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
