"""Current-user medication profile API schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_MEDICATION_CLASSES = {
    "ace_inhibitor",
    "arb",
    "beta_blocker",
    "calcium_channel_blocker",
    "diuretic",
    "maoi",
    "nitrate",
    "pde5_inhibitor",
    "ssri",
    "snri",
    "statin",
    "thyroid_hormone",
    "warfarin",
    "anticoagulant",
    "diabetes_medication",
    "other",
}

ALLOWED_CONDITION_TAGS = {
    "hypertension",
    "diabetes",
    "kidney_disease",
    "dyslipidemia",
    "thyroid_disease",
    "heart_disease",
    "mental_health",
    "other",
}

MAX_CONDITION_TAG_LENGTH = 64


class UserMedicationCreate(BaseModel):
    """Create request for a saved medication name."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str = Field(min_length=1, max_length=160)
    normalized_name: str | None = Field(default=None, min_length=1, max_length=160)
    medication_class: str | None = Field(default=None, min_length=1, max_length=80)
    condition_tags: list[str] = Field(default_factory=list, max_length=8)
    is_active: bool = True

    @field_validator("medication_class")
    @classmethod
    def validate_medication_class(cls, value: str | None) -> str | None:
        """Keep class labels structured enough for policy routing."""
        if value is None:
            return None
        normalized = value.casefold().strip()
        if normalized not in ALLOWED_MEDICATION_CLASSES:
            raise ValueError("Unsupported medication_class.")
        return normalized

    @field_validator("condition_tags")
    @classmethod
    def validate_condition_tags(cls, value: list[str]) -> list[str]:
        """Keep condition tags bounded and structured."""
        normalized: list[str] = []
        for tag in value:
            cleaned = tag.casefold().strip()
            if not cleaned or len(cleaned) > MAX_CONDITION_TAG_LENGTH:
                raise ValueError("condition_tags must contain non-empty labels.")
            if cleaned not in ALLOWED_CONDITION_TAGS:
                raise ValueError("Unsupported condition tag.")
            if cleaned not in normalized:
                normalized.append(cleaned)
        return normalized


class UserMedicationUpdate(BaseModel):
    """Update request for a saved medication name."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    normalized_name: str | None = Field(default=None, min_length=1, max_length=160)
    medication_class: str | None = Field(default=None, min_length=1, max_length=80)
    condition_tags: list[str] | None = Field(default=None, max_length=8)
    is_active: bool | None = None

    @field_validator("medication_class")
    @classmethod
    def validate_medication_class(cls, value: str | None) -> str | None:
        """Keep class labels structured enough for policy routing."""
        if value is None:
            return None
        normalized = value.casefold().strip()
        if normalized not in ALLOWED_MEDICATION_CLASSES:
            raise ValueError("Unsupported medication_class.")
        return normalized

    @field_validator("condition_tags")
    @classmethod
    def validate_condition_tags(cls, value: list[str] | None) -> list[str] | None:
        """Keep condition tags bounded and structured."""
        if value is None:
            return None
        return UserMedicationCreate.validate_condition_tags(value)


class UserMedicationResponse(BaseModel):
    """Public saved medication response."""

    id: UUID
    display_name: str
    normalized_name: str | None = None
    medication_class: str | None = None
    condition_tags: list[str] = Field(default_factory=list)
    confirmation_status: str
    is_active: bool
    last_confirmed_at: datetime
    created_at: datetime
    updated_at: datetime


class UserMedicationListResponse(BaseModel):
    """List response for current-user medications."""

    items: list[UserMedicationResponse] = Field(default_factory=list)
