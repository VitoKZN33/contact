import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

PersonaKey = Literal["friendly", "neutral", "reserved", "shy", "sociable", "skeptical", "demanding", "unpredictable"]
GenderKey = Literal["male", "female"]
DifficultyKey = Literal["easy", "medium", "hard"]


class CreateTrainingRequest(BaseModel):
    scenario_id: uuid.UUID
    persona_type: PersonaKey
    persona_gender: GenderKey
    difficulty: DifficultyKey
    interaction_mode: Literal["text"] = "text"
    # Длина дополнительно ограничивается настройкой MAX_CUSTOM_SITUATION_CHARS
    custom_situation: str | None = Field(default=None, max_length=4000)

    @field_validator("custom_situation")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        return v.strip() or None if v is not None else None


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    client_message_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


class MessageOut(BaseModel):
    id: str
    sequence_number: int
    role: Literal["user", "persona"]
    content: str
    status: Literal["accepted", "completed", "failed"]
    client_message_id: str | None
    created_at: datetime


class ScenarioBrief(BaseModel):
    id: str
    slug: str
    title: str
    description: str
    objective: str
    category: str
    category_title: str


class PersonaOut(BaseModel):
    name: str
    gender: str
    type: str
    type_title: str


class TrainingOut(BaseModel):
    id: str
    status: Literal["active", "completed", "abandoned", "expired"]
    analysis_status: Literal["none", "pending", "done", "failed"]
    scenario: ScenarioBrief
    persona: PersonaOut
    difficulty: str
    difficulty_title: str
    interaction_mode: str
    custom_situation: str | None
    user_turns: int
    max_user_turns: int
    started_at: datetime
    last_message_at: datetime
    completed_at: datetime | None
    messages: list[MessageOut]


class ActiveTrainingResponse(BaseModel):
    training: TrainingOut | None


class SendMessageResponse(BaseModel):
    user_message: MessageOut
    reply: MessageOut
    user_turns: int
    turns_left: int


class FinishResponse(BaseModel):
    id: str
    status: str
    analysis_status: str


class EvidenceOut(BaseModel):
    message_seq: int
    quote: str


class PointOut(BaseModel):
    text: str
    evidence: list[EvidenceOut]


class ImprovementOut(PointOut):
    suggestion: str


class AlternativeReplyOut(BaseModel):
    message_seq: int
    original: str
    better: str
    why: str


class ScoreOut(BaseModel):
    key: str
    title: str
    score: int
    comment: str
    evidence: list[EvidenceOut]


class ResultOut(BaseModel):
    summary: str
    strengths: list[PointOut]
    improvements: list[ImprovementOut]
    alternative_replies: list[AlternativeReplyOut]
    scores: list[ScoreOut]
    created_at: datetime


class ResultResponse(BaseModel):
    training_id: str
    analysis_status: Literal["none", "pending", "done", "failed"]
    result: ResultOut | None
    disclaimer: str = "Разбор сделан ИИ по репликам этого разговора. Это не психологическая оценка."


class HistoryItem(BaseModel):
    id: str
    scenario_title: str
    category_title: str
    interaction_mode: str
    persona_name: str
    persona_type_title: str
    difficulty_title: str
    completed_at: datetime | None
    analysis_status: str
    summary: str | None


class HistoryResponse(BaseModel):
    items: list[HistoryItem]
    next_cursor: str | None
