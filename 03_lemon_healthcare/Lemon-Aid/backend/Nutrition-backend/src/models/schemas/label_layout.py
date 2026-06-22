"""Pydantic schemas for coordinate-based supplement label layout parsing."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SectionType = Literal[
    "daily_intake",
    "nutrition_function_info",
    "intake_method",
    "precautions",
    "allergen_warning",
    "ingredients",
    "functionality",
    "storage_method",
    "unknown",
]


class LayoutParserOptions(BaseModel):
    """Runtime knobs for deterministic OCR layout grouping.

    Attributes:
        row_y_tolerance_ratio: Multiplier applied to median word height for y-band rows.
        column_gap_ratio: Multiplier applied to median word width for splitting cells.
        min_anchor_overlap_ratio: Reserved threshold for future anchor-box overlap checks.
        max_section_gap_rows: Maximum rows retained in one section before warning.
    """

    model_config = ConfigDict(extra="forbid")

    row_y_tolerance_ratio: float = Field(default=0.60, ge=0.1, le=2.0)
    column_gap_ratio: float = Field(default=1.80, ge=0.5, le=8.0)
    min_anchor_overlap_ratio: float = Field(default=0.30, ge=0.0, le=1.0)
    max_section_gap_rows: int = Field(default=80, ge=1, le=500)


class LabelBox(BaseModel):
    """Bounding box for a parsed label element.

    Attributes:
        page_index: Zero-based OCR page index.
        left: Minimum horizontal coordinate.
        top: Minimum vertical coordinate.
        right: Maximum horizontal coordinate.
        bottom: Maximum vertical coordinate.
    """

    model_config = ConfigDict(extra="forbid")

    page_index: int = Field(ge=0)
    left: float = Field(ge=0)
    top: float = Field(ge=0)
    right: float = Field(ge=0)
    bottom: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_non_empty_box(self) -> Self:
        """Validate the box has positive area.

        Returns:
            Validated box.

        Raises:
            ValueError: If the box has no positive area.
        """
        if self.right <= self.left:
            raise ValueError("right must be greater than left.")
        if self.bottom <= self.top:
            raise ValueError("bottom must be greater than top.")
        return self


class LabelCell(BaseModel):
    """One reconstructed cell in a supplement label section.

    Attributes:
        row_index: Zero-based row index within the section.
        column_index: Zero-based column index within the section.
        text: OCR text assembled from words inside the cell.
        bounding_box: Union bounding box of the cell words.
        confidence: Optional average word confidence from 0.0 to 1.0.
        word_count: Number of OCR words used to build the cell.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    row_index: int = Field(ge=0)
    column_index: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=500)
    bounding_box: LabelBox
    confidence: float | None = Field(default=None, ge=0, le=1)
    word_count: int = Field(ge=1)


class LabelSection(BaseModel):
    """A semantic label section inferred from keyword anchors.

    Attributes:
        section_type: Normalized semantic section type.
        anchor_text: Anchor keyword text that started the section, when present.
        anchor_box: Anchor row or cell bounding box, when present.
        rows: Reconstructed cell rows in visual order.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    section_type: SectionType
    anchor_text: str | None = Field(default=None, max_length=120)
    anchor_box: LabelBox | None = None
    rows: list[list[LabelCell]] = Field(default_factory=list)


class LabelLayout(BaseModel):
    """Coordinate-derived layout for one OCR result.

    Attributes:
        provider: OCR provider label copied from ``OCRResult.provider``.
        page_count: Number of OCR pages inspected.
        sections: Parsed sections with row/cell arrays.
        warnings: Safe deterministic parser warnings.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    provider: str = Field(min_length=1, max_length=64)
    page_count: int = Field(ge=0)
    sections: list[LabelSection] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("warnings")
    @classmethod
    def normalize_warnings(cls, values: list[str]) -> list[str]:
        """Normalize warnings and remove duplicates.

        Args:
            values: Warning strings.

        Returns:
            Trimmed unique warnings in first-seen order.
        """
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            stripped = value.strip()
            if not stripped or stripped in seen:
                continue
            normalized.append(stripped)
            seen.add(stripped)
        return normalized


__all__ = [
    "LabelBox",
    "LabelCell",
    "LabelLayout",
    "LabelSection",
    "LayoutParserOptions",
    "SectionType",
]
