"""Current-user food record API schemas."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

MealType = str

ALLOWED_MEAL_TYPES = {"breakfast", "lunch", "dinner", "snack", "extra"}
ALLOWED_FOOD_RECORD_SOURCES = {"manual", "food_user_input", "food_ocr_confirmed"}
MAX_LABEL_LENGTH = 120


class FoodRecordCreate(BaseModel):
    """Create request for a user-confirmed food record."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    recorded_date: date
    meal_type: MealType = Field(min_length=1, max_length=24)
    display_items: list[str] = Field(min_length=1, max_length=12)
    amount_text: str | None = Field(default=None, min_length=1, max_length=120)
    estimated_tags: list[str] | None = Field(default=None, max_length=16)
    rough_nutrient_axes: list[str] | None = Field(default=None, max_length=16)
    user_confirmed: bool = True
    source: str = Field(default="manual", min_length=1, max_length=40)
    food_db_match_id: str | None = Field(default=None, min_length=1, max_length=120)
    match_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    nutrient_estimates: dict[str, float] | None = None

    @field_validator("meal_type")
    @classmethod
    def validate_meal_type(cls, value: str) -> str:
        normalized = value.casefold().strip()
        if normalized not in ALLOWED_MEAL_TYPES:
            raise ValueError("Unsupported meal_type.")
        return normalized

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str) -> str:
        normalized = value.casefold().strip()
        if normalized not in ALLOWED_FOOD_RECORD_SOURCES:
            raise ValueError("Unsupported food record source.")
        return normalized

    @field_validator("display_items")
    @classmethod
    def validate_display_items(cls, value: list[str]) -> list[str]:
        return _normalize_labels(value, field_name="display_items")

    @field_validator("estimated_tags", "rough_nutrient_axes")
    @classmethod
    def validate_optional_labels(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return _normalize_labels(value, field_name="labels")


class FoodRecordUpdate(BaseModel):
    """Update request for a user-confirmed food record."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    recorded_date: date | None = None
    meal_type: MealType | None = Field(default=None, min_length=1, max_length=24)
    display_items: list[str] | None = Field(default=None, min_length=1, max_length=12)
    amount_text: str | None = Field(default=None, min_length=1, max_length=120)
    estimated_tags: list[str] | None = Field(default=None, max_length=16)
    rough_nutrient_axes: list[str] | None = Field(default=None, max_length=16)
    user_confirmed: bool | None = None
    source: str | None = Field(default=None, min_length=1, max_length=40)
    food_db_match_id: str | None = Field(default=None, min_length=1, max_length=120)
    match_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    nutrient_estimates: dict[str, float] | None = None

    @field_validator("meal_type")
    @classmethod
    def validate_meal_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return FoodRecordCreate.validate_meal_type(value)

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return FoodRecordCreate.validate_source(value)

    @field_validator("display_items")
    @classmethod
    def validate_display_items(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return _normalize_labels(value, field_name="display_items")

    @field_validator("estimated_tags", "rough_nutrient_axes")
    @classmethod
    def validate_optional_labels(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return _normalize_labels(value, field_name="labels")


class FoodRecordResponse(BaseModel):
    """Public saved food record response."""

    id: UUID
    recorded_date: date
    meal_type: str
    display_items: list[str] = Field(default_factory=list)
    amount_text: str | None = None
    estimated_tags: list[str] = Field(default_factory=list)
    rough_nutrient_axes: list[str] = Field(default_factory=list)
    user_confirmed: bool
    source: str
    food_db_match_id: str | None = None
    match_confidence: float | None = None
    nutrient_estimates: dict[str, float] | None = None
    created_at: datetime
    updated_at: datetime


class FoodRecordListResponse(BaseModel):
    """List response for current-user food records."""

    items: list[FoodRecordResponse] = Field(default_factory=list)


def _normalize_labels(values: list[str], *, field_name: str) -> list[str]:
    normalized: list[str] = []
    for item in values:
        cleaned = item.strip()
        if not cleaned or len(cleaned) > MAX_LABEL_LENGTH:
            raise ValueError(f"{field_name} must contain bounded non-empty labels.")
        if cleaned not in normalized:
            normalized.append(cleaned)
    return normalized
