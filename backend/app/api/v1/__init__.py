from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.profile import router as profile_router
from app.api.v1.scenarios import router as scenarios_router
from app.api.v1.trainings import router as trainings_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(scenarios_router)
api_router.include_router(trainings_router)
api_router.include_router(profile_router)
