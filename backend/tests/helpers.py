import json
import time

from app.core.config import get_settings
from app.core.telegram_auth import sign_init_data


def make_init_data(
    user_id: int = 100500,
    *,
    first_name: str = "Иван",
    username: str | None = "ivan_test",
    auth_date: int | None = None,
    bot_token: str | None = None,
    extra: dict[str, str] | None = None,
) -> str:
    """Честно подписанные initData — как их формирует Telegram."""
    user = {"id": user_id, "first_name": first_name, "language_code": "ru"}
    if username:
        user["username"] = username
    fields = {
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": json.dumps(user, ensure_ascii=False, separators=(",", ":")),
        "auth_date": str(int(time.time()) if auth_date is None else auth_date),
        **(extra or {}),
    }
    token = bot_token or get_settings().telegram_bot_token.get_secret_value()
    return sign_init_data(fields, token)


async def login(client, user_id: int = 100500, **kwargs) -> str:
    response = await client.post("/api/v1/auth/telegram", json={"init_data": make_init_data(user_id, **kwargs)})
    assert response.status_code == 200, response.text
    return response.json()["token"]


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
