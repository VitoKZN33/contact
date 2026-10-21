import time
from collections import defaultdict, deque

from app.core.errors import AppError


class SlidingWindowLimiter:
    """Ограничитель частоты в памяти процесса.

    Достаточно для MVP с одним воркером uvicorn. При масштабировании на
    несколько процессов заменяется на хранилище в PostgreSQL или Redis.
    """

    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str, now: float | None = None) -> None:
        if self.limit <= 0:
            return
        current = time.monotonic() if now is None else now
        bucket = self._hits[key]
        while bucket and current - bucket[0] >= self.window:
            bucket.popleft()
        if len(bucket) >= self.limit:
            raise AppError("rate_limited", "Слишком много запросов, попробуйте через минуту", 429)
        bucket.append(current)
        # Простая защита от разрастания: пустые ключи удаляются
        if len(self._hits) > 10_000:
            for k in [k for k, v in self._hits.items() if not v]:
                del self._hits[k]

    def reset(self) -> None:
        self._hits.clear()


# Вход: 20 попыток в минуту с одного IP
auth_limiter = SlidingWindowLimiter(limit=20, window_seconds=60)
