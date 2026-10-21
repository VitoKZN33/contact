from functools import lru_cache

from app.ai.deepseek import DeepSeekProvider
from app.ai.mock import MockProvider
from app.ai.provider import LLMProvider
from app.core.config import get_settings


@lru_cache
def get_llm_provider() -> LLMProvider:
    """Зависимость FastAPI. В тестах подменяется через app.dependency_overrides."""
    settings = get_settings()
    if settings.ai_provider == "mock":
        return MockProvider()
    return DeepSeekProvider(
        api_key=settings.deepseek_api_key.get_secret_value(),
        base_url=settings.deepseek_base_url,
        timeout_seconds=settings.ai_timeout_seconds,
        max_retries=settings.ai_max_retries,
    )
