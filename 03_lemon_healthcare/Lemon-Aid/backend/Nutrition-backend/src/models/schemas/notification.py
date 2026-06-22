"""Reminder preference API schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReminderCategory(StrEnum):
    """Supported reminder categories."""

    SUPPLEMENT_REMINDER = "supplement_reminder"
    MEAL_CHECK_IN = "meal_check_in"
    DAILY_COACHING_PROMPT = "daily_coaching_prompt"
    SAFETY_FOLLOW_UP = "safety_follow_up"


FORBIDDEN_REMINDER_TERMS = {
    "진단",
    "처방",
    "치료",
    "diagnose",
    "prescribe",
    "treat",
    "treatment",
}
MAX_HOUR_OF_DAY = 23


class ReminderPreferenceCreate(BaseModel):
    """Create request for a health reminder preference."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    category: ReminderCategory
    time_of_day: str = Field(pattern=r"^[0-2][0-9]:[0-5][0-9]$")
    timezone: str = Field(default="Asia/Seoul", min_length=1, max_length=80)
    enabled: bool = True
    message: str = Field(min_length=1, max_length=240)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("time_of_day")
    @classmethod
    def validate_time_of_day(cls, value: str) -> str:
        """Reject impossible HH:MM values."""
        hour = int(value[:2])
        if hour > MAX_HOUR_OF_DAY:
            raise ValueError("time_of_day hour must be 00-23.")
        return value

    @field_validator("message")
    @classmethod
    def validate_safe_message(cls, value: str) -> str:
        """Reject diagnosis, treatment, prescription, and sales language."""
        lowered = value.lower()
        if any(term in lowered for term in FORBIDDEN_REMINDER_TERMS):
            raise ValueError(
                "Reminder text must avoid diagnosis, treatment, or prescription language."
            )
        return value


class ReminderPreferenceUpdate(BaseModel):
    """Update request for a health reminder preference."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    time_of_day: str | None = Field(default=None, pattern=r"^[0-2][0-9]:[0-5][0-9]$")
    timezone: str | None = Field(default=None, min_length=1, max_length=80)
    enabled: bool | None = None
    message: str | None = Field(default=None, min_length=1, max_length=240)
    metadata: dict[str, Any] | None = None

    @field_validator("time_of_day")
    @classmethod
    def validate_time_of_day(cls, value: str | None) -> str | None:
        """Reject impossible HH:MM values."""
        if value is None:
            return None
        hour = int(value[:2])
        if hour > MAX_HOUR_OF_DAY:
            raise ValueError("time_of_day hour must be 00-23.")
        return value

    @field_validator("message")
    @classmethod
    def validate_safe_message(cls, value: str | None) -> str | None:
        """Reject diagnosis, treatment, prescription, and sales language."""
        if value is None:
            return None
        lowered = value.lower()
        if any(term in lowered for term in FORBIDDEN_REMINDER_TERMS):
            raise ValueError(
                "Reminder text must avoid diagnosis, treatment, or prescription language."
            )
        return value


class ReminderPreferenceResponse(BaseModel):
    """Public reminder preference response."""

    id: UUID
    category: ReminderCategory
    time_of_day: str
    timezone: str
    enabled: bool
    message: str
    created_at: datetime
    updated_at: datetime
    disabled_at: datetime | None = None


class ReminderPreferenceListResponse(BaseModel):
    """List response for current-user reminder preferences."""

    items: list[ReminderPreferenceResponse] = Field(default_factory=list)
