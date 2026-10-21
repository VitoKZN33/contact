from typing import Literal

from pydantic import BaseModel

from app.schemas.auth import LimitsOut, UserOut


class ProfileResponse(BaseModel):
    user: UserOut
    stored_data: list[str]


class ProfilePatch(BaseModel):
    notifications_enabled: bool


class UsageResponse(BaseModel):
    trainings_today: int
    analyses_today: int
    limits: LimitsOut


class DeleteDataRequest(BaseModel):
    confirm: Literal["DELETE"]


class DeletedResponse(BaseModel):
    deleted_trainings: int
