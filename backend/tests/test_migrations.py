"""Миграции: воспроизводимость и совпадение со схемой моделей."""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

import app.models  # noqa: F401
from app.db.base import Base
from tests.conftest import run_alembic


async def _diff(url: str):
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        diff = await conn.run_sync(
            lambda sync_conn: compare_metadata(MigrationContext.configure(sync_conn), Base.metadata)
        )
    await engine.dispose()
    return diff


async def test_models_match_migrations(migrated_database):
    # Если модель изменили, а миграцию не написали — тест упадёт со списком различий
    assert await _diff(migrated_database) == []


async def test_downgrade_and_upgrade_again(migrated_database):
    down = run_alembic("downgrade", "base")
    assert down.returncode == 0, down.stderr
    engine = create_async_engine(migrated_database)
    async with engine.connect() as conn:
        tables = (
            await conn.execute(text("SELECT count(*) FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version'"))
        ).scalar_one()
    await engine.dispose()
    assert tables == 0

    up = run_alembic("upgrade", "head")
    assert up.returncode == 0, up.stderr
    assert await _diff(migrated_database) == []
