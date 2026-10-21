from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.models import AuthSession, User
from app.services.auth import resolve_session

DbSession = Annotated[AsyncSession, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


@dataclass
class CurrentAuth:
    user: User
    session: AuthSession


async def get_current_auth(request: Request, db: DbSession, settings: AppSettings) -> CurrentAuth:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token or len(token) > 128:
        raise AppError("unauthorized", "Требуется вход", 401)
    user, session = await resolve_session(db, settings, token.strip())
    return CurrentAuth(user=user, session=session)


Auth = Annotated[CurrentAuth, Depends(get_current_auth)]


def client_ip(request: Request) -> str:
    # uvicorn --proxy-headers подставляет адрес из X-Forwarded-For (его ставит Nginx)
    return request.client.host if request.client else "unknown"
