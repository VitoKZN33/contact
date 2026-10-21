from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.core.telegram_auth import InitDataError, validate_init_data
from app.core.tokens import hash_token, new_session_token
from app.models import AuthSession, User

# Продление сессии не чаще раза в сутки, чтобы не писать в БД на каждый запрос
_EXTEND_STEP = timedelta(days=1)


@dataclass(frozen=True)
class IssuedSession:
    token: str
    expires_at: datetime
    user: User


def _now() -> datetime:
    return datetime.now(UTC)


async def login_with_init_data(db: AsyncSession, settings: Settings, init_data: str) -> IssuedSession:
    try:
        validated = validate_init_data(
            init_data,
            bot_token=settings.telegram_bot_token.get_secret_value(),
            max_age_seconds=settings.initdata_max_age_seconds,
        )
    except InitDataError as exc:
        raise AppError(exc.code, exc.message, 401) from exc

    tg = validated.user
    now = _now()
    # Upsert по telegram_user_id: данные профиля обновляются при каждом входе
    stmt = (
        insert(User)
        .values(
            telegram_user_id=tg.id,
            username=tg.username,
            display_name=tg.display_name or None,
            locale=tg.language_code,
            last_active_at=now,
        )
        .on_conflict_do_update(
            index_elements=[User.telegram_user_id],
            set_={
                "username": tg.username,
                "display_name": tg.display_name or None,
                "locale": tg.language_code,
                "last_active_at": now,
                "updated_at": now,
            },
        )
        .returning(User.id)
    )
    user_id = (await db.execute(stmt)).scalar_one()
    user = await db.get(User, user_id, populate_existing=True)
    assert user is not None
    if user.status != "active":
        await db.rollback()
        raise AppError("forbidden", "Доступ ограничен", 403)

    token = new_session_token()
    expires_at = now + timedelta(days=settings.session_ttl_days)
    db.add(AuthSession(user_id=user.id, token_hash=hash_token(token), expires_at=expires_at))
    await db.commit()
    return IssuedSession(token=token, expires_at=expires_at, user=user)


async def resolve_session(db: AsyncSession, settings: Settings, token: str) -> tuple[User, AuthSession]:
    row = (
        await db.execute(
            select(AuthSession, User)
            .join(User, User.id == AuthSession.user_id)
            .where(AuthSession.token_hash == hash_token(token))
        )
    ).first()
    if row is None:
        raise AppError("unauthorized", "Сессия не найдена — войдите заново", 401)
    session, user = row
    now = _now()
    if session.revoked_at is not None or session.expires_at <= now:
        raise AppError("unauthorized", "Сессия истекла — войдите заново", 401)
    if user.status != "active":
        raise AppError("forbidden", "Доступ ограничен", 403)

    full_expiry = now + timedelta(days=settings.session_ttl_days)
    if full_expiry - session.expires_at >= _EXTEND_STEP:
        session.expires_at = full_expiry
        user.last_active_at = now
        await db.commit()
    return user, session


async def revoke_session(db: AsyncSession, session: AuthSession) -> None:
    session.revoked_at = _now()
    await db.commit()
