"""Structured supplement OCR parser schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.models.schemas.supplement import (
    SupplementMissingRequiredSection,
    SupplementPreviewEvidenceSpan,
    SupplementPreviewFunctionalClaim,
    SupplementPreviewIntakeMethod,
    SupplementPreviewLabelSection,
    SupplementPreviewPrecaution,
)

SUPPLEMENT_PARSER_OUTPUT_V2: Literal["supplement-parser-output-v2"] = "supplement-parser-output-v2"


class SupplementParserProduct(BaseModel):
    """Product-level facts extracted from supplement OCR text.

    Attributes:
        product_name: Product name candidate exactly supported by the label text.
        manufacturer: Manufacturer candidate exactly supported by the label text.
        serving_size: Serving-size text from the label.
        daily_servings: Daily serving count stated on the label.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    product_name: str | None = Field(default=None, max_length=200)
    manufacturer: str | None = Field(default=None, max_length=160)
    serving_size: str | None = Field(default=None, max_length=120)
    daily_servings: float | None = Field(default=None, ge=0, le=20)


class SupplementParserIngredientCandidate(BaseModel):
    """Ingredient candidate extracted from supplement OCR text.

    Attributes:
        display_name: Ingredient name shown to the user for confirmation.
        original_name: Original ingredient name visible in OCR text, usually the
            English label wording. This is a bounded per-ingredient label, not raw OCR.
        nutrient_code: Always null at the LLM extraction stage; deterministic mapping happens later.
        amount: Ingredient amount per serving when visible.
        unit: Ingredient unit when visible.
        confidence: Extraction confidence from 0.0 to 1.0.
        source: Stable parser source marker. ``ingredient_declaration`` marks a
            name-only candidate mined from the Korean 원재료명 / 원료명 declaration
            list; such candidates carry no trustworthy amount/unit and must be
            confirmed manually.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str = Field(min_length=1, max_length=120)
    original_name: str | None = Field(default=None, min_length=1, max_length=120)
    nutrient_code: Literal[None] = Field(default=None)
    amount: float | None = Field(default=None, ge=0, le=1_000_000)
    unit: str | None = Field(default=None, max_length=40)
    daily_value_percent: float | None = Field(default=None, ge=0, le=10000)
    confidence: float = Field(ge=0, le=1)
    source: Literal[
        "ollama_structured",
        "ocr_pattern_fallback",
        "ingredient_declaration",
    ] = "ollama_structured"


class SupplementStructuredParseResult(BaseModel):
    """Validated structured output returned by the supplement parser.

    Attributes:
        parsed_product: Product-level parsed fields.
        ingredient_candidates: Ingredient candidates that require user confirmation.
        label_sections: Bounded label section summaries for mobile review.
        intake_method: Label-supported intake instruction candidate.
        precautions: Label-supported precaution candidates.
        functional_claims: Label-supported functional claim candidates.
        evidence_spans: Short bounded excerpts supporting preview fields.
        missing_required_sections: Label sections still missing from evidence.
        low_confidence_fields: Field paths that need extra user review.
        warnings: Safe non-medical warnings for the preview UI.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    parsed_product: SupplementParserProduct = Field(default_factory=SupplementParserProduct)
    ingredient_candidates: list[SupplementParserIngredientCandidate] = Field(
        default_factory=list,
        max_length=80,
    )
    label_sections: list[SupplementPreviewLabelSection] = Field(
        default_factory=list,
        max_length=40,
    )
    intake_method: SupplementPreviewIntakeMethod = Field(
        default_factory=SupplementPreviewIntakeMethod
    )
    precautions: list[SupplementPreviewPrecaution] = Field(default_factory=list, max_length=40)
    functional_claims: list[SupplementPreviewFunctionalClaim] = Field(
        default_factory=list,
        max_length=40,
    )
    evidence_spans: list[SupplementPreviewEvidenceSpan] = Field(
        default_factory=list,
        max_length=160,
    )
    missing_required_sections: list[SupplementMissingRequiredSection] = Field(
        default_factory=list,
        max_length=10,
    )
    low_confidence_fields: list[str] = Field(default_factory=list, max_length=80)
    warnings: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("low_confidence_fields", "warnings")
    @classmethod
    def _normalize_string_list(cls, values: list[str]) -> list[str]:
        """Normalize parser-produced string lists and remove duplicates.

        Args:
            values: Candidate strings produced by the parser.

        Returns:
            Trimmed non-empty strings in first-seen order.
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


class SupplementOCRTextParseRequest(BaseModel):
    """Request payload for attaching OCR text to an existing preview.

    Attributes:
        ocr_text: OCR text extracted from a supplement label. The API normalizes,
            hashes, and parses this text without storing it raw.
        ocr_provider: Bounded OCR provider label, such as ``manual`` or ``clova``.
        ocr_confidence: Optional provider-level OCR confidence from 0.0 to 1.0.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    ocr_text: str = Field(min_length=1, max_length=50_000)
    ocr_provider: str = Field(min_length=1, max_length=64)
    ocr_confidence: float | None = Field(default=None, ge=0, le=1)
