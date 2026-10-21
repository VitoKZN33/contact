from typing import Literal

from pydantic import BaseModel


class NamedOption(BaseModel):
    key: str
    title: str


class CriterionOut(BaseModel):
    key: str
    title: str
    description: str


class ScenarioListItem(BaseModel):
    id: str
    slug: str
    title: str
    description: str
    category: str
    category_title: str
    starts: Literal["persona", "user"]
    requires_custom_situation: bool


class ScenarioDetail(ScenarioListItem):
    objective: str
    personas: list[NamedOption]
    difficulties: list[NamedOption]
    genders: list[NamedOption]
    criteria: list[CriterionOut]


class ScenarioListResponse(BaseModel):
    items: list[ScenarioListItem]


class CategoryOut(BaseModel):
    key: str
    title: str
    scenario_count: int


class CategoryListResponse(BaseModel):
    items: list[CategoryOut]
