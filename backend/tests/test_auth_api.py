from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update

from app.core.tokens import hash_token
from app.models import AuthSession, User
from tests.helpers import bearer, login, make_init_data


async def test_login_creates_user_and_session(client, db):
    response = await client.post("/api/v1/auth/telegram", json={"init_data": make_init_data(777)})
    assert response.status_code == 200
    body = response.json()
    assert body["token"]
    assert body["user"]["display_name"] == "Иван"
    assert body["user"]["plan"] == "free"

    user = (await db.execute(select(User).where(User.telegram_user_id == 777))).scalar_one()
    stored = (await db.execute(select(AuthSession).where(AuthSession.user_id == user.id))).scalar_one()
    # В БД — только хэш токена
    assert stored.token_hash == hash_token(body["token"])
    assert stored.token_hash != body["token"]


async def test_repeat_login_updates_profile_without_duplicate(client, db):
    await login(client, 777, username="old_name")
    await login(client, 777, username="new_name")
    users = (await db.execute(select(User).where(User.telegram_user_id == 777))).scalars().all()
    assert len(users) == 1
    assert users[0].username == "new_name"
    assert (await db.execute(select(func.count()).select_from(AuthSession))).scalar_one() == 2


async def test_large_telegram_id_fits(client, db):
    big_id = 2**52 + 7
    await login(client, big_id)
    assert (await db.execute(select(User.telegram_user_id))).scalar_one() == big_id


async def test_invalid_signature_returns_401(client):
    response = await client.post(
        "/api/v1/auth/telegram", json={"init_data": make_init_data(777, bot_token="1:WRONG")}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_init_data"


async def test_expired_init_data_returns_401(client, settings):
    old = int(datetime.now(UTC).timestamp()) - settings.initdata_max_age_seconds - 5
    response = await client.post("/api/v1/auth/telegram", json={"init_data": make_init_data(777, auth_date=old)})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "init_data_expired"


async def test_me_requires_token(client):
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    bad = await client.get("/api/v1/auth/me", headers=bearer("not-a-real-token"))
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "unauthorized"


async def test_user_id_in_body_is_ignored(client):
    # Доверяем только подписанным данным: лишние поля запроса отклоняются или игнорируются
    response = await client.post(
        "/api/v1/auth/telegram", json={"init_data": make_init_data(777), "user_id": 1}
    )
    assert response.status_code == 200
    assert response.json()["user"]["id"]


async def test_me_returns_user_and_limits(client, settings):
    token = await login(client, 777)
    response = await client.get("/api/v1/auth/me", headers=bearer(token))
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["username"] == "ivan_test"
    assert body["limits"]["max_message_chars"] == settings.max_message_chars


async def test_logout_revokes_token(client):
    token = await login(client, 777)
    assert (await client.post("/api/v1/auth/logout", headers=bearer(token))).status_code == 204
    assert (await client.get("/api/v1/auth/me", headers=bearer(token))).status_code == 401


async def test_expired_session_rejected(client, db):
    token = await login(client, 777)
    await db.execute(
        update(AuthSession)
        .where(AuthSession.token_hash == hash_token(token))
        .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    )
    await db.commit()
    assert (await client.get("/api/v1/auth/me", headers=bearer(token))).status_code == 401


async def test_blocked_user_cannot_login(client, db):
    await login(client, 777)
    await db.execute(update(User).where(User.telegram_user_id == 777).values(status="blocked"))
    await db.commit()
    response = await client.post("/api/v1/auth/telegram", json={"init_data": make_init_data(777)})
    assert response.status_code == 403


async def test_tokens_are_per_user(client):
    token_a = await login(client, 1001, username="alice")
    token_b = await login(client, 1002, username="bob")
    me_a = (await client.get("/api/v1/auth/me", headers=bearer(token_a))).json()
    me_b = (await client.get("/api/v1/auth/me", headers=bearer(token_b))).json()
    assert me_a["user"]["username"] == "alice"
    assert me_b["user"]["username"] == "bob"
    assert me_a["user"]["id"] != me_b["user"]["id"]


async def test_login_rate_limited(client):
    for _ in range(20):
        await client.post("/api/v1/auth/telegram", json={"init_data": "garbage"})
    response = await client.post("/api/v1/auth/telegram", json={"init_data": make_init_data(777)})
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"
