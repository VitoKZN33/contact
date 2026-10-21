"""Ограничения БД работают независимо от кода приложения."""

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.models import AIUsage, Message, Scenario, TrainingSession, User
from app.scenarios.loader import load_dir, seed


async def _user(db, tg_id: int = 1) -> User:
    user = User(telegram_user_id=tg_id)
    db.add(user)
    await db.commit()
    return user


async def _training(db, user: User, **kw) -> TrainingSession:
    await seed(db, load_dir()[:1])
    scenario = (await db.execute(select(Scenario))).scalars().first()
    tr = TrainingSession(
        user_id=user.id,
        scenario_id=scenario.id,
        persona_type="friendly",
        persona_gender="female",
        persona_name="Анна",
        difficulty="easy",
        **kw,
    )
    db.add(tr)
    await db.commit()
    return tr


async def test_telegram_id_unique(db):
    await _user(db, 5)
    db.add(User(telegram_user_id=5))
    with pytest.raises(IntegrityError):
        await db.commit()


async def test_one_active_training_per_user(db):
    user = await _user(db)
    await _training(db, user)
    scenario_id = (await db.execute(select(Scenario.id))).scalars().first()
    db.add(
        TrainingSession(
            user_id=user.id,
            scenario_id=scenario_id,
            persona_type="neutral",
            persona_gender="male",
            persona_name="Илья",
            difficulty="hard",
        )
    )
    with pytest.raises(IntegrityError):
        await db.commit()


async def test_invalid_persona_rejected_by_db(db):
    user = await _user(db)
    await seed(db, load_dir()[:1])
    scenario_id = (await db.execute(select(Scenario.id))).scalars().first()
    db.add(
        TrainingSession(
            user_id=user.id,
            scenario_id=scenario_id,
            persona_type="evil",
            persona_gender="male",
            persona_name="X",
            difficulty="easy",
        )
    )
    with pytest.raises(IntegrityError):
        await db.commit()


async def test_message_sequence_unique(db):
    user = await _user(db)
    tr = await _training(db, user)
    db.add(Message(session_id=tr.id, sequence_number=1, role="user", content="a", status="completed"))
    await db.commit()
    db.add(Message(session_id=tr.id, sequence_number=1, role="persona", content="b", status="completed"))
    with pytest.raises(IntegrityError):
        await db.commit()


async def test_user_deletion_cascades_and_keeps_usage(db):
    user = await _user(db)
    tr = await _training(db, user)
    db.add(Message(session_id=tr.id, sequence_number=1, role="user", content="привет", status="completed"))
    db.add(AIUsage(user_id=user.id, session_id=tr.id, operation="reply", model="m", success=True))
    await db.commit()
    user_id = user.id

    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()
    db.expunge_all()

    assert (await db.execute(select(TrainingSession))).first() is None
    assert (await db.execute(select(Message))).first() is None
    usage = (await db.execute(select(AIUsage))).scalar_one()
    assert usage.user_id is None and usage.session_id is None


async def test_scenario_with_trainings_cannot_be_deleted(db):
    user = await _user(db)
    tr = await _training(db, user)
    with pytest.raises(IntegrityError):
        await db.execute(delete(Scenario).where(Scenario.id == tr.scenario_id))
        await db.commit()
