from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    telegram_bot_token: SecretStr
    telegram_webapp_url: str = ""
    log_level: str = "INFO"

    @property
    def webapp_url(self) -> str | None:
        """Telegram открывает Mini App только по HTTPS."""
        url = self.telegram_webapp_url.strip()
        return url if url.startswith("https://") else None


@lru_cache
def get_settings() -> BotSettings:
    return BotSettings()  # type: ignore[call-arg]
