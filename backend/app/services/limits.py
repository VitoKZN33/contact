"""Серверные лимиты бесплатного использования. Клиент их только отображает."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.core.ratelimit import SlidingWindowLimiter
from app.models import TrainingResult, TrainingSession

_message_limiters: dict[int, SlidingWindowLimiter] = {}


def day_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    return now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


def message_limiter(settings: Settings) -> SlidingWindowLimiter:
    limit = settings.limit_messages_per_minute
    if limit not in _message_limiters:
        _message_limiters[limit] = SlidingWindowLimiter(limit=limit, window_seconds=60)
    return _message_limiters[limit]


def reset_message_limiters() -> None:
    _message_limiters.clear()


async def trainings_today(db: AsyncSession, user_id: uuid.UUID) -> int:
    return (
        await db.execute(
            select(func.count())
            .select_from(TrainingSession)
            .where(TrainingSession.user_id == user_id, TrainingSession.started_at >= day_start())
        )
    ).scalar_one()


async def analyses_today(db: AsyncSession, user_id: uuid.UUID) -> int:
    done = (
        await db.execute(
            select(func.count())
            .select_from(TrainingResult)
            .join(TrainingSession, TrainingSession.id == TrainingResult.session_id)
            .where(TrainingSession.user_id == user_id, TrainingResult.created_at >= day_start())
        )
    ).scalar_one()
    pending = (
        await db.execute(
            select(func.count())
            .select_from(TrainingSession)
            .where(TrainingSession.user_id == user_id, TrainingSession.analysis_status == "pending")
        )
    ).scalar_one()
    return done + pending


async def ensure_can_start_training(db: AsyncSession, settings: Settings, user_id: uuid.UUID) -> None:
    if await trainings_today(db, user_id) >= settings.limit_trainings_per_day:
        raise AppError(
            "limit_exceeded",
            f"Лимит тренировок на сегодня исчерпан ({settings.limit_trainings_per_day}). Возвращайтесь завтра.",
            429,
        )


async def can_analyze(db: AsyncSession, settings: Settings, user_id: uuid.UUID) -> bool:
    return await analyses_today(db, user_id) < settings.limit_analyses_per_day
