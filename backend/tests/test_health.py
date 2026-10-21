async def test_live_ok(client):
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers.get("x-request-id")


async def test_ready_checks_database(client):
    # В docker compose БД доступна → 200; без БД → 503 с понятным телом
    response = await client.get("/health/ready")
    assert response.status_code in (200, 503)
    body = response.json()
    assert body["checks"]["database"] in ("ok", "fail")


async def test_unknown_route_uses_error_format(client):
    response = await client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "not_found"
    assert error["request_id"]


async def test_oversized_body_rejected(client):
    response = await client.post(
        "/api/v1/anything",
        content=b"x" * (64 * 1024 + 1),
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


async def test_openapi_visibility_follows_env(client):
    from app.core.config import get_settings

    response = await client.get("/api/openapi.json")
    expected = 200 if get_settings().is_dev else 404
    assert response.status_code == expected
