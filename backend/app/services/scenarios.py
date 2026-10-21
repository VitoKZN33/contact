import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.domain.constants import CATEGORIES, DIFFICULTIES, GENDERS, PERSONAS
from app.models import Scenario
from app.schemas.scenario import (
    CategoryOut,
    CriterionOut,
    NamedOption,
    ScenarioDetail,
    ScenarioListItem,
)


def _list_item(sc: Scenario) -> ScenarioListItem:
    return ScenarioListItem(
        id=str(sc.id),
        slug=sc.slug,
        title=sc.title,
        description=sc.description,
        category=sc.category,
        category_title=CATEGORIES[sc.category],
        starts="persona" if sc.initial_message else "user",
        requires_custom_situation=sc.requires_custom_situation,
    )


async def list_active(db: AsyncSession, category: str | None) -> list[ScenarioListItem]:
    stmt = select(Scenario).where(Scenario.is_active.is_(True))
    if category is not None:
        if category not in CATEGORIES:
            raise AppError("validation_error", "Неизвестная категория", 422)
        stmt = stmt.where(Scenario.category == category)
    rows = (await db.execute(stmt.order_by(Scenario.sort_order, Scenario.title))).scalars().all()
    return [_list_item(sc) for sc in rows]


async def list_categories(db: AsyncSession) -> list[CategoryOut]:
    counts = dict(
        (
            await db.execute(
                select(Scenario.category, func.count())
                .where(Scenario.is_active.is_(True))
                .group_by(Scenario.category)
            )
        ).all()
    )
    # Порядок — как в справочнике; пустые категории не показываются
    return [CategoryOut(key=k, title=t, scenario_count=counts[k]) for k, t in CATEGORIES.items() if counts.get(k)]


async def get_active(db: AsyncSession, scenario_id: uuid.UUID) -> Scenario:
    sc = await db.get(Scenario, scenario_id)
    if sc is None or not sc.is_active:
        raise AppError("not_found", "Сценарий не найден", 404)
    return sc


def detail(sc: Scenario) -> ScenarioDetail:
    base = _list_item(sc)
    return ScenarioDetail(
        **base.model_dump(),
        objective=sc.objective,
        personas=[NamedOption(key=k, title=PERSONAS[k]) for k in sc.allowed_personas],
        difficulties=[NamedOption(key=k, title=t) for k, t in DIFFICULTIES.items()],
        genders=[NamedOption(key=k, title=t) for k, t in GENDERS.items()],
        # Названия и описания критериев открыты: пользователь заранее знает, что оценивается
        criteria=[CriterionOut(**c) for c in sc.evaluation_config["criteria"]],
    )
