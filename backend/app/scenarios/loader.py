from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Scenario
from app.scenarios.schema import ScenarioFile

SEED_DIR = Path(__file__).parent / "seed"


class ScenarioFileError(Exception):
    pass


def load_file(path: Path) -> ScenarioFile:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ScenarioFileError(f"{path.name}: ошибка YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise ScenarioFileError(f"{path.name}: ожидается объект верхнего уровня")
    try:
        scenario = ScenarioFile.model_validate(raw)
    except ValidationError as exc:
        details = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        raise ScenarioFileError(f"{path.name}: {details}") from exc
    if path.stem != scenario.slug:
        raise ScenarioFileError(f"{path.name}: имя файла должно совпадать со slug «{scenario.slug}»")
    return scenario


def load_dir(directory: Path = SEED_DIR) -> list[ScenarioFile]:
    files = sorted(directory.glob("*.yaml"))
    if not files:
        raise ScenarioFileError(f"в {directory} нет файлов *.yaml")
    errors: list[str] = []
    scenarios: list[ScenarioFile] = []
    for path in files:
        try:
            scenarios.append(load_file(path))
        except ScenarioFileError as exc:
            errors.append(str(exc))
    if errors:
        raise ScenarioFileError("\n".join(errors))
    return scenarios


@dataclass
class SeedReport:
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    toggled: list[str] = field(default_factory=list)


def _row_from_file(sc: ScenarioFile) -> Scenario:
    return Scenario(
        slug=sc.slug,
        version=sc.version,
        title=sc.title,
        description=sc.description,
        category=sc.category,
        objective=sc.objective,
        initial_message=sc.initial_message,
        allowed_personas=list(sc.allowed_personas),
        requires_custom_situation=sc.requires_custom_situation,
        sort_order=sc.sort_order,
        role_config=sc.role.model_dump(mode="json"),
        evaluation_config=sc.evaluation.model_dump(mode="json"),
        content_hash=sc.content_hash(),
        is_active=sc.active,
    )


async def seed(db: AsyncSession, scenarios: list[ScenarioFile]) -> SeedReport:
    """Идемпотентная загрузка. Изменённое содержимое требует version+1:
    старая версия деактивируется, но остаётся для истории тренировок."""
    report = SeedReport()
    for sc in scenarios:
        latest = (
            await db.execute(
                select(Scenario).where(Scenario.slug == sc.slug).order_by(Scenario.version.desc()).limit(1)
            )
        ).scalar_one_or_none()

        if latest is None:
            db.add(_row_from_file(sc))
            report.created.append(sc.slug)
            continue

        if sc.version < latest.version:
            raise ScenarioFileError(f"{sc.slug}: в файле version {sc.version}, в БД уже {latest.version}")

        if sc.version == latest.version:
            if latest.content_hash != sc.content_hash():
                raise ScenarioFileError(
                    f"{sc.slug}: содержимое изменилось, а version осталась {sc.version} — увеличьте version"
                )
            if latest.is_active != sc.active:
                latest.is_active = sc.active
                report.toggled.append(sc.slug)
            else:
                report.unchanged.append(sc.slug)
            continue

        # Новая версия: старые деактивируются до вставки (уникальный индекс активной)
        await db.execute(update(Scenario).where(Scenario.slug == sc.slug).values(is_active=False))
        await db.flush()
        db.add(_row_from_file(sc))
        report.updated.append(sc.slug)

    await db.commit()
    return report


async def set_active(db: AsyncSession, slug: str, active: bool) -> bool:
    latest_version = (
        await db.execute(select(func.max(Scenario.version)).where(Scenario.slug == slug))
    ).scalar_one_or_none()
    if latest_version is None:
        return False
    await db.execute(update(Scenario).where(Scenario.slug == slug).values(is_active=False))
    if active:
        await db.execute(
            update(Scenario)
            .where(Scenario.slug == slug, Scenario.version == latest_version)
            .values(is_active=True)
        )
    await db.commit()
    return True
