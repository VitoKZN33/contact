from datetime import datetime

from pydantic import BaseModel, Field


class TelegramLoginRequest(BaseModel):
    init_data: str = Field(min_length=1, max_length=4096)


class UserOut(BaseModel):
    id: str
    display_name: str | None
    username: str | None
    locale: str | None
    plan: str
    notifications_enabled: bool


class LimitsOut(BaseModel):
    trainings_per_day: int
    analyses_per_day: int
    messages_per_minute: int
    max_user_turns: int
    max_message_chars: int
    max_custom_situation_chars: int


class LoginResponse(BaseModel):
    token: str
    expires_at: datetime
    user: UserOut


class MeResponse(BaseModel):
    user: UserOut
    limits: LimitsOut
