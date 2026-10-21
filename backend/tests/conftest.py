import os

# Тестовые значения задаются до импорта приложения. DATABASE_URL из окружения
# контейнера (реальная PostgreSQL в docker compose) имеет приоритет.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://contact:contact@localhost:5432/contact")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TEST")
os.environ.setdefault("FRONTEND_URL", "https://app.test")

import httpx  # noqa: E402
import pytest  # noqa: E402

from app.main import create_app  # noqa: E402


@pytest.fixture
async def client():
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
