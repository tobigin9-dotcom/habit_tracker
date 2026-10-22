from datetime import date, datetime, time
from pydantic import BaseModel, ConfigDict, Field, field_validator


class RegisterRequest(BaseModel):
    telegram_id: int = Field(gt=0)
    display_name: str = Field(default="Telegram user", min_length=1, max_length=120)
    password: str = Field(min_length=10, max_length=128)


class TokenRequest(BaseModel):
    telegram_id: int = Field(gt=0)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    telegram_id: int
    display_name: str
    created_at: datetime


class HabitCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)
    goal: str = Field(default="", max_length=255)
    target_completions: int = Field(default=21, ge=1, le=3650)
    reminder_time: time

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return value.strip()


class HabitUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    goal: str | None = Field(default=None, max_length=255)
    target_completions: int | None = Field(default=None, ge=1, le=3650)
    reminder_time: time | None = None
    is_active: bool | None = None


class HabitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str
    goal: str
    target_completions: int
    completion_count: int
    reminder_time: time
    is_active: bool
    created_at: datetime


class CompletionRequest(BaseModel):
    is_completed: bool


class CompletionResponse(BaseModel):
    habit_id: int
    completion_date: date
    is_completed: bool
    completion_count: int


class HabitStatsResponse(BaseModel):
    habit_id: int
    name: str
    target_completions: int
    completion_count: int
    remaining_completions: int
    total_recorded_days: int
    completed_days: int
    completion_rate_percent: float


class DueReminder(BaseModel):
    habit_id: int
    telegram_id: int
    name: str
    description: str
    is_completed_today: bool
