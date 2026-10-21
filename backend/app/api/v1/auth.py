from fastapi import APIRouter, Request, Response

from app.api.deps import AppSettings, Auth, DbSession, client_ip
from app.core.config import Settings
from app.core.ratelimit import auth_limiter
from app.models import User
from app.schemas.auth import LimitsOut, LoginResponse, MeResponse, TelegramLoginRequest, UserOut
from app.services.auth import login_with_init_data, revoke_session

router = APIRouter(prefix="/auth", tags=["auth"])


def user_out(user: User) -> UserOut:
    return UserOut(
        id=str(user.id),
        display_name=user.display_name,
        username=user.username,
        locale=user.locale,
        plan=user.plan,
        notifications_enabled=user.notifications_enabled,
    )


def limits_out(settings: Settings) -> LimitsOut:
    return LimitsOut(
        trainings_per_day=settings.limit_trainings_per_day,
        analyses_per_day=settings.limit_analyses_per_day,
        messages_per_minute=settings.limit_messages_per_minute,
        max_user_turns=settings.max_user_turns,
        max_message_chars=settings.max_message_chars,
        max_custom_situation_chars=settings.max_custom_situation_chars,
    )


@router.post("/telegram", response_model=LoginResponse)
async def login_telegram(body: TelegramLoginRequest, request: Request, db: DbSession, settings: AppSettings):
    """Проверяет подпись initData и выдаёт серверную сессию."""
    auth_limiter.hit(client_ip(request))
    issued = await login_with_init_data(db, settings, body.init_data)
    return LoginResponse(token=issued.token, expires_at=issued.expires_at, user=user_out(issued.user))


@router.get("/me", response_model=MeResponse)
async def me(auth: Auth, settings: AppSettings):
    return MeResponse(user=user_out(auth.user), limits=limits_out(settings))


@router.post("/logout", status_code=204)
async def logout(auth: Auth, db: DbSession) -> Response:
    await revoke_session(db, auth.session)
    return Response(status_code=204)
