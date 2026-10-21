"""Тесты работают с отдельной базой <имя>_test на том же сервере PostgreSQL.
Рабочая база не затрагивается: DATABASE_URL подменяется до импорта приложения."""

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _test_database_url(url: str) -> str:
    parts = urlsplit(url)
    name = parts.path.lstrip("/") or "contact"
    if not name.endswith("_test"):
        name = f"{name}_test"
    return urlunsplit(parts._replace(path=f"/{name}"))


_base_url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://contact:contact@localhost:5432/contact")
TEST_DATABASE_URL = _test_database_url(_base_url)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TEST")
os.environ.setdefault("FRONTEND_URL", "https://app.test")

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.ratelimit import auth_limiter  # noqa: E402
from app.db.session import dispose_engine, get_sessionmaker  # noqa: E402
from app.main import create_app  # noqa: E402

_TABLES = "ai_usage, training_results, messages, training_sessions, auth_sessions, scenarios, users"


async def _recreate_database() -> None:
    parts = urlsplit(TEST_DATABASE_URL)
    db_name = parts.path.lstrip("/")
    assert db_name.endswith("_test"), "тесты никогда не работают с рабочей базой"
    admin_url = urlunsplit(parts._replace(path="/postgres"))
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))
        await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    await engine.dispose()


def run_alembic(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL},
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture(scope="session")
def migrated_database():
    """Чистая тестовая база с применёнными миграциями — один раз на прогон."""
    asyncio.run(_recreate_database())
    result = run_alembic("upgrade", "head")
    assert result.returncode == 0, f"alembic upgrade head упал:\n{result.stdout}\n{result.stderr}"
    return TEST_DATABASE_URL


@pytest.fixture
async def db(migrated_database):
    """Сессия БД; таблицы очищаются до и после теста."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await session.execute(text(f"TRUNCATE {_TABLES} RESTART IDENTITY CASCADE"))
        await session.commit()
    async with sessionmaker() as session:
        yield session
    # Движок привязан к циклу событий теста — закрываем, чтобы следующий тест создал свой
    await dispose_engine()


@pytest.fixture
def settings():
    return get_settings()


@pytest.fixture
async def client(db):
    auth_limiter.reset()
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def plain_client():
    """Клиент без базы — для проверок, которым БД не нужна."""
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await dispose_engine()
