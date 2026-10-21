import uuid

from fastapi import APIRouter, Query

from app.api.deps import Auth, DbSession
from app.schemas.scenario import CategoryListResponse, ScenarioDetail, ScenarioListResponse
from app.services import scenarios as service

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("", response_model=ScenarioListResponse)
async def list_scenarios(
    _: Auth,
    db: DbSession,
    category: str | None = Query(default=None, max_length=32),
):
    return ScenarioListResponse(items=await service.list_active(db, category))


@router.get("/categories", response_model=CategoryListResponse)
async def list_categories(_: Auth, db: DbSession):
    return CategoryListResponse(items=await service.list_categories(db))


@router.get("/{scenario_id}", response_model=ScenarioDetail)
async def get_scenario(scenario_id: uuid.UUID, _: Auth, db: DbSession):
    return service.detail(await service.get_active(db, scenario_id))
