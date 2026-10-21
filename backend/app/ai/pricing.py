"""Стоимость AI-вызовов. Цены — USD за 1M токенов, с api-docs.deepseek.com
(октябрь 2026). Переопределяются переменной AI_PRICING_JSON без релиза.

В пиковые часы (пн–пт 01:00–04:00 и 06:00–10:00 UTC, без учёта китайских
праздников) цена вдвое выше базовой.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

DEFAULT_PRICING: dict[str, dict[str, float]] = {
    # Базовая (внепиковая) цена
    "deepseek-flash": {"cache_hit": 0.003, "cache_miss": 0.15, "output": 0.6},
    "deepseek-v4-pro": {"cache_hit": 0.022, "cache_miss": 0.66, "output": 1.98},
}
PEAK_MULTIPLIER = 2
_PEAK_HOURS_UTC = set(range(1, 4)) | set(range(6, 10))


@dataclass(frozen=True)
class Price:
    cache_hit: Decimal
    cache_miss: Decimal
    output: Decimal


def load_pricing(raw_json: str) -> dict[str, Price]:
    table = DEFAULT_PRICING
    if raw_json.strip():
        table = {**DEFAULT_PRICING, **json.loads(raw_json)}
    return {
        model: Price(Decimal(str(p["cache_hit"])), Decimal(str(p["cache_miss"])), Decimal(str(p["output"])))
        for model, p in table.items()
    }


def is_peak(moment: datetime) -> bool:
    moment = moment.astimezone(UTC)
    return moment.weekday() < 5 and moment.hour in _PEAK_HOURS_UTC


def cost_usd(
    pricing: dict[str, Price],
    model: str,
    tokens_in: int,
    tokens_cached: int,
    tokens_out: int,
    moment: datetime | None = None,
) -> Decimal:
    price = pricing.get(model)
    if price is None:
        # Неизвестная модель (провайдер вернул другое имя) — считаем по самой дорогой
        price = max(pricing.values(), key=lambda p: p.output)
    multiplier = PEAK_MULTIPLIER if is_peak(moment or datetime.now(UTC)) else 1
    miss = max(tokens_in - tokens_cached, 0)
    total = (
        Decimal(tokens_cached) * price.cache_hit + Decimal(miss) * price.cache_miss + Decimal(tokens_out) * price.output
    ) * multiplier / Decimal(1_000_000)
    return total.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
