"""DeepSeek через OpenAI-совместимый /chat/completions.

Сверено с api-docs.deepseek.com (октябрь 2026):
- режим размышлений включён по умолчанию, отключается {"thinking": {"type": "disabled"}};
  в нём игнорируется temperature, а для диалога он даёт лишнюю задержку;
- JSON-режим: response_format={"type": "json_object"} и слово «json» в промпте;
- usage содержит prompt_cache_hit_tokens / prompt_cache_miss_tokens.
"""

import asyncio
import logging
import time

import httpx

from app.ai.provider import LLMError, LLMRequest, LLMResult

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class DeepSeekProvider:
    name = "deepseek"

    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
        max_retries: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._transport = transport  # подменяется в тестах

    async def complete(self, request: LLMRequest) -> LLMResult:
        if not self._api_key:
            raise LLMError("ai_not_configured", "Не задан DEEPSEEK_API_KEY")

        payload: dict = {
            "model": request.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "thinking": {"type": "disabled"},
            "stream": False,
        }
        if request.json_mode:
            payload["response_format"] = {"type": "json_object"}

        started = time.perf_counter()
        last_error: LLMError | None = None
        for attempt in range(self._max_retries + 1):
            try:
                return await self._call(payload, started)
            except LLMError as exc:
                last_error = exc
                if not exc.retryable or attempt == self._max_retries:
                    break
                # Экспоненциальная пауза 1 с, 2 с, 4 с — но не дольше общего тайм-аута
                delay = 2**attempt
                if (time.perf_counter() - started) + delay > self._timeout:
                    break
                logger.warning("deepseek retry", extra={"operation": exc.code, "duration_ms": delay * 1000})
                await asyncio.sleep(delay)
        assert last_error is not None
        last_error.latency_ms = int((time.perf_counter() - started) * 1000)
        raise last_error

    async def _call(self, payload: dict, started: float) -> LLMResult:
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout, connect=10), transport=self._transport
            ) as client:
                response = await client.post(self._url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise LLMError("ai_timeout", "AI-провайдер не ответил вовремя", retryable=False) from exc
        except httpx.HTTPError as exc:
            raise LLMError("ai_unavailable", "AI-провайдер недоступен", retryable=True) from exc

        if response.status_code == 429:
            raise LLMError("ai_rate_limited", "AI-провайдер перегружен", retryable=True)
        if response.status_code in _RETRYABLE_STATUS:
            raise LLMError("ai_unavailable", f"AI-провайдер ответил {response.status_code}", retryable=True)
        if response.status_code == 402:
            raise LLMError("ai_unavailable", "Недостаточно средств на балансе DeepSeek")
        if response.status_code >= 400:
            # Тело ошибки не логируем целиком: в нём может быть эхо запроса
            raise LLMError("ai_unavailable", f"AI-провайдер отклонил запрос ({response.status_code})")

        try:
            data = response.json()
            text = data["choices"][0]["message"]["content"] or ""
            usage = data.get("usage") or {}
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError("ai_bad_response", "Некорректный ответ AI-провайдера", retryable=True) from exc

        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        cached = int(usage.get("prompt_cache_hit_tokens") or 0)
        return LLMResult(
            text=text.strip(),
            model=str(data.get("model") or payload["model"]),
            tokens_in=prompt_tokens,
            tokens_cached=min(cached, prompt_tokens),
            tokens_out=int(usage.get("completion_tokens") or 0),
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
