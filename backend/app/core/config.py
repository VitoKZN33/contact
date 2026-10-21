from functools import lru_cache
from typing import Any, Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Пустая строка в .env означает «взять значение по умолчанию»
_BLANK_MEANS_DEFAULT = (
    "deepseek_base_url",
    "deepseek_model_dialog",
    "deepseek_model_analysis",
    "ai_pricing_json",
    "ai_provider",
)


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

    # --- AI ---
    ai_provider: Literal["deepseek", "mock"] = "deepseek"
    deepseek_api_key: SecretStr = SecretStr("")
    deepseek_base_url: str = "https://api.deepseek.com"
    # Идентификаторы сверены с api-docs.deepseek.com (октябрь 2026)
    deepseek_model_dialog: str = "deepseek-flash"
    deepseek_model_analysis: str = "deepseek-v4-pro"
    ai_timeout_seconds: float = Field(default=40, gt=0)
    ai_max_retries: int = Field(default=2, ge=0, le=5)
    ai_dialog_max_tokens: int = Field(default=300, ge=50, le=4000)
    ai_dialog_temperature: float = Field(default=0.9, ge=0, le=2)
    ai_analysis_max_tokens: int = Field(default=2500, ge=500, le=8000)
    ai_analysis_temperature: float = Field(default=0.3, ge=0, le=2)
    # Цены, USD за 1M токенов; пусто — значения из app/ai/pricing.py
    ai_pricing_json: str = ""

    # --- Тренировки ---
    training_ttl_hours: int = Field(default=24, ge=1)
    context_keep_messages: int = Field(default=16, ge=4)
    context_summarize_after: int = Field(default=28, ge=8)

    # --- Лимиты ---
    limit_trainings_per_day: int = Field(default=10, ge=0)
    limit_analyses_per_day: int = Field(default=20, ge=0)
    limit_messages_per_minute: int = Field(default=20, ge=0)
    max_user_turns: int = Field(default=30, ge=1)
    max_message_chars: int = Field(default=1000, ge=1)
    max_custom_situation_chars: int = Field(default=1500, ge=0)

    @model_validator(mode="before")
    @classmethod
    def _blank_to_default(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return {
                k: v
                for k, v in data.items()
                if not (k.lower() in _BLANK_MEANS_DEFAULT and isinstance(v, str) and not v.strip())
            }
        return data

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
