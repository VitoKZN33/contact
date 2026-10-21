"""Проверка initData без БД: подпись, возраст, структура."""

import time
from urllib.parse import parse_qsl, urlencode

import pytest

from app.core.telegram_auth import InitDataError, validate_init_data
from tests.helpers import make_init_data

TOKEN = "123456:TEST"
MAX_AGE = 3600


def test_valid_init_data_accepted():
    data = make_init_data(42, bot_token=TOKEN)
    result = validate_init_data(data, TOKEN, MAX_AGE)
    assert result.user.id == 42
    assert result.user.username == "ivan_test"
    assert result.user.display_name == "Иван"


def test_signature_field_is_part_of_check_string():
    # Новые клиенты Telegram присылают поле signature — оно входит в проверку
    data = make_init_data(42, bot_token=TOKEN, extra={"signature": "abc"})
    assert validate_init_data(data, TOKEN, MAX_AGE).user.id == 42


def test_wrong_bot_token_rejected():
    data = make_init_data(42, bot_token="999:OTHER")
    with pytest.raises(InitDataError) as exc:
        validate_init_data(data, TOKEN, MAX_AGE)
    assert exc.value.code == "invalid_init_data"


def test_tampered_user_rejected():
    fields = dict(parse_qsl(make_init_data(42, bot_token=TOKEN)))
    fields["user"] = fields["user"].replace("42", "43")
    with pytest.raises(InitDataError):
        validate_init_data(urlencode(fields), TOKEN, MAX_AGE)


def test_missing_hash_rejected():
    fields = dict(parse_qsl(make_init_data(42, bot_token=TOKEN)))
    fields.pop("hash")
    with pytest.raises(InitDataError):
        validate_init_data(urlencode(fields), TOKEN, MAX_AGE)


def test_expired_rejected_with_own_code():
    old = int(time.time()) - MAX_AGE - 10
    data = make_init_data(42, bot_token=TOKEN, auth_date=old)
    with pytest.raises(InitDataError) as exc:
        validate_init_data(data, TOKEN, MAX_AGE)
    assert exc.value.code == "init_data_expired"


def test_future_auth_date_rejected():
    future = int(time.time()) + 3600
    data = make_init_data(42, bot_token=TOKEN, auth_date=future)
    with pytest.raises(InitDataError) as exc:
        validate_init_data(data, TOKEN, MAX_AGE)
    assert exc.value.code == "invalid_init_data"


def test_duplicate_fields_rejected():
    data = make_init_data(42, bot_token=TOKEN) + "&auth_date=1"
    with pytest.raises(InitDataError):
        validate_init_data(data, TOKEN, MAX_AGE)


@pytest.mark.parametrize("garbage", ["", "not-a-query", "hash=", "a" * 5000])
def test_garbage_rejected(garbage):
    with pytest.raises(InitDataError):
        validate_init_data(garbage, TOKEN, MAX_AGE)
