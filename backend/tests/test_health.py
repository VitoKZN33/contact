async def test_live_ok(plain_client):
    response = await plain_client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers.get("x-request-id")


async def test_ready_with_database(client):
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["checks"]["database"] == "ok"


async def test_unknown_route_uses_error_format(plain_client):
    response = await plain_client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "not_found"
    assert error["request_id"]


async def test_oversized_body_rejected(plain_client):
    response = await plain_client.post(
        "/api/v1/auth/telegram",
        content=b"x" * (64 * 1024 + 1),
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


async def test_openapi_visibility_follows_env(plain_client, settings):
    response = await plain_client.get("/api/openapi.json")
    assert response.status_code == (200 if settings.is_dev else 404)
