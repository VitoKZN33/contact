"""Схема YAML-файла сценария. Любой файл проверяется ею до записи в БД."""

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.constants import CATEGORIES, PERSONAS

_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_KEY = re.compile(r"^[a-z][a-z0-9_]*$")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PersonaNames(_Strict):
    male: list[str] = Field(min_length=1, max_length=10)
    female: list[str] = Field(min_length=1, max_length=10)


class RoleConfig(_Strict):
    """Скрытая часть: из неё собирается роль персонажа в промпте."""

    who: str = Field(min_length=10, max_length=600, description="Кто персонаж и его положение")
    setting: str = Field(min_length=10, max_length=600, description="Где и при каких обстоятельствах разговор")
    relationship: str = Field(min_length=3, max_length=300, description="Отношения с пользователем")
    persona_goal: str = Field(min_length=5, max_length=600, description="Чего персонаж хочет в разговоре")
    hidden_context: str | None = Field(default=None, max_length=600, description="То, чего пользователь не знает")
    ending_hint: str | None = Field(default=None, max_length=300, description="Когда разговор естественно завершается")
    names: PersonaNames


class Criterion(_Strict):
    key: str = Field(max_length=40)
    title: str = Field(min_length=3, max_length=60)
    description: str = Field(min_length=10, max_length=300)

    @field_validator("key")
    @classmethod
    def _key(cls, v: str) -> str:
        if not _KEY.match(v):
            raise ValueError("key: латиница в нижнем регистре, цифры и _")
        return v


class EvaluationConfig(_Strict):
    criteria: list[Criterion] = Field(min_length=3, max_length=5)
    notes: str | None = Field(default=None, max_length=600, description="Подсказки для разбора")

    @model_validator(mode="after")
    def _unique_keys(self) -> "EvaluationConfig":
        keys = [c.key for c in self.criteria]
        if len(keys) != len(set(keys)):
            raise ValueError("ключи критериев должны быть уникальными")
        return self


class ScenarioFile(_Strict):
    slug: str = Field(max_length=64)
    version: int = Field(ge=1)
    category: Literal[tuple(CATEGORIES)]  # type: ignore[valid-type]
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=10, max_length=400)
    objective: str = Field(min_length=10, max_length=400)
    starts: Literal["persona", "user"]
    initial_message: str | None = Field(default=None, max_length=500)
    allowed_personas: list[Literal[tuple(PERSONAS)]] = Field(min_length=1)  # type: ignore[valid-type]
    requires_custom_situation: bool = False
    sort_order: int = Field(default=100, ge=0, le=10_000)
    active: bool = True
    role: RoleConfig
    evaluation: EvaluationConfig

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not _SLUG.match(v):
            raise ValueError("slug: латиница в нижнем регистре, цифры и дефисы")
        return v

    @model_validator(mode="after")
    def _consistency(self) -> "ScenarioFile":
        if self.starts == "persona" and not self.initial_message:
            raise ValueError("starts: persona требует initial_message")
        if self.starts == "user" and self.initial_message:
            raise ValueError("starts: user — initial_message должен быть пустым")
        if len(set(self.allowed_personas)) != len(self.allowed_personas):
            raise ValueError("allowed_personas содержит повторы")
        if self.category == "custom" and not self.requires_custom_situation:
            raise ValueError("категория custom требует requires_custom_situation: true")
        return self

    def content_hash(self) -> str:
        """Хэш содержимого без поля active: включение/отключение — не новая версия."""
        payload = self.model_dump(mode="json", exclude={"active"})
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
