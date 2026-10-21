"""Интерфейс AI-провайдера. Бизнес-логика знает только его, а не DeepSeek."""

from dataclasses import dataclass, field
from typing import Literal, Protocol

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class LLMMessage:
    role: Role
    content: str


@dataclass(frozen=True)
class LLMRequest:
    messages: list[LLMMessage]
    model: str
    max_tokens: int
    temperature: float
    json_mode: bool = False


@dataclass(frozen=True)
class LLMResult:
    text: str
    model: str
    tokens_in: int = 0
    tokens_cached: int = 0
    tokens_out: int = 0
    latency_ms: int = 0


@dataclass
class LLMError(Exception):
    """code: ai_timeout | ai_rate_limited | ai_unavailable | ai_bad_response | ai_not_configured"""

    code: str
    message: str
    retryable: bool = False
    latency_ms: int = 0
    details: dict = field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


class LLMProvider(Protocol):
    name: str

    async def complete(self, request: LLMRequest) -> LLMResult: ...
