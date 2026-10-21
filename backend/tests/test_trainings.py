"""Полный цикл тренировки через API с mock-провайдером."""

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, update

from app.ai.provider import LLMError
from app.models import AIUsage, Message, Scenario, TrainingResult, TrainingSession, User
from app.scenarios.loader import load_dir, seed
from tests.helpers import bearer, login


@pytest.fixture
async def seeded(db):
    await seed(db, load_dir())


async def _scenario_id(db, slug: str) -> str:
    return str((await db.execute(select(Scenario.id).where(Scenario.slug == slug, Scenario.is_active))).scalar_one())


async def _start(client, db, token, slug="coffee-queue", **kw) -> dict:
    body = {
        "scenario_id": await _scenario_id(db, slug),
        "persona_type": kw.pop("persona_type", "friendly"),
        "persona_gender": kw.pop("persona_gender", "female"),
        "difficulty": kw.pop("difficulty", "medium"),
        **kw,
    }
    response = await client.post("/api/v1/trainings", json=body, headers=bearer(token))
    assert response.status_code == 201, response.text
    return response.json()


async def _say(client, token, training_id, text="Привет!", cid=None):
    return await client.post(
        f"/api/v1/trainings/{training_id}/messages",
        json={"content": text, "client_message_id": cid or uuid.uuid4().hex},
        headers=bearer(token),
    )


# --- Создание ---


async def test_create_user_start_scenario(client, db, seeded):
    token = await login(client)
    tr = await _start(client, db, token, "coffee-queue")
    assert tr["status"] == "active" and tr["messages"] == []
    assert tr["persona"]["name"] in ("Анна", "Ксения", "Вера")
    assert tr["scenario"]["objective"]


async def test_create_persona_start_scenario_has_first_line(client, db, seeded):
    token = await login(client)
    tr = await _start(client, db, token, "colleague-after-vacation", persona_type="neutral")
    assert len(tr["messages"]) == 1 and tr["messages"][0]["role"] == "persona"


async def test_idempotency_key_returns_same_training(client, db, seeded):
    token = await login(client)
    body = {
        "scenario_id": await _scenario_id(db, "coffee-queue"),
        "persona_type": "friendly",
        "persona_gender": "male",
        "difficulty": "easy",
    }
    headers = {**bearer(token), "Idempotency-Key": "start-123"}
    first = await client.post("/api/v1/trainings", json=body, headers=headers)
    second = await client.post("/api/v1/trainings", json=body, headers=headers)
    assert first.json()["id"] == second.json()["id"]
    assert (await db.execute(select(func.count()).select_from(TrainingSession))).scalar_one() == 1


async def test_second_active_training_conflict(client, db, seeded):
    token = await login(client)
    await _start(client, db, token)
    body = {
        "scenario_id": await _scenario_id(db, "train-companion"),
        "persona_type": "friendly",
        "persona_gender": "male",
        "difficulty": "easy",
    }
    response = await client.post("/api/v1/trainings", json=body, headers=bearer(token))
    assert response.status_code == 409


async def test_persona_not_allowed(client, db, seeded):
    token = await login(client)
    body = {
        "scenario_id": await _scenario_id(db, "disagree-at-meeting"),
        "persona_type": "shy",
        "persona_gender": "male",
        "difficulty": "easy",
    }
    assert (await client.post("/api/v1/trainings", json=body, headers=bearer(token))).status_code == 422


async def test_custom_scenario_requires_situation(client, db, seeded, settings, monkeypatch):
    token = await login(client)
    body = {
        "scenario_id": await _scenario_id(db, "custom-situation"),
        "persona_type": "friendly",
        "persona_gender": "male",
        "difficulty": "easy",
    }
    assert (await client.post("/api/v1/trainings", json=body, headers=bearer(token))).status_code == 422
    monkeypatch.setattr(settings, "max_custom_situation_chars", 10)
    long = body | {"custom_situation": "очень длинное описание ситуации"}
    assert (await client.post("/api/v1/trainings", json=long, headers=bearer(token))).status_code == 422


async def test_daily_training_limit(client, db, seeded, settings, monkeypatch):
    monkeypatch.setattr(settings, "limit_trainings_per_day", 1)
    token = await login(client)
    tr = await _start(client, db, token)
    await client.post(f"/api/v1/trainings/{tr['id']}/abandon", headers=bearer(token))
    body = {
        "scenario_id": await _scenario_id(db, "coffee-queue"),
        "persona_type": "friendly",
        "persona_gender": "male",
        "difficulty": "easy",
    }
    response = await client.post("/api/v1/trainings", json=body, headers=bearer(token))
    assert response.status_code == 429 and response.json()["error"]["code"] == "limit_exceeded"


# --- Ходы ---


async def test_message_roundtrip_and_prompt(client, db, seeded, llm):
    token = await login(client)
    tr = await _start(client, db, token, custom_situation=None)
    response = await _say(client, token, tr["id"], "Простите, тут всегда такая очередь?")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user_message"]["status"] == "completed"
    assert body["reply"]["role"] == "persona" and body["reply"]["sequence_number"] == 2
    assert body["user_turns"] == 1

    request = llm.calls[-1]
    assert request.messages[0].role == "system"
    assert tr["persona"]["name"] in request.messages[0].content
    assert request.messages[-1].content == "Простите, тут всегда такая очередь?"

    usage = (await db.execute(select(AIUsage))).scalar_one()
    assert usage.operation == "reply" and usage.success and usage.tokens_out > 0


async def test_duplicate_client_id_no_second_generation(client, db, seeded, llm):
    token = await login(client)
    tr = await _start(client, db, token)
    first = await _say(client, token, tr["id"], "Привет", cid="same-id-0001")
    calls = len(llm.calls)
    second = await _say(client, token, tr["id"], "Привет", cid="same-id-0001")
    assert second.status_code == 200
    assert second.json()["reply"]["id"] == first.json()["reply"]["id"]
    assert len(llm.calls) == calls
    count = (await db.execute(select(func.count()).select_from(Message))).scalar_one()
    assert count == 2


async def test_provider_failure_keeps_message_and_retry_works(client, db, seeded, llm):
    token = await login(client)
    tr = await _start(client, db, token)
    llm.fail_next(LLMError("ai_unavailable", "down", retryable=True))
    failed = await _say(client, token, tr["id"], "Сохрани меня", cid="retry-id-0001")
    assert failed.status_code == 503
    assert failed.json()["error"]["code"] == "ai_unavailable"
    msg = (await db.execute(select(Message).where(Message.client_message_id == "retry-id-0001"))).scalar_one()
    assert msg.status == "failed" and msg.content == "Сохрани меня"

    retried = await _say(client, token, tr["id"], "Сохрани меня", cid="retry-id-0001")
    assert retried.status_code == 200
    assert retried.json()["user_message"]["sequence_number"] == msg.sequence_number
    failed_usage = (await db.execute(select(func.count()).select_from(AIUsage).where(AIUsage.success.is_(False)))).scalar_one()
    assert failed_usage == 1


async def test_timeout_maps_to_504(client, db, seeded, llm):
    token = await login(client)
    tr = await _start(client, db, token)
    llm.fail_next(LLMError("ai_timeout", "slow"))
    response = await _say(client, token, tr["id"])
    assert response.status_code == 504 and response.json()["error"]["code"] == "ai_timeout"


async def test_message_in_progress_blocks_new_message(client, db, seeded):
    token = await login(client)
    tr = await _start(client, db, token)
    db.add(
        Message(
            session_id=uuid.UUID(tr["id"]), sequence_number=1, role="user", content="в пути", status="accepted",
            client_message_id="inflight-0001",
        )
    )
    await db.commit()
    response = await _say(client, token, tr["id"])
    assert response.status_code == 409 and response.json()["error"]["code"] == "message_in_progress"
    finish = await client.post(f"/api/v1/trainings/{tr['id']}/finish", headers=bearer(token))
    assert finish.status_code == 409


async def test_guard_retry_hides_out_of_character_reply(client, db, seeded, llm):
    token = await login(client)
    tr = await _start(client, db, token)
    answers = iter(["Как языковая модель, я не могу ответить", "Да, тут всегда очередь по утрам."])
    llm.respond_with(lambda req: next(answers))
    response = await _say(client, token, tr["id"])
    assert response.json()["reply"]["content"] == "Да, тут всегда очередь по утрам."
    assert len(llm.calls) == 2


async def test_guard_double_failure_is_error(client, db, seeded, llm):
    token = await login(client)
    tr = await _start(client, db, token)
    llm.respond_with(lambda req: "Я — искусственный интеллект")
    assert (await _say(client, token, tr["id"])).status_code == 503


async def test_turn_limit(client, db, seeded, settings, monkeypatch):
    monkeypatch.setattr(settings, "max_user_turns", 1)
    token = await login(client)
    tr = await _start(client, db, token)
    assert (await _say(client, token, tr["id"])).status_code == 200
    second = await _say(client, token, tr["id"])
    assert second.status_code == 409 and second.json()["error"]["code"] == "turn_limit"


async def test_message_too_long(client, db, seeded, settings, monkeypatch):
    monkeypatch.setattr(settings, "max_message_chars", 5)
    token = await login(client)
    tr = await _start(client, db, token)
    assert (await _say(client, token, tr["id"], "слишком длинно")).status_code == 422


async def test_long_dialog_is_summarized(client, db, seeded, llm, settings, monkeypatch):
    monkeypatch.setattr(settings, "context_summarize_after", 8)
    monkeypatch.setattr(settings, "context_keep_messages", 4)
    token = await login(client)
    tr = await _start(client, db, token)
    for i in range(6):
        assert (await _say(client, token, tr["id"], f"Реплика {i}")).status_code == 200
    stored = await db.get(TrainingSession, uuid.UUID(tr["id"]), populate_existing=True)
    assert stored.context_summary and stored.summary_until_seq > 0
    dialog_call = llm.calls[-1]
    assert "Что было в начале разговора" in dialog_call.messages[0].content
    assert len(dialog_call.messages) <= 1 + 8
    summary_usage = (await db.execute(select(func.count()).select_from(AIUsage).where(AIUsage.operation == "summary"))).scalar_one()
    assert summary_usage >= 1


# --- Восстановление и истечение ---


async def test_active_training_restored(client, db, seeded):
    token = await login(client)
    tr = await _start(client, db, token)
    await _say(client, token, tr["id"], "Привет")
    active = (await client.get("/api/v1/trainings/active", headers=bearer(token))).json()["training"]
    assert active["id"] == tr["id"] and len(active["messages"]) == 2


async def test_stale_training_expires(client, db, seeded):
    token = await login(client)
    tr = await _start(client, db, token)
    await db.execute(
        update(TrainingSession)
        .where(TrainingSession.id == uuid.UUID(tr["id"]))
        .values(last_message_at=datetime.now(UTC) - timedelta(hours=25))
    )
    await db.commit()
    assert (await client.get("/api/v1/trainings/active", headers=bearer(token))).json()["training"] is None
    assert (await _say(client, token, tr["id"])).status_code == 409
    # После истечения можно начать новую
    await _start(client, db, token)


# --- Завершение и разбор ---


async def test_finish_runs_analysis(client, db, seeded, llm):
    token = await login(client)
    tr = await _start(client, db, token)
    await _say(client, token, tr["id"], "Привет, вы тоже за кофе?")
    await _say(client, token, tr["id"], "Я тут первый раз")
    finish = await client.post(f"/api/v1/trainings/{tr['id']}/finish", headers=bearer(token))
    assert finish.status_code == 200 and finish.json()["status"] == "completed"

    result = (await client.get(f"/api/v1/trainings/{tr['id']}/result", headers=bearer(token))).json()
    assert result["analysis_status"] == "done"
    scores = result["result"]["scores"]
    keys = [c["key"] for c in load_dir()[[s.slug for s in load_dir()].index("coffee-queue")].evaluation.criteria]
    assert [s["key"] for s in scores] == keys and all(s["title"] for s in scores)
    assert result["disclaimer"]
    assert llm.calls[-1].json_mode is True

    again = await client.post(f"/api/v1/trainings/{tr['id']}/finish", headers=bearer(token))
    assert again.status_code == 200  # идемпотентно
    assert (await db.execute(select(func.count()).select_from(TrainingResult))).scalar_one() == 1


async def test_finish_without_messages_abandons(client, db, seeded, llm):
    token = await login(client)
    tr = await _start(client, db, token)
    body = (await client.post(f"/api/v1/trainings/{tr['id']}/finish", headers=bearer(token))).json()
    assert body["status"] == "abandoned" and body["analysis_status"] == "none"
    assert not any(c.json_mode for c in llm.calls)


async def test_bad_analysis_json_fails_then_retry_succeeds(client, db, seeded, llm):
    token = await login(client)
    tr = await _start(client, db, token)
    await _say(client, token, tr["id"], "Привет")
    original = llm._responder

    def broken(req):
        return "это не json" if req.json_mode else original(req)

    llm.respond_with(broken)
    await client.post(f"/api/v1/trainings/{tr['id']}/finish", headers=bearer(token))
    result = (await client.get(f"/api/v1/trainings/{tr['id']}/result", headers=bearer(token))).json()
    assert result["analysis_status"] == "failed" and result["result"] is None
    # Тренировка не потеряна
    detail = (await client.get(f"/api/v1/trainings/{tr['id']}", headers=bearer(token))).json()
    assert detail["status"] == "completed" and len(detail["messages"]) == 2

    llm.respond_with(original)
    retry = await client.post(f"/api/v1/trainings/{tr['id']}/retry-analysis", headers=bearer(token))
    assert retry.status_code == 202
    result = (await client.get(f"/api/v1/trainings/{tr['id']}/result", headers=bearer(token))).json()
    assert result["analysis_status"] == "done"


async def test_retry_analysis_only_after_failure(client, db, seeded):
    token = await login(client)
    tr = await _start(client, db, token)
    response = await client.post(f"/api/v1/trainings/{tr['id']}/retry-analysis", headers=bearer(token))
    assert response.status_code == 409


async def test_retry_creates_new_attempt_without_history(client, db, seeded):
    token = await login(client)
    tr = await _start(client, db, token, persona_type="skeptical", difficulty="hard")
    await _say(client, token, tr["id"])
    await client.post(f"/api/v1/trainings/{tr['id']}/finish", headers=bearer(token))
    new = await client.post(f"/api/v1/trainings/{tr['id']}/retry", headers=bearer(token))
    assert new.status_code == 201
    body = new.json()
    assert body["id"] != tr["id"] and body["messages"] == []
    assert body["persona"]["type"] == "skeptical" and body["difficulty"] == "hard"


async def test_history_pagination(client, db, seeded):
    token = await login(client)
    ids = []
    for _ in range(3):
        tr = await _start(client, db, token)
        await _say(client, token, tr["id"])
        await client.post(f"/api/v1/trainings/{tr['id']}/finish", headers=bearer(token))
        ids.append(tr["id"])
    page1 = (await client.get("/api/v1/trainings?limit=2", headers=bearer(token))).json()
    assert len(page1["items"]) == 2 and page1["next_cursor"]
    page2 = (await client.get(f"/api/v1/trainings?limit=2&cursor={page1['next_cursor']}", headers=bearer(token))).json()
    assert len(page2["items"]) == 1 and page2["next_cursor"] is None
    seen = [i["id"] for i in page1["items"] + page2["items"]]
    assert sorted(seen) == sorted(ids) and seen[0] == ids[-1]
    assert page1["items"][0]["summary"]


# --- Доступ к чужим данным ---


async def test_other_user_cannot_touch_training(client, db, seeded):
    owner = await login(client, 1, username="owner")
    intruder = await login(client, 2, username="intruder")
    tr = await _start(client, db, owner)
    await _say(client, owner, tr["id"])
    tid = tr["id"]
    for method, path in [
        ("get", f"/api/v1/trainings/{tid}"),
        ("get", f"/api/v1/trainings/{tid}/result"),
        ("post", f"/api/v1/trainings/{tid}/finish"),
        ("post", f"/api/v1/trainings/{tid}/abandon"),
        ("post", f"/api/v1/trainings/{tid}/retry"),
        ("post", f"/api/v1/trainings/{tid}/retry-analysis"),
    ]:
        response = await getattr(client, method)(path, headers=bearer(intruder))
        assert response.status_code == 404, (method, path, response.status_code)
    assert (await _say(client, intruder, tid)).status_code == 404
    assert (await client.get("/api/v1/trainings", headers=bearer(intruder))).json()["items"] == []
    assert (await client.get("/api/v1/trainings/active", headers=bearer(intruder))).json()["training"] is None


async def test_unknown_training_404(client, seeded):
    token = await login(client)
    assert (await client.get(f"/api/v1/trainings/{uuid.uuid4()}", headers=bearer(token))).status_code == 404


# --- Профиль и удаление ---


async def test_profile_and_usage(client, db, seeded):
    token = await login(client)
    profile = (await client.get("/api/v1/profile", headers=bearer(token))).json()
    assert profile["stored_data"] and profile["user"]["notifications_enabled"] is False
    patched = await client.patch("/api/v1/profile", json={"notifications_enabled": True}, headers=bearer(token))
    assert patched.json()["user"]["notifications_enabled"] is True
    await _start(client, db, token)
    usage = (await client.get("/api/v1/profile/usage", headers=bearer(token))).json()
    assert usage["trainings_today"] == 1 and usage["limits"]["trainings_per_day"] == 100


async def test_delete_history_keeps_active(client, db, seeded):
    token = await login(client)
    first = await _start(client, db, token)
    await _say(client, token, first["id"])
    await client.post(f"/api/v1/trainings/{first['id']}/finish", headers=bearer(token))
    active = await _start(client, db, token)
    deleted = (await client.delete("/api/v1/profile/trainings", headers=bearer(token))).json()
    assert deleted["deleted_trainings"] == 1
    remaining = (await db.execute(select(TrainingSession.id))).scalars().all()
    assert [str(r) for r in remaining] == [active["id"]]


async def test_delete_all_data(client, db, seeded):
    token = await login(client, 555)
    tr = await _start(client, db, token)
    await _say(client, token, tr["id"])
    refused = await client.request("DELETE", "/api/v1/profile/data", json={"confirm": "yes"}, headers=bearer(token))
    assert refused.status_code == 422
    response = await client.request("DELETE", "/api/v1/profile/data", json={"confirm": "DELETE"}, headers=bearer(token))
    assert response.status_code == 204
    assert (await db.execute(select(User).where(User.telegram_user_id == 555))).first() is None
    assert (await db.execute(select(Message))).first() is None
    assert (await client.get("/api/v1/auth/me", headers=bearer(token))).status_code == 401
    # Учёт расходов остаётся обезличенным
    usage = (await db.execute(select(AIUsage))).scalars().all()
    assert usage and all(u.user_id is None for u in usage)


async def test_logs_do_not_contain_message_text(client, db, seeded, caplog):
    token = await login(client)
    tr = await _start(client, db, token)
    secret = "моя-очень-личная-фраза"
    caplog.set_level("INFO")
    await _say(client, token, tr["id"], secret)
    assert secret not in caplog.text
    assert json.dumps(secret, ensure_ascii=False) not in caplog.text
