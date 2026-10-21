"""Mock-провайдер для тестов и локальной разработки: без сети и без затрат."""

import json
from collections.abc import Callable

from app.ai.provider import LLMError, LLMRequest, LLMResult

Responder = Callable[[LLMRequest], str]


class MockProvider:
    name = "mock"

    def __init__(self, responder: Responder | None = None) -> None:
        self.calls: list[LLMRequest] = []
        self._responder = responder or default_responder
        self._failures: list[LLMError] = []

    def fail_next(self, *errors: LLMError) -> None:
        """Следующие вызовы завершатся этими ошибками по очереди."""
        self._failures.extend(errors)

    def respond_with(self, responder: Responder) -> None:
        self._responder = responder

    async def complete(self, request: LLMRequest) -> LLMResult:
        self.calls.append(request)
        if self._failures:
            raise self._failures.pop(0)
        text = self._responder(request)
        prompt_chars = sum(len(m.content) for m in request.messages)
        return LLMResult(
            text=text,
            model=request.model,
            tokens_in=prompt_chars // 3,
            tokens_cached=0,
            tokens_out=max(1, len(text) // 3),
            latency_ms=5,
        )


def default_responder(request: LLMRequest) -> str:
    if request.json_mode:
        return json.dumps(sample_analysis(request), ensure_ascii=False)
    last_user = next((m.content for m in reversed(request.messages) if m.role == "user"), "")
    if "Сожми" in request.messages[0].content:
        return "Собеседники познакомились и обсудили работу."
    return f"Интересно. А почему ты так думаешь? ({len(last_user)})"


def sample_analysis(request: LLMRequest) -> dict:
    """Валидный разбор: критерии берутся из промпта (строки «- key: ...»)."""
    system = request.messages[0].content
    keys_line = next((line for line in system.splitlines() if line.startswith("Ключи критериев:")), "")
    keys = [k.strip() for k in keys_line.split(":", 1)[-1].split(",") if k.strip()]
    first_seq = 1
    for m in request.messages:
        for line in m.content.splitlines():
            if line.startswith("[") and "] Пользователь:" in line:
                first_seq = int(line[1 : line.index("]")])
                break
    return {
        "summary": "Разговор получился живым, пользователь задавал вопросы.",
        "strengths": [{"text": "Начал разговор с ситуации", "evidence": [{"message_seq": first_seq, "quote": ""}]}],
        "improvements": [
            {
                "text": "Можно больше рассказывать о себе",
                "suggestion": "Добавляйте короткую историю из своего опыта",
                "evidence": [],
            }
        ],
        "alternative_replies": [],
        "scores": [{"key": k, "score": 4, "comment": "Хорошо", "evidence": []} for k in keys],
    }
