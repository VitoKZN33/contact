"""Фоновый разбор тренировки. Никогда не выбрасывает исключений наружу:
любой сбой переводит тренировку в analysis_status=failed, сама тренировка сохраняется."""

import asyncio
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.ai.analysis import PROMPT_VERSION, AnalysisFormatError, build_analysis_messages, parse_analysis
from app.ai.provider import LLMError, LLMMessage, LLMProvider, LLMRequest
from app.core.config import Settings
from app.db.session import get_sessionmaker
from app.domain.constants import DIFFICULTIES, PERSONAS
from app.models import Message, Scenario, TrainingResult, TrainingSession
from app.services.usage import record_usage

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 2


async def run_analysis(training_id: uuid.UUID, provider: LLMProvider, settings: Settings) -> None:
    try:
        await _run(training_id, provider, settings)
    except Exception:
        logger.exception("analysis crashed", extra={"training_id": str(training_id), "operation": "analysis"})
        await _mark_failed(training_id)


async def _mark_failed(training_id: uuid.UUID) -> None:
    try:
        async with get_sessionmaker()() as db:
            tr = await db.get(TrainingSession, training_id)
            if tr is not None and tr.analysis_status == "pending":
                tr.analysis_status = "failed"
                await db.commit()
    except Exception:
        logger.exception("failed to mark analysis as failed", extra={"training_id": str(training_id)})


async def _run(training_id: uuid.UUID, provider: LLMProvider, settings: Settings) -> None:
    async with get_sessionmaker()() as db:
        tr = await db.get(TrainingSession, training_id)
        if tr is None or tr.analysis_status != "pending":
            return
        if (await db.execute(select(TrainingResult.id).where(TrainingResult.session_id == tr.id))).first():
            tr.analysis_status = "done"
            await db.commit()
            return

        scenario = await db.get(Scenario, tr.scenario_id)
        assert scenario is not None
        rows = (
            await db.execute(
                select(Message)
                .where(Message.session_id == tr.id, Message.status == "completed")
                .order_by(Message.sequence_number)
            )
        ).scalars().all()
        transcript = [(m.sequence_number, m.role, m.content) for m in rows]
        user_messages = {m.sequence_number: m.content for m in rows if m.role == "user"}
        criteria = scenario.evaluation_config["criteria"]
        keys = [c["key"] for c in criteria]

        messages = build_analysis_messages(
            title=scenario.title,
            objective=scenario.objective,
            persona_title=PERSONAS[tr.persona_type],
            difficulty_title=DIFFICULTIES[tr.difficulty],
            persona_name=tr.persona_name,
            criteria=criteria,
            notes=scenario.evaluation_config.get("notes"),
            custom_situation=tr.custom_situation,
            transcript=transcript,
        )

        parsed = None
        model_used = settings.deepseek_model_analysis
        for attempt in range(_MAX_ATTEMPTS):
            request = LLMRequest(
                messages=messages,
                model=settings.deepseek_model_analysis,
                max_tokens=settings.ai_analysis_max_tokens,
                temperature=settings.ai_analysis_temperature,
                json_mode=True,
                timeout_seconds=settings.ai_analysis_timeout_seconds,
            )
            try:
                result = await provider.complete(request)
            except LLMError as exc:
                record_usage(db, user_id=tr.user_id, session_id=tr.id, operation="analysis", model=request.model, error=exc)
                await db.commit()
                logger.warning("analysis provider error", extra={"training_id": str(tr.id), "error_code": exc.code})
                if not exc.retryable:
                    break
                await asyncio.sleep(2)
                continue
            record_usage(db, user_id=tr.user_id, session_id=tr.id, operation="analysis", model=result.model, result=result)
            await db.commit()
            model_used = result.model
            try:
                parsed = parse_analysis(result.text, keys, user_messages)
                break
            except AnalysisFormatError as exc:
                logger.warning("analysis format error", extra={"training_id": str(tr.id), "error_code": str(exc)[:120]})
                messages = [
                    *messages,
                    LLMMessage("assistant", result.text[:4000]),
                    LLMMessage(
                        "user",
                        f"Ответ не прошёл проверку: {exc}. Верни исправленный JSON строго по структуре, "
                        f"с оценками ровно по ключам: {', '.join(keys)}.",
                    ),
                ]

        tr = await db.get(TrainingSession, training_id, populate_existing=True)
        if tr is None:
            return  # пользователь удалил данные, пока шёл разбор
        if parsed is None:
            tr.analysis_status = "failed"
            await db.commit()
            return

        titles = {c["key"]: c["title"] for c in criteria}
        db.add(
            TrainingResult(
                session_id=tr.id,
                summary=parsed.summary,
                strengths=[p.model_dump() for p in parsed.strengths],
                improvement_points=[p.model_dump() for p in parsed.improvements],
                alternative_replies=[a.model_dump() for a in parsed.alternative_replies],
                scores=[{**s.model_dump(), "title": titles[s.key]} for s in parsed.scores],
                prompt_version=PROMPT_VERSION,
                model=model_used[:64],
            )
        )
        tr.analysis_status = "done"
        try:
            await db.commit()
        except IntegrityError:
            # Параллельный запуск уже сохранил результат
            await db.rollback()
        logger.info("analysis done", extra={"training_id": str(training_id), "operation": "analysis"})


# Задачи, запущенные вне запроса (восстановление после перезапуска)
_background: set[asyncio.Task] = set()


async def recover_pending(provider: LLMProvider, settings: Settings) -> None:
    """При старте процесса: разборы в статусе pending остались от прошлого запуска."""
    async with get_sessionmaker()() as db:
        ids = list(
            (await db.execute(select(TrainingSession.id).where(TrainingSession.analysis_status == "pending"))).scalars()
        )
    if ids:
        logger.info("recovering pending analyses", extra={"operation": "analysis", "duration_ms": len(ids)})
    for training_id in ids:
        await run_analysis(training_id, provider, settings)


def schedule_recovery(provider: LLMProvider, settings: Settings) -> None:
    task = asyncio.create_task(recover_pending(provider, settings))
    _background.add(task)
    task.add_done_callback(_background.discard)
