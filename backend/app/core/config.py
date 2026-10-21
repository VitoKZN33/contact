from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфигурация backend. Значения приходят только из переменных окружения."""

    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    app_env: Literal["production", "development"] = "production"
    log_level: str = "INFO"

    database_url: str
    frontend_url: str = "http://localhost"

    secret_key: SecretStr
    bot_internal_secret: SecretStr = SecretStr("")
    initdata_max_age_seconds: int = Field(default=3600, ge=60)
    session_ttl_days: int = Field(default=7, ge=1)

    telegram_bot_token: SecretStr
    telegram_bot_username: str = ""

    deepseek_api_key: SecretStr = SecretStr("")
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model_dialog: str = ""
    deepseek_model_analysis: str = ""
    ai_timeout_seconds: float = Field(default=40, gt=0)
    ai_max_retries: int = Field(default=2, ge=0, le=5)

    limit_trainings_per_day: int = Field(default=10, ge=0)
    limit_analyses_per_day: int = Field(default=20, ge=0)
    limit_messages_per_minute: int = Field(default=20, ge=0)
    max_user_turns: int = Field(default=30, ge=1)
    max_message_chars: int = Field(default=1000, ge=1)
    max_custom_situation_chars: int = Field(default=1500, ge=0)

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
