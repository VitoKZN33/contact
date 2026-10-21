import base64
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query

from app.ai.factory import get_llm_provider
from app.ai.provider import LLMProvider
from app.api.deps import AppSettings, Auth, DbSession
from app.core.errors import AppError
from app.models import Scenario
from app.schemas.training import (
    ActiveTrainingResponse,
    CreateTrainingRequest,
    FinishResponse,
    HistoryResponse,
    ResultResponse,
    SendMessageRequest,
    SendMessageResponse,
    TrainingOut,
)
from app.services import training as service
from app.services.analysis_runner import run_analysis
from app.services.serializers import history_item, message_out, result_out, training_out

router = APIRouter(prefix="/trainings", tags=["trainings"])

Provider = Annotated[LLMProvider, Depends(get_llm_provider)]


async def _full(db, settings, tr) -> TrainingOut:
    sc = await db.get(Scenario, tr.scenario_id)
    return training_out(tr, sc, await service.messages_of(db, tr.id), await service.user_turns(db, tr.id), settings)


def _encode_cursor(completed_at: datetime, training_id: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(f"{completed_at.isoformat()}|{training_id}".encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        stamp, raw_id = base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
        return datetime.fromisoformat(stamp), uuid.UUID(raw_id)
    except (ValueError, UnicodeDecodeError) as exc:
        raise AppError("validation_error", "Некорректный курсор", 422) from exc


@router.post("", response_model=TrainingOut, status_code=201)
async def create_training(
    body: CreateTrainingRequest,
    auth: Auth,
    db: DbSession,
    settings: AppSettings,
    idempotency_key: Annotated[str | None, Header(max_length=64)] = None,
):
    tr = await service.create_training(
        db,
        settings,
        auth.user,
        service.TrainingParams(
            scenario_id=body.scenario_id,
            persona_type=body.persona_type,
            persona_gender=body.persona_gender,
            difficulty=body.difficulty,
            interaction_mode=body.interaction_mode,
            custom_situation=body.custom_situation,
        ),
        idempotency_key,
    )
    return await _full(db, settings, tr)


@router.get("/active", response_model=ActiveTrainingResponse)
async def active_training(auth: Auth, db: DbSession, settings: AppSettings):
    tr = await service.get_active(db, settings, auth.user)
    return ActiveTrainingResponse(training=await _full(db, settings, tr) if tr else None)


@router.get("", response_model=HistoryResponse)
async def list_history(
    auth: Auth,
    db: DbSession,
    cursor: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=20, ge=1, le=50),
):
    rows = await service.history(db, auth.user, _decode_cursor(cursor) if cursor else None, limit + 1)
    page = rows[:limit]
    next_cursor = None
    if len(rows) > limit and page:
        last = page[-1][0]
        next_cursor = _encode_cursor(last.completed_at, last.id)
    return HistoryResponse(items=[history_item(*row) for row in page], next_cursor=next_cursor)


@router.get("/{training_id}", response_model=TrainingOut)
async def get_training(training_id: uuid.UUID, auth: Auth, db: DbSession, settings: AppSettings):
    tr = await service.get_owned(db, auth.user, training_id)
    await service.expire_if_stale(db, settings, tr)
    return await _full(db, settings, tr)


@router.post("/{training_id}/messages", response_model=SendMessageResponse)
async def send_message(
    training_id: uuid.UUID, body: SendMessageRequest, auth: Auth, db: DbSession, settings: AppSettings, provider: Provider
):
    turn = await service.send_message(
        db, settings, provider, auth.user, training_id, body.content, body.client_message_id
    )
    return SendMessageResponse(
        user_message=message_out(turn.user_message),
        reply=message_out(turn.reply),
        user_turns=turn.user_turns,
        turns_left=max(settings.max_user_turns - turn.user_turns, 0),
    )


@router.post("/{training_id}/finish", response_model=FinishResponse)
async def finish_training(
    training_id: uuid.UUID,
    auth: Auth,
    db: DbSession,
    settings: AppSettings,
    provider: Provider,
    background: BackgroundTasks,
):
    tr, start_analysis = await service.finish(db, settings, auth.user, training_id)
    if start_analysis:
        background.add_task(run_analysis, tr.id, provider, settings)
    return FinishResponse(id=str(tr.id), status=tr.status, analysis_status=tr.analysis_status)


@router.post("/{training_id}/abandon", response_model=FinishResponse)
async def abandon_training(training_id: uuid.UUID, auth: Auth, db: DbSession):
    tr = await service.abandon(db, auth.user, training_id)
    return FinishResponse(id=str(tr.id), status=tr.status, analysis_status=tr.analysis_status)


@router.get("/{training_id}/result", response_model=ResultResponse)
async def get_result(training_id: uuid.UUID, auth: Auth, db: DbSession):
    tr, result = await service.get_result(db, auth.user, training_id)
    return ResultResponse(
        training_id=str(tr.id),
        analysis_status=tr.analysis_status,  # type: ignore[arg-type]
        result=result_out(result) if result else None,
    )


@router.post("/{training_id}/retry-analysis", response_model=FinishResponse, status_code=202)
async def retry_analysis(
    training_id: uuid.UUID,
    auth: Auth,
    db: DbSession,
    settings: AppSettings,
    provider: Provider,
    background: BackgroundTasks,
):
    tr = await service.request_analysis_retry(db, settings, auth.user, training_id)
    background.add_task(run_analysis, tr.id, provider, settings)
    return FinishResponse(id=str(tr.id), status=tr.status, analysis_status=tr.analysis_status)


@router.post("/{training_id}/retry", response_model=TrainingOut, status_code=201)
async def retry_training(training_id: uuid.UUID, auth: Auth, db: DbSession, settings: AppSettings):
    tr = await service.retry_training(db, settings, auth.user, training_id)
    return await _full(db, settings, tr)
