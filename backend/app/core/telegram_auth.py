"""Проверка Telegram Mini Apps initData по официальному алгоритму.

https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app

secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)
hash       = hex(HMAC_SHA256(key=secret_key, msg=data_check_string))
data_check_string — все поля, кроме hash, в виде key=value, отсортированные
по ключу и соединённые через \\n.
"""

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

# Допуск на расхождение часов клиента и сервера
_CLOCK_SKEW_SECONDS = 60


class InitDataError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class TelegramUser:
    id: int
    first_name: str
    last_name: str | None
    username: str | None
    language_code: str | None

    @property
    def display_name(self) -> str:
        return " ".join(p for p in (self.first_name, self.last_name) if p)[:128]


@dataclass(frozen=True)
class ValidatedInitData:
    user: TelegramUser
    auth_date: int


def _secret_key(bot_token: str) -> bytes:
    return hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()


def sign_init_data(fields: dict[str, str], bot_token: str) -> str:
    """Подпись по тому же алгоритму. Используется в тестах для честных initData."""
    from urllib.parse import urlencode

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    digest = hmac.new(_secret_key(bot_token), data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode({**fields, "hash": digest})


def validate_init_data(init_data: str, bot_token: str, max_age_seconds: int, now: float | None = None) -> ValidatedInitData:
    if not init_data or len(init_data) > 4096:
        raise InitDataError("invalid_init_data", "Некорректные данные запуска")

    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    except ValueError as exc:
        raise InitDataError("invalid_init_data", "Некорректные данные запуска") from exc

    fields: dict[str, str] = {}
    for key, value in pairs:
        if key in fields:
            raise InitDataError("invalid_init_data", "Повторяющиеся поля в данных запуска")
        fields[key] = value

    received_hash = fields.pop("hash", None)
    if not received_hash:
        raise InitDataError("invalid_init_data", "Нет подписи данных запуска")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    expected = hmac.new(_secret_key(bot_token), data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash.lower()):
        raise InitDataError("invalid_init_data", "Подпись данных запуска не совпадает")

    # Возраст проверяется только после подписи: auth_date подписан
    try:
        auth_date = int(fields.get("auth_date", ""))
    except ValueError as exc:
        raise InitDataError("invalid_init_data", "Нет даты авторизации") from exc
    current = time.time() if now is None else now
    if auth_date > current + _CLOCK_SKEW_SECONDS:
        raise InitDataError("invalid_init_data", "Дата авторизации в будущем")
    if current - auth_date > max_age_seconds:
        raise InitDataError("init_data_expired", "Данные запуска устарели — перезапустите приложение")

    try:
        raw_user = json.loads(fields["user"])
        user = TelegramUser(
            id=int(raw_user["id"]),
            first_name=str(raw_user.get("first_name") or "")[:64],
            last_name=(str(raw_user["last_name"])[:64] if raw_user.get("last_name") else None),
            username=(str(raw_user["username"])[:64] if raw_user.get("username") else None),
            language_code=(str(raw_user["language_code"])[:16] if raw_user.get("language_code") else None),
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise InitDataError("invalid_init_data", "Нет данных пользователя") from exc
    if user.id <= 0:
        raise InitDataError("invalid_init_data", "Некорректный пользователь")

    return ValidatedInitData(user=user, auth_date=auth_date)
