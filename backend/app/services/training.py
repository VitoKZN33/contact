"""Жизненный цикл тренировки: создание, ходы, завершение, история.

Ключевые гарантии:
- реплика пользователя сохраняется ДО вызова модели и не теряется при сбое;
- повтор с тем же client_message_id не создаёт дубль;
- в тренировке одновременно обрабатывается не больше одной реплики;
- все запросы фильтруются по владельцу; чужая тренировка — 404.
"""

import logging
import random
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.dialog_prompt import DialogContext, build_dialog_messages, build_summary_messages
from app.ai.guard import GuardViolation, clean_reply
from app.ai.provider import LLMError, LLMMessage, LLMProvider, LLMRequest
from app.core.config import Settings
from app.core.errors import AppError
from app.models import Message, Scenario, TrainingResult, TrainingSession, User
from app.services import limits
from app.services.usage import record_usage

logger = logging.getLogger(__name__)

_AI_ERRORS = {
    "ai_timeout": (504, "Собеседник задумался слишком надолго. Попробуйте отправить ещё раз."),
    "ai_rate_limited": (503, "Сервис сейчас перегружен. Попробуйте через минуту."),
    "ai_unavailable": (503, "Собеседник временно недоступен. Ваше сообщение сохранено — отправьте его ещё раз."),
    "ai_bad_response": (503, "Не получилось сформулировать ответ. Отправьте сообщение ещё раз."),
    "ai_not_configured": (503, "AI-провайдер не настроен."),
}


def _now() -> datetime:
    return datetime.now(UTC)


async def _release(db: AsyncSession) -> None:
    """Завершает транзакцию и снимает блокировку строки.
    Используется commit, а не rollback: rollback сбросил бы загруженные
    объекты, и чтение их полей потребовало бы синхронной подгрузки."""
    await db.commit()


def ai_app_error(exc: LLMError) -> AppError:
    status, message = _AI_ERRORS.get(exc.code, (503, "Собеседник временно недоступен."))
    code = "ai_timeout" if exc.code == "ai_timeout" else "ai_unavailable"
    return AppError(code, message, status)


# ---------- Чтение ----------


async def get_owned(db: AsyncSession, user: User, training_id: uuid.UUID, *, lock: bool = False) -> TrainingSession:
    stmt = select(TrainingSession).where(TrainingSession.id == training_id, TrainingSession.user_id == user.id)
    if lock:
        stmt = stmt.with_for_update()
    tr = (await db.execute(stmt.execution_options(populate_existing=True))).scalar_one_or_none()
    if tr is None:
        raise AppError("not_found", "Тренировка не найдена", 404)
    return tr


async def messages_of(db: AsyncSession, training_id: uuid.UUID) -> list[Message]:
    return list(
        (
            await db.execute(
                select(Message).where(Message.session_id == training_id).order_by(Message.sequence_number)
            )
        ).scalars()
    )


async def user_turns(db: AsyncSession, training_id: uuid.UUID) -> int:
    return (
        await db.execute(
            select(func.count())
            .select_from(Message)
            .where(Message.session_id == training_id, Message.role == "user", Message.status == "completed")
        )
    ).scalar_one()


async def expire_if_stale(db: AsyncSession, settings: Settings, tr: TrainingSession) -> bool:
    if tr.status == "active" and tr.last_message_at < _now() - timedelta(hours=settings.training_ttl_hours):
        tr.status = "expired"
        tr.completed_at = _now()
        await db.commit()
        return True
    return False


async def get_active(db: AsyncSession, settings: Settings, user: User) -> TrainingSession | None:
    tr = (
        await db.execute(
            select(TrainingSession).where(TrainingSession.user_id == user.id, TrainingSession.status == "active")
        )
    ).scalar_one_or_none()
    if tr is None or await expire_if_stale(db, settings, tr):
        return None
    return tr


# ---------- Создание ----------


@dataclass(frozen=True)
class TrainingParams:
    scenario_id: uuid.UUID
    persona_type: str
    persona_gender: str
    difficulty: str
    interaction_mode: str
    custom_situation: str | None


async def create_training(
    db: AsyncSession, settings: Settings, user: User, params: TrainingParams, idempotency_key: str | None
) -> TrainingSession:
    if idempotency_key:
        existing = (
            await db.execute(
                select(TrainingSession).where(
                    TrainingSession.user_id == user.id, TrainingSession.idempotency_key == idempotency_key
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

    scenario = await db.get(Scenario, params.scenario_id)
    if scenario is None or not scenario.is_active:
        raise AppError("not_found", "Сценарий не найден", 404)
    if params.persona_type not in scenario.allowed_personas:
        raise AppError("validation_error", "Этот характер недоступен для сценария", 422)

    situation = params.custom_situation
    if scenario.requires_custom_situation and not situation:
        raise AppError("validation_error", "Опишите ситуацию своими словами", 422)
    if situation and len(situation) > settings.max_custom_situation_chars:
        raise AppError(
            "validation_error", f"Описание ситуации длиннее {settings.max_custom_situation_chars} символов", 422
        )

    active = await get_active(db, settings, user)
    if active is not None:
        raise AppError("conflict", "У вас есть незавершённая тренировка — продолжите или завершите её", 409)
    await limits.ensure_can_start_training(db, settings, user.id)

    names = scenario.role_config["names"][params.persona_gender]
    tr = TrainingSession(
        user_id=user.id,
        scenario_id=scenario.id,
        custom_situation=situation,
        persona_type=params.persona_type,
        persona_gender=params.persona_gender,
        persona_name=random.choice(names),
        difficulty=params.difficulty,
        interaction_mode=params.interaction_mode,
        idempotency_key=idempotency_key,
    )
    db.add(tr)
    try:
        await db.flush()
        if scenario.initial_message:
            db.add(
                Message(
                    session_id=tr.id,
                    sequence_number=1,
                    role="persona",
                    content=scenario.initial_message,
                    status="completed",
                )
            )
            tr.message_count = 1
        await db.commit()
    except IntegrityError as exc:
        # Параллельный запрос успел создать активную тренировку или тот же ключ
        await db.rollback()
        if idempotency_key:
            existing = (
                await db.execute(
                    select(TrainingSession).where(
                        TrainingSession.user_id == user.id, TrainingSession.idempotency_key == idempotency_key
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                return existing
        raise AppError("conflict", "У вас есть незавершённая тренировка", 409) from exc
    return tr


async def retry_training(db: AsyncSession, settings: Settings, user: User, training_id: uuid.UUID) -> TrainingSession:
    """Новая попытка с теми же параметрами. История не переносится."""
    old = await get_owned(db, user, training_id)
    old_scenario = await db.get(Scenario, old.scenario_id)
    assert old_scenario is not None
    current = (
        await db.execute(select(Scenario).where(Scenario.slug == old_scenario.slug, Scenario.is_active.is_(True)))
    ).scalar_one_or_none()
    if current is None:
        raise AppError("not_found", "Сценарий больше недоступен", 404)
    params = TrainingParams(
        scenario_id=current.id,
        persona_type=old.persona_type if old.persona_type in current.allowed_personas else current.allowed_personas[0],
        persona_gender=old.persona_gender,
        difficulty=old.difficulty,
        interaction_mode=old.interaction_mode,
        custom_situation=old.custom_situation,
    )
    return await create_training(db, settings, user, params, idempotency_key=None)


# ---------- Ход разговора ----------


@dataclass
class TurnResult:
    user_message: Message
    reply: Message
    user_turns: int


async def send_message(
    db: AsyncSession,
    settings: Settings,
    provider: LLMProvider,
    user: User,
    training_id: uuid.UUID,
    content: str,
    client_message_id: str,
) -> TurnResult:
    content = content.strip()
    if not content:
        raise AppError("validation_error", "Пустое сообщение", 422)
    if len(content) > settings.max_message_chars:
        raise AppError("validation_error", f"Сообщение длиннее {settings.max_message_chars} символов", 422)

    # 1. Под блокировкой строки тренировки: проверки и сохранение реплики
    tr = await get_owned(db, user, training_id, lock=True)
    if await expire_if_stale(db, settings, tr) or tr.status != "active":
        await _release(db)
        raise AppError("training_not_active", "Тренировка уже завершена", 409)

    existing = (
        await db.execute(
            select(Message).where(Message.session_id == tr.id, Message.client_message_id == client_message_id)
        )
    ).scalar_one_or_none()
    all_messages = await messages_of(db, tr.id)
    last_seq = all_messages[-1].sequence_number if all_messages else 0

    if existing is not None:
        if existing.status == "completed":
            reply = next((m for m in all_messages if m.sequence_number == existing.sequence_number + 1), None)
            await _release(db)
            if reply is None:
                raise AppError("conflict", "Ответ на это сообщение не найден", 409)
            return TurnResult(existing, reply, await user_turns(db, tr.id))
        if existing.status == "accepted":
            await _release(db)
            raise AppError("message_in_progress", "Сообщение уже обрабатывается", 409)
        # failed → повторная генерация, только если после него ничего не было
        if existing.sequence_number != last_seq:
            await _release(db)
            raise AppError("conflict", "Это сообщение уже устарело — отправьте новое", 409)
        existing.status = "accepted"
        existing.content = content
        user_msg = existing
    else:
        if any(m.role == "user" and m.status == "accepted" for m in all_messages):
            await _release(db)
            raise AppError("message_in_progress", "Дождитесь ответа на предыдущее сообщение", 409)
        if await user_turns(db, tr.id) >= settings.max_user_turns:
            await _release(db)
            raise AppError("turn_limit", "Разговор достиг лимита реплик — завершите тренировку, чтобы получить разбор", 409)
        limits.message_limiter(settings).hit(str(user.id))
        user_msg = Message(
            session_id=tr.id,
            sequence_number=last_seq + 1,
            role="user",
            content=content,
            status="accepted",
            client_message_id=client_message_id,
        )
        db.add(user_msg)
    await db.commit()

    # 2. Генерация вне транзакции
    scenario = await db.get(Scenario, tr.scenario_id)
    assert scenario is not None
    history_rows = [m for m in await messages_of(db, tr.id) if m.status == "completed" or m.id == user_msg.id]
    ctx = DialogContext(
        persona_name=tr.persona_name,
        persona_gender=tr.persona_gender,
        persona_type=tr.persona_type,
        difficulty=tr.difficulty,
        role_config=scenario.role_config,
        scenario_title=scenario.title,
        custom_situation=tr.custom_situation,
        context_summary=tr.context_summary,
    )
    summary_update = await _maybe_summarize(db, settings, provider, user, tr, ctx, history_rows)
    if summary_update is not None:
        ctx = DialogContext(**{**ctx.__dict__, "context_summary": summary_update[0]})
        window = [m for m in history_rows if m.sequence_number > summary_update[1]]
    else:
        window = [m for m in history_rows if m.sequence_number > tr.summary_until_seq]
    # Жёсткий предел контекста, даже если свёртка не удалась
    window = window[-max(settings.context_summarize_after, settings.context_keep_messages) :]

    try:
        reply_text, result = await _generate_reply(settings, provider, ctx, window)
    except LLMError as exc:
        user_msg.status = "failed"
        record_usage(
            db, user_id=user.id, session_id=tr.id, operation="reply", model=settings.deepseek_model_dialog, error=exc
        )
        await db.commit()
        raise ai_app_error(exc) from exc

    # 3. Сохранение ответа
    tr = await get_owned(db, user, training_id, lock=True)
    reply = Message(
        session_id=tr.id,
        sequence_number=user_msg.sequence_number + 1,
        role="persona",
        content=reply_text,
        status="completed",
    )
    db.add(reply)
    user_msg.status = "completed"
    now = _now()
    tr.last_message_at = now
    tr.message_count = user_msg.sequence_number + 1
    if summary_update is not None:
        tr.context_summary, tr.summary_until_seq = summary_update
    record_usage(db, user_id=user.id, session_id=tr.id, operation="reply", model=result.model, result=result)
    await db.commit()
    return TurnResult(user_msg, reply, await user_turns(db, tr.id))


async def _generate_reply(settings: Settings, provider: LLMProvider, ctx: DialogContext, window: list[Message]):
    messages = build_dialog_messages(ctx, [(m.role, m.content) for m in window])
    request = LLMRequest(
        messages=messages,
        model=settings.deepseek_model_dialog,
        max_tokens=settings.ai_dialog_max_tokens,
        temperature=settings.ai_dialog_temperature,
    )
    result = await provider.complete(request)
    try:
        return clean_reply(result.text, ctx.persona_name), result
    except GuardViolation as first:
        logger.warning("persona guard violation, retrying", extra={"error_code": str(first)})
    # Одна повторная попытка с напоминанием о роли
    retry = LLMRequest(
        messages=[
            *messages,
            LLMMessage(
                "system",
                f"Ответь заново: только живая реплика {ctx.persona_name} в этой ситуации, без упоминаний ИИ, "
                "правил и тренировки.",
            ),
        ],
        model=request.model,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
    )
    result = await provider.complete(retry)
    try:
        return clean_reply(result.text, ctx.persona_name), result
    except GuardViolation as exc:
        raise LLMError("ai_bad_response", "Ответ персонажа не прошёл проверку") from exc


async def _maybe_summarize(
    db: AsyncSession,
    settings: Settings,
    provider: LLMProvider,
    user: User,
    tr: TrainingSession,
    ctx: DialogContext,
    history: list[Message],
) -> tuple[str, int] | None:
    """Сворачивает раннюю часть диалога, когда он становится длинным."""
    fresh = [m for m in history if m.sequence_number > tr.summary_until_seq]
    if len(fresh) <= settings.context_summarize_after:
        return None
    chunk = fresh[: -settings.context_keep_messages]
    if not chunk:
        return None
    request = LLMRequest(
        messages=build_summary_messages(ctx.persona_name, tr.context_summary, [(m.role, m.content) for m in chunk]),
        model=settings.deepseek_model_dialog,
        max_tokens=400,
        temperature=0.2,
    )
    try:
        result = await provider.complete(request)
    except LLMError as exc:
        record_usage(db, user_id=user.id, session_id=tr.id, operation="summary", model=request.model, error=exc)
        await db.commit()
        return None
    record_usage(db, user_id=user.id, session_id=tr.id, operation="summary", model=result.model, result=result)
    await db.commit()
    return result.text.strip()[:2000], chunk[-1].sequence_number


# ---------- Завершение ----------


async def finish(db: AsyncSession, settings: Settings, user: User, training_id: uuid.UUID) -> tuple[TrainingSession, bool]:
    """Возвращает (тренировка, нужно_ли_запустить_анализ). Идемпотентно."""
    tr = await get_owned(db, user, training_id, lock=True)
    if tr.status != "active":
        await _release(db)
        return tr, False
    if any(m.status == "accepted" for m in await messages_of(db, tr.id)):
        await _release(db)
        raise AppError("message_in_progress", "Дождитесь ответа собеседника", 409)

    tr.completed_at = _now()
    if await user_turns(db, tr.id) == 0:
        tr.status = "abandoned"
        await db.commit()
        return tr, False

    tr.status = "completed"
    if await limits.can_analyze(db, settings, user.id):
        tr.analysis_status = "pending"
        start = True
    else:
        tr.analysis_status = "failed"
        start = False
    await db.commit()
    return tr, start


async def abandon(db: AsyncSession, user: User, training_id: uuid.UUID) -> TrainingSession:
    tr = await get_owned(db, user, training_id, lock=True)
    if tr.status == "active":
        tr.status = "abandoned"
        tr.completed_at = _now()
    await db.commit()
    return tr


async def request_analysis_retry(db: AsyncSession, settings: Settings, user: User, training_id: uuid.UUID) -> TrainingSession:
    tr = await get_owned(db, user, training_id, lock=True)
    if tr.status != "completed" or tr.analysis_status != "failed":
        await _release(db)
        raise AppError("conflict", "Повторный анализ доступен только после неудачного", 409)
    if not await limits.can_analyze(db, settings, user.id):
        await _release(db)
        raise AppError("limit_exceeded", "Лимит разборов на сегодня исчерпан. Попробуйте завтра.", 429)
    tr.analysis_status = "pending"
    await db.commit()
    return tr


async def get_result(db: AsyncSession, user: User, training_id: uuid.UUID) -> tuple[TrainingSession, TrainingResult | None]:
    tr = await get_owned(db, user, training_id)
    result = (
        await db.execute(select(TrainingResult).where(TrainingResult.session_id == tr.id))
    ).scalar_one_or_none()
    return tr, result


# ---------- История и удаление ----------


async def history(
    db: AsyncSession, user: User, cursor: tuple[datetime, uuid.UUID] | None, limit: int
) -> list[tuple[TrainingSession, Scenario, TrainingResult | None]]:
    stmt = (
        select(TrainingSession, Scenario, TrainingResult)
        .join(Scenario, Scenario.id == TrainingSession.scenario_id)
        .outerjoin(TrainingResult, TrainingResult.session_id == TrainingSession.id)
        .where(TrainingSession.user_id == user.id, TrainingSession.status == "completed")
    )
    if cursor is not None:
        stmt = stmt.where(tuple_(TrainingSession.completed_at, TrainingSession.id) < tuple_(*cursor))
    stmt = stmt.order_by(TrainingSession.completed_at.desc(), TrainingSession.id.desc()).limit(limit)
    return [tuple(row) for row in (await db.execute(stmt)).all()]


async def delete_history(db: AsyncSession, user: User) -> int:
    result = await db.execute(
        delete(TrainingSession).where(TrainingSession.user_id == user.id, TrainingSession.status != "active")
    )
    await db.commit()
    return result.rowcount or 0
