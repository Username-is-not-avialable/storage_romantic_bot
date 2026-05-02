from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    _ROOT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"

    model_config = SettingsConfigDict(
        # Resolve against repo root, not current working directory.
        env_file=_ROOT_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: str = Field(default="dev", validation_alias="APP_ENV")
    auth_session_ttl_hours: int = Field(default=24, validation_alias="AUTH_SESSION_TTL_HOURS")
    auth_code_ttl_minutes: int = Field(default=15, validation_alias="AUTH_CODE_TTL_MINUTES")
    vk_bot_secret: str = Field(default="", validation_alias="VK_BOT_SECRET")
    vk_link_ttl_minutes: int = Field(default=15, validation_alias="VK_LINK_TTL_MINUTES")
    gmail_token_file: str = Field(default="token.json", validation_alias="GMAIL_TOKEN_FILE")
    gmail_default_sender: str = Field(default="me", validation_alias="GMAIL_DEFAULT_SENDER")

    # Database
    db_host: str | None = Field(default=None, validation_alias="DB_HOST")
    db_port: int = Field(default=5432, validation_alias="DB_PORT")
    db_user: str | None = Field(default=None, validation_alias="DB_USER")
    db_password: str | None = Field(default=None, validation_alias="DB_PASSWORD")
    db_name: str | None = Field(default=None, validation_alias="DB_NAME")

    @model_validator(mode="after")
    def _validate_required_env(self) -> "Settings":
        missing: list[str] = []
        if not self.db_host:
            missing.append("DB_HOST")
        if not self.db_user:
            missing.append("DB_USER")
        if not self.db_password:
            missing.append("DB_PASSWORD")
        if not self.db_name:
            missing.append("DB_NAME")

        if missing:
            raise ValueError(
                "Database configuration is missing. "
                "Provide DB_HOST, DB_USER, DB_PASSWORD, DB_NAME. "
                f"Missing: {', '.join(missing)}"
            )
        return self

    def build_sync_database_url(self) -> str:
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    def build_async_database_url(self) -> str:
        sync_url = self.build_sync_database_url()
        if sync_url.startswith("postgresql://"):
            return sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return sync_url

    def safe_dump(self) -> dict[str, Any]:
        """
        For debugging/telemetry without secrets.
        """
        return {
            "app_env": self.app_env,
            "auth_session_ttl_hours": self.auth_session_ttl_hours,
            "auth_code_ttl_minutes": self.auth_code_ttl_minutes,
            "vk_link_ttl_minutes": self.vk_link_ttl_minutes,
            "vk_bot_secret_configured": bool(self.vk_bot_secret),
            "db_host": self.db_host,
            "db_port": self.db_port,
            "db_user": self.db_user,
            "db_name": self.db_name,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()

