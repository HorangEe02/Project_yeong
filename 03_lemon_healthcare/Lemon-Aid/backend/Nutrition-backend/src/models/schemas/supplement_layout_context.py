"""Bounded supplement label layout context schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SupplementLayoutContextV1(BaseModel):
    """Safe summary of deterministic OCR layout parsing.

    Attributes:
        provider: OCR provider used for the layout pass.
        page_count: Number of OCR pages considered.
        section_count: Number of parsed label sections.
        warnings: Non-sensitive parser warning codes.
        fallback_reason: Safe reason when coordinate layout could not be used.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    provider: str | None = Field(default=None, max_length=80)
    page_count: int = Field(default=0, ge=0)
    section_count: int = Field(default=0, ge=0)
    warnings: list[str] = Field(default_factory=list, max_length=80)
    fallback_reason: str | None = Field(default=None, max_length=120)


__all__ = ["SupplementLayoutContextV1"]
