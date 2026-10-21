from fastapi import APIRouter, Response
from sqlalchemy import delete

from app.api.deps import AppSettings, Auth, DbSession
from app.api.v1.auth import limits_out, user_out
from app.models import User
from app.schemas.profile import (
    DeleteDataRequest,
    DeletedResponse,
    ProfilePatch,
    ProfileResponse,
    UsageResponse,
)
from app.services import limits
from app.services import training as training_service

router = APIRouter(prefix="/profile", tags=["profile"])

STORED_DATA = [
    "Telegram ID, имя, username и язык интерфейса — для входа и приветствия",
    "Тренировки: выбранные параметры, реплики и разборы — чтобы показывать историю",
    "Технические счётчики AI-запросов без текстов — для лимитов и расчёта затрат",
    "Тексты разговоров отправляются AI-провайдеру DeepSeek только для ответа и разбора; ваши Telegram ID и имя туда не передаются",
    "Диалоги не используются для обучения моделей",
]


@router.get("", response_model=ProfileResponse)
async def get_profile(auth: Auth):
    return ProfileResponse(user=user_out(auth.user), stored_data=STORED_DATA)


@router.patch("", response_model=ProfileResponse)
async def patch_profile(body: ProfilePatch, auth: Auth, db: DbSession):
    auth.user.notifications_enabled = body.notifications_enabled
    await db.commit()
    return ProfileResponse(user=user_out(auth.user), stored_data=STORED_DATA)


@router.get("/usage", response_model=UsageResponse)
async def get_usage(auth: Auth, db: DbSession, settings: AppSettings):
    return UsageResponse(
        trainings_today=await limits.trainings_today(db, auth.user.id),
        analyses_today=await limits.analyses_today(db, auth.user.id),
        limits=limits_out(settings),
    )


@router.delete("/trainings", response_model=DeletedResponse)
async def delete_trainings(auth: Auth, db: DbSession):
    """Удаляет завершённые тренировки с репликами и разборами. Активная остаётся."""
    return DeletedResponse(deleted_trainings=await training_service.delete_history(db, auth.user))


@router.delete("/data", status_code=204)
async def delete_all_data(body: DeleteDataRequest, auth: Auth, db: DbSession) -> Response:
    """Полное удаление: пользователь, сессии входа, тренировки, реплики, разборы.
    В учёте расходов ссылки на пользователя обнуляются (ON DELETE SET NULL)."""
    await db.execute(delete(User).where(User.id == auth.user.id))
    await db.commit()
    return Response(status_code=204)
