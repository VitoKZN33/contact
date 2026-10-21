from pathlib import Path

import pytest
import yaml
from sqlalchemy import select

from app.domain.constants import CATEGORIES
from app.models import Scenario
from app.scenarios.loader import SEED_DIR, ScenarioFileError, load_dir, load_file, seed, set_active
from app.scenarios.schema import ScenarioFile
from tests.helpers import bearer, login

# --- Файлы сценариев (без БД) ---


def test_all_seed_files_valid():
    scenarios = load_dir()
    assert 15 <= len(scenarios) <= 20
    assert len({s.slug for s in scenarios}) == len(scenarios)


def test_every_category_covered():
    categories = {s.category for s in load_dir()}
    assert categories == set(CATEGORIES)


def test_initial_messages_are_gender_neutral_enough():
    # Пол персонажа выбирает пользователь: первая реплика не должна выдавать род
    for sc in load_dir():
        if sc.initial_message:
            assert "(а)" not in sc.initial_message, sc.slug


def _write(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / f"{data['slug']}.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _sample() -> dict:
    return yaml.safe_load((SEED_DIR / "coffee-queue.yaml").read_text(encoding="utf-8"))


def test_unknown_field_rejected(tmp_path):
    data = _sample() | {"surprise": 1}
    with pytest.raises(ScenarioFileError):
        load_file(_write(tmp_path, data))


def test_unknown_persona_rejected(tmp_path):
    data = _sample()
    data["allowed_personas"] = ["friendly", "evil"]
    with pytest.raises(ScenarioFileError):
        load_file(_write(tmp_path, data))


def test_persona_start_requires_initial_message(tmp_path):
    data = _sample() | {"starts": "persona"}
    with pytest.raises(ScenarioFileError):
        load_file(_write(tmp_path, data))


def test_filename_must_match_slug(tmp_path):
    data = _sample()
    path = tmp_path / "other-name.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ScenarioFileError):
        load_file(path)


# --- Загрузка в БД ---


async def test_seed_is_idempotent(db):
    scenarios = load_dir()
    first = await seed(db, scenarios)
    assert len(first.created) == len(scenarios)
    second = await seed(db, scenarios)
    assert len(second.unchanged) == len(scenarios)
    assert not second.created and not second.updated


async def test_changed_content_requires_version_bump(db):
    sc = load_dir()[0]
    await seed(db, [sc])
    changed = ScenarioFile.model_validate(sc.model_dump() | {"title": "Другое название"})
    with pytest.raises(ScenarioFileError):
        await seed(db, [changed])
    await db.rollback()

    bumped = ScenarioFile.model_validate(sc.model_dump() | {"title": "Другое название", "version": sc.version + 1})
    report = await seed(db, [bumped])
    assert report.updated == [sc.slug]
    rows = (await db.execute(select(Scenario).where(Scenario.slug == sc.slug))).scalars().all()
    # Старая версия сохранена, активна только новая
    assert sorted((r.version, r.is_active) for r in rows) == [(sc.version, False), (sc.version + 1, True)]


async def test_disable_and_enable(db):
    sc = load_dir()[0]
    await seed(db, [sc])
    assert await set_active(db, sc.slug, False)
    assert not (await db.execute(select(Scenario.is_active).where(Scenario.slug == sc.slug))).scalar_one()
    assert await set_active(db, sc.slug, True)
    assert not await set_active(db, "no-such-slug", True)


# --- API ---


@pytest.fixture
async def seeded(db):
    await seed(db, load_dir())


async def test_scenarios_require_auth(client, seeded):
    assert (await client.get("/api/v1/scenarios")).status_code == 401


async def test_list_hides_prompt_internals(client, seeded):
    token = await login(client)
    response = await client.get("/api/v1/scenarios", headers=bearer(token))
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == len(load_dir())
    raw = response.text
    assert "role_config" not in raw and "hidden_context" not in raw and "persona_goal" not in raw


async def test_filter_by_category(client, seeded):
    token = await login(client)
    items = (await client.get("/api/v1/scenarios?category=saying_no", headers=bearer(token))).json()["items"]
    assert items and all(i["category"] == "saying_no" for i in items)
    bad = await client.get("/api/v1/scenarios?category=unknown", headers=bearer(token))
    assert bad.status_code == 422


async def test_categories_have_counts(client, seeded):
    token = await login(client)
    items = (await client.get("/api/v1/scenarios/categories", headers=bearer(token))).json()["items"]
    assert sum(i["scenario_count"] for i in items) == len(load_dir())
    assert items[0]["key"] == "acquaintance"


async def test_detail_returns_options_and_criteria(client, db, seeded):
    token = await login(client)
    sc = (await db.execute(select(Scenario).where(Scenario.slug == "coffee-queue"))).scalar_one()
    body = (await client.get(f"/api/v1/scenarios/{sc.id}", headers=bearer(token))).json()
    assert body["starts"] == "user"
    assert {p["key"] for p in body["personas"]} == set(sc.allowed_personas)
    assert len(body["difficulties"]) == 3
    assert body["criteria"][0]["title"]
    assert "hidden_context" not in str(body)


async def test_inactive_scenario_not_found(client, db, seeded):
    token = await login(client)
    await set_active(db, "coffee-queue", False)
    sc = (await db.execute(select(Scenario).where(Scenario.slug == "coffee-queue"))).scalar_one()
    assert (await client.get(f"/api/v1/scenarios/{sc.id}", headers=bearer(token))).status_code == 404
    slugs = {i["slug"] for i in (await client.get("/api/v1/scenarios", headers=bearer(token))).json()["items"]}
    assert "coffee-queue" not in slugs


async def test_invalid_uuid_is_validation_error(client, seeded):
    token = await login(client)
    response = await client.get("/api/v1/scenarios/not-a-uuid", headers=bearer(token))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
