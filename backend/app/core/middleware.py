import json
import logging
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_body
from app.core.logging import request_id_var

logger = logging.getLogger("app.request")

# Жёсткий лимит тела также задан в Nginx (client_max_body_size 64k),
# он же покрывает запросы без Content-Length.
MAX_BODY_BYTES = 64 * 1024


class RequestContextMiddleware:
    """request_id, лимит размера тела и access-лог без содержимого запросов."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex[:16]
        request_id_var.set(request_id)
        started = time.perf_counter()
        status_code = 500

        try:
            headers = dict(scope.get("headers") or [])
            content_length = headers.get(b"content-length", b"")
            if content_length.isdigit() and int(content_length) > MAX_BODY_BYTES:
                status_code = 413
                await _send_json(send, 413, error_body("payload_too_large", "Слишком большой запрос"), request_id)
                return

            async def send_wrapper(message: Message) -> None:
                nonlocal status_code
                if message["type"] == "http.response.start":
                    status_code = message["status"]
                    message.setdefault("headers", [])
                    message["headers"].append((b"x-request-id", request_id.encode()))
                await send(message)

            await self.app(scope, receive, send_wrapper)
        finally:
            path = scope.get("path", "")
            if not path.startswith("/health"):
                logger.info(
                    "request",
                    extra={
                        "method": scope.get("method"),
                        "path": path,
                        "status_code": status_code,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    },
                )
            # request_id_var не сбрасывается: каждый запрос uvicorn выполняется
            # в своей задаче, а обработчик 500 работает снаружи этого middleware.


async def _send_json(send: Send, status: int, body: dict, request_id: str) -> None:
    raw = json.dumps(body, ensure_ascii=False).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(raw)).encode()),
                (b"x-request-id", request_id.encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": raw})
