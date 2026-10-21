from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.scenarios import router as scenarios_router

# Маршруты trainings и profile подключаются на Этапе 4
api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(scenarios_router)
