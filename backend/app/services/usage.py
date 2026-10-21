import logging
import uuid
from datetime import UTC, datetime
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.pricing import Price, cost_usd, load_pricing
from app.ai.provider import LLMError, LLMResult
from app.core.config import get_settings
from app.models import AIUsage

logger = logging.getLogger(__name__)


@lru_cache
def pricing() -> dict[str, Price]:
    return load_pricing(get_settings().ai_pricing_json)


def record_usage(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    session_id: uuid.UUID | None,
    operation: str,
    model: str,
    result: LLMResult | None = None,
    error: LLMError | None = None,
) -> AIUsage:
    """Добавляет строку учёта в текущую транзакцию. Тексты не сохраняются."""
    now = datetime.now(UTC)
    if result is not None:
        row = AIUsage(
            user_id=user_id,
            session_id=session_id,
            operation=operation,
            model=result.model[:64],
            tokens_in=result.tokens_in,
            tokens_cached=result.tokens_cached,
            tokens_out=result.tokens_out,
            cost_usd=cost_usd(pricing(), result.model, result.tokens_in, result.tokens_cached, result.tokens_out, now),
            latency_ms=result.latency_ms,
            success=True,
        )
    else:
        row = AIUsage(
            user_id=user_id,
            session_id=session_id,
            operation=operation,
            model=model[:64],
            tokens_in=0,
            tokens_cached=0,
            tokens_out=0,
            cost_usd=0,
            latency_ms=error.latency_ms if error else 0,
            success=False,
        )
    db.add(row)
    logger.info(
        "ai call",
        extra={
            "operation": operation,
            "training_id": str(session_id) if session_id else None,
            "duration_ms": row.latency_ms,
            "error_code": error.code if error else None,
        },
    )
    return row
