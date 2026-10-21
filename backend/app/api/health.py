import asyncio
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db.session import get_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live() -> dict:
    """Процесс жив и отвечает. Зависимости не проверяются."""
    return {"status": "ok"}


@router.get("/ready")
async def ready() -> JSONResponse:
    """Готовность принимать трафик: доступна PostgreSQL."""
    try:
        async with asyncio.timeout(3):
            async with get_engine().connect() as conn:
                await conn.execute(text("SELECT 1"))
    except Exception:
        logger.warning("readiness check failed: database unavailable", extra={"error_code": "db_unavailable"})
        return JSONResponse({"status": "unavailable", "checks": {"database": "fail"}}, status_code=503)
    return JSONResponse({"status": "ok", "checks": {"database": "ok"}})
