"""Versioned supplement OCR snapshot schemas.

The snapshot contract stores label-supported extraction candidates only. It must
not contain raw image bytes, raw OCR text, raw provider payloads, or direct
medical recommendations.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.models.schemas.label_layout import LabelSection
from src.models.schemas.supplement_layout_context import SupplementLayoutContextV1
from src.models.schemas.supplement_parser import SUPPLEMENT_PARSER_OUTPUT_V2

SUPPLEMENT_PARSED_SNAPSHOT_V2: Literal["supplement-parsed-snapshot-v2"] = (
    "supplement-parsed-snapshot-v2"
)
SUPPLEMENT_PARSED_SNAPSHOT_V3: Literal["supplement-parsed-snapshot-v3"] = (
    "supplement-parsed-snapshot-v3"
)

OCRSnapshotProvider = Literal[
    "google_vision_document",
    "clova_ocr",
    "paddleocr_local",
    "ollama_vision_assist",
    "manual",
    "intake-only",
    "noop",
    "none",
]
NutrientCodeMatchMethod = Literal["alias_exact", "alias_fuzzy", "manual"]
IngredientSnapshotSource = Literal["ocr_llm_preview", "user_confirmed", "manual"]
IntakeFrequency = Literal["daily", "weekly", "as_needed", "unknown"]
WithFoodFlag = Literal["yes", "no", "unknown"]
PrecautionCategory = Literal[
    "general",
    "pregnancy",
    "medication",
    "disease",
    "allergy",
    "age",
    "unknown",
]
FunctionalClaimType = Literal["label_claim", "functionality", "unknown"]
DomainCorrectionAction = Literal["reported", "applied"]
SnapshotSectionType = Literal[
    "nutrition_info",
    "functional_info",
    "intake_method",
    "precautions",
    "allergen_warning",
    "ingredients",
    "storage_method",
    "unknown",
]
EvidenceSourceType = Literal["ocr_text", "label_layout", "barcode", "manual"]
BarcodeCandidateSource = Literal["client_scan", "foodqr", "mfds", "manual"]
PrecautionSeverity = Literal["label_warning", "label_caution", "unknown"]


def _normalize_unique_strings(values: list[str]) -> list[str]:
    """Normalize a string list while preserving first-seen order.

    Args:
        values: Candidate string values.

    Returns:
        Trimmed non-empty strings with duplicates removed.
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


class SupplementParsedSnapshotSource(BaseModel):
    """Source metadata for a parsed supplement snapshot.

    Attributes:
        analysis_id: Temporary supplement analysis identifier.
        ocr_provider: OCR provider label that produced the selected OCR candidate.
        ocr_confidence: Optional provider-level OCR confidence.
        layout_available: Whether coordinate-derived layout was available.
        raw_image_stored: Always false for the normal preview path.
        raw_ocr_text_stored: Always false for the normal preview path.
        raw_provider_payload_stored: Always false for provider responses.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    analysis_id: UUID | None = None
    ocr_provider: OCRSnapshotProvider
    ocr_confidence: float | None = Field(default=None, ge=0, le=1)
    layout_available: bool = False
    raw_image_stored: Literal[False] = False
    raw_ocr_text_stored: Literal[False] = False
    raw_provider_payload_stored: Literal[False] = False


class SupplementSnapshotProduct(BaseModel):
    """Product facts supported by label OCR or official barcode candidates.

    Attributes:
        product_name: Product name candidate.
        manufacturer: Manufacturer candidate.
        barcode_text: Optional barcode value supplied by the client scanner.
        barcode_format: Optional barcode format label.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    product_name: str | None = Field(default=None, max_length=200)
    manufacturer: str | None = Field(default=None, max_length=160)
    barcode_text: str | None = Field(default=None, max_length=256)
    barcode_format: str | None = Field(default=None, max_length=40)


class SupplementSnapshotServing(BaseModel):
    """Serving facts extracted from the label.

    Attributes:
        serving_size_text: Label-supported serving text.
        serving_amount: Numeric serving amount when parseable.
        serving_unit: Serving unit when parseable.
        daily_servings: Daily serving count stated on the label.
        evidence_refs: Layout or text evidence references for this serving.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    serving_size_text: str | None = Field(default=None, max_length=120)
    serving_amount: float | None = Field(default=None, ge=0, le=1_000_000)
    serving_unit: str | None = Field(default=None, max_length=40)
    daily_servings: float | None = Field(default=None, ge=0, le=20)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("evidence_refs")
    @classmethod
    def normalize_evidence_refs(cls, values: list[str]) -> list[str]:
        """Normalize evidence references.

        Args:
            values: Evidence reference strings.

        Returns:
            Trimmed unique evidence references.
        """
        return _normalize_unique_strings(values)


class NutrientCodeCandidate(BaseModel):
    """Deterministic nutrient-code match candidate.

    Attributes:
        nutrient_code: Internal nutrient code candidate.
        match_method: Deterministic matching method.
        confidence: Candidate match confidence.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nutrient_code: str = Field(min_length=1, max_length=80)
    match_method: NutrientCodeMatchMethod
    confidence: float = Field(ge=0, le=1)


class SupplementSnapshotIngredientCandidate(BaseModel):
    """Ingredient candidate requiring user confirmation.

    Attributes:
        display_name: Ingredient name shown to the user.
        original_name: Original visible ingredient name from OCR text.
        normalized_name: Normalized ingredient name for matching.
        nutrient_code_candidates: Deterministic nutrient-code candidates.
        amount: Ingredient amount per serving.
        unit: Ingredient unit.
        daily_amount: Amount multiplied by daily servings when available.
        confidence: Extraction confidence.
        source: Candidate source marker.
        evidence_refs: Layout or text evidence references.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str = Field(min_length=1, max_length=120)
    original_name: str | None = Field(default=None, min_length=1, max_length=120)
    normalized_name: str | None = Field(default=None, max_length=120)
    nutrient_code_candidates: list[NutrientCodeCandidate] = Field(
        default_factory=list,
        max_length=10,
    )
    amount: float | None = Field(default=None, ge=0, le=1_000_000)
    unit: str | None = Field(default=None, max_length=40)
    daily_amount: float | None = Field(default=None, ge=0, le=20_000_000)
    confidence: float = Field(ge=0, le=1)
    source: IngredientSnapshotSource
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("evidence_refs")
    @classmethod
    def normalize_evidence_refs(cls, values: list[str]) -> list[str]:
        """Normalize evidence references.

        Args:
            values: Evidence reference strings.

        Returns:
            Trimmed unique evidence references.
        """
        return _normalize_unique_strings(values)


class StructuredIntakeMethod(BaseModel):
    """Structured intake-method candidate derived only from label text.

    Attributes:
        frequency: Intake frequency candidate.
        time_of_day: Optional label-supported time-of-day values.
        with_food: Whether the label mentions taking with food.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    frequency: IntakeFrequency = "unknown"
    time_of_day: list[str] = Field(default_factory=list, max_length=8)
    with_food: WithFoodFlag = "unknown"

    @field_validator("time_of_day")
    @classmethod
    def normalize_time_of_day(cls, values: list[str]) -> list[str]:
        """Normalize time-of-day labels.

        Args:
            values: Candidate time labels.

        Returns:
            Trimmed unique time labels.
        """
        return _normalize_unique_strings(values)


class SupplementSnapshotIntakeMethod(BaseModel):
    """Label-supported intake method candidate.

    Attributes:
        text: Intake instruction text supported by the label.
        structured: Conservative structured candidate.
        evidence_refs: Layout or text evidence references.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str | None = Field(default=None, max_length=500)
    structured: StructuredIntakeMethod = Field(default_factory=StructuredIntakeMethod)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("evidence_refs")
    @classmethod
    def normalize_evidence_refs(cls, values: list[str]) -> list[str]:
        """Normalize evidence references.

        Args:
            values: Evidence reference strings.

        Returns:
            Trimmed unique evidence references.
        """
        return _normalize_unique_strings(values)


class SupplementSnapshotPrecaution(BaseModel):
    """Label-supported precaution candidate.

    Attributes:
        text: Precaution text from the label.
        category: Conservative precaution category.
        evidence_refs: Layout or text evidence references.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(min_length=1, max_length=500)
    category: PrecautionCategory = "unknown"
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("evidence_refs")
    @classmethod
    def normalize_evidence_refs(cls, values: list[str]) -> list[str]:
        """Normalize evidence references.

        Args:
            values: Evidence reference strings.

        Returns:
            Trimmed unique evidence references.
        """
        return _normalize_unique_strings(values)


class SupplementSnapshotFunctionalClaim(BaseModel):
    """Label-supported functional claim candidate.

    Attributes:
        text: Functional claim text from the label.
        claim_type: Conservative claim category.
        evidence_refs: Layout or text evidence references.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(min_length=1, max_length=500)
    claim_type: FunctionalClaimType = "unknown"
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("evidence_refs")
    @classmethod
    def normalize_evidence_refs(cls, values: list[str]) -> list[str]:
        """Normalize evidence references.

        Args:
            values: Evidence reference strings.

        Returns:
            Trimmed unique evidence references.
        """
        return _normalize_unique_strings(values)


class SupplementParsedSnapshotV2(BaseModel):
    """Versioned parsed supplement-label preview snapshot.

    Attributes:
        schema_version: Fixed schema version marker.
        requires_user_confirmation: Always true before a user supplement is registered.
        source: OCR and storage metadata.
        product: Product-level candidates.
        serving: Serving candidates.
        label_sections: Optional coordinate-derived label sections.
        ingredient_candidates: Ingredient candidates requiring user review.
        intake_method: Label-supported intake method candidate.
        precautions: Label-supported precaution candidates.
        functional_claims: Label-supported functional claim candidates.
        low_confidence_fields: Field paths that need extra user review.
        warnings: Safe preview warnings.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    schema_version: Literal["supplement-parsed-snapshot-v2"] = SUPPLEMENT_PARSED_SNAPSHOT_V2
    requires_user_confirmation: Literal[True] = True
    source: SupplementParsedSnapshotSource
    product: SupplementSnapshotProduct = Field(default_factory=SupplementSnapshotProduct)
    serving: SupplementSnapshotServing = Field(default_factory=SupplementSnapshotServing)
    label_sections: list[LabelSection] = Field(default_factory=list, max_length=40)
    ingredient_candidates: list[SupplementSnapshotIngredientCandidate] = Field(
        default_factory=list,
        max_length=80,
    )
    intake_method: SupplementSnapshotIntakeMethod = Field(
        default_factory=SupplementSnapshotIntakeMethod
    )
    precautions: list[SupplementSnapshotPrecaution] = Field(default_factory=list, max_length=40)
    functional_claims: list[SupplementSnapshotFunctionalClaim] = Field(
        default_factory=list,
        max_length=40,
    )
    low_confidence_fields: list[str] = Field(default_factory=list, max_length=80)
    warnings: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("low_confidence_fields", "warnings")
    @classmethod
    def normalize_string_lists(cls, values: list[str]) -> list[str]:
        """Normalize field path and warning lists.

        Args:
            values: Candidate field paths or warning strings.

        Returns:
            Trimmed unique strings.
        """
        return _normalize_unique_strings(values)


class SupplementParsedSnapshotSourceV3(BaseModel):
    """Source metadata for a V3 parsed supplement snapshot.

    Attributes:
        analysis_id: Temporary supplement analysis identifier.
        parser_schema_version: Parser output schema version used before enrichment.
        ocr_provider: OCR provider label that produced the selected OCR candidate.
        ocr_confidence: Optional provider-level OCR confidence.
        layout_available: Whether coordinate-derived layout was available.
        raw_image_stored: Always false for the normal preview path.
        raw_ocr_text_stored: Always false for the normal preview path.
        raw_provider_payload_stored: Always false for provider responses.
        raw_model_response_stored: Always false for local LLM responses.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    analysis_id: UUID | None = None
    parser_schema_version: Literal["supplement-parser-output-v2"] = SUPPLEMENT_PARSER_OUTPUT_V2
    ocr_provider: OCRSnapshotProvider
    ocr_confidence: float | None = Field(default=None, ge=0, le=1)
    layout_available: bool = False
    raw_image_stored: Literal[False] = False
    raw_ocr_text_stored: Literal[False] = False
    raw_provider_payload_stored: Literal[False] = False
    raw_model_response_stored: Literal[False] = False


class SupplementSnapshotBarcodeCandidate(BaseModel):
    """Review-only barcode candidate attached to a parsed product.

    Attributes:
        barcode_text: Barcode value supplied by a scanner or official source.
        barcode_format: Barcode format label.
        source: Candidate source marker.
        confidence: Candidate confidence or deterministic match score.
        evidence_refs: Evidence span ids supporting this candidate.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    barcode_text: str = Field(min_length=1, max_length=256)
    barcode_format: str | None = Field(default=None, max_length=40)
    source: BarcodeCandidateSource
    confidence: float = Field(ge=0, le=1)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("evidence_refs")
    @classmethod
    def normalize_evidence_refs(cls, values: list[str]) -> list[str]:
        """Normalize evidence references.

        Args:
            values: Evidence span ids.

        Returns:
            Trimmed unique evidence span ids.
        """
        return _normalize_unique_strings(values)


class SupplementSnapshotProductV3(BaseModel):
    """V3 product facts supported by label OCR or barcode candidates.

    Attributes:
        product_name: Product name candidate.
        manufacturer: Manufacturer candidate.
        barcode_candidates: Review-only barcode candidates.
        evidence_refs: Evidence span ids supporting product facts.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    product_name: str | None = Field(default=None, max_length=200)
    manufacturer: str | None = Field(default=None, max_length=160)
    barcode_candidates: list[SupplementSnapshotBarcodeCandidate] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("evidence_refs")
    @classmethod
    def normalize_evidence_refs(cls, values: list[str]) -> list[str]:
        """Normalize evidence references.

        Args:
            values: Evidence span ids.

        Returns:
            Trimmed unique evidence span ids.
        """
        return _normalize_unique_strings(values)


class SupplementSnapshotServingV3(BaseModel):
    """V3 serving facts extracted from the label.

    Attributes:
        serving_size_text: Label-supported serving text.
        serving_amount: Numeric serving amount when parseable.
        serving_unit: Serving unit when parseable.
        daily_servings: Daily serving count stated on the label.
        total_amount: Label-stated total amount, not inferred.
        total_unit: Label-stated total amount unit.
        evidence_refs: Evidence span ids supporting serving facts.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    serving_size_text: str | None = Field(default=None, max_length=120)
    serving_amount: float | None = Field(default=None, ge=0, le=1_000_000)
    serving_unit: str | None = Field(default=None, max_length=40)
    daily_servings: float | None = Field(default=None, ge=0, le=20)
    total_amount: float | None = Field(default=None, ge=0, le=100_000_000)
    total_unit: str | None = Field(default=None, max_length=40)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("evidence_refs")
    @classmethod
    def normalize_evidence_refs(cls, values: list[str]) -> list[str]:
        """Normalize evidence references.

        Args:
            values: Evidence span ids.

        Returns:
            Trimmed unique evidence span ids.
        """
        return _normalize_unique_strings(values)


class SupplementSnapshotNutrientCodeCandidate(BaseModel):
    """Deterministic nutrient-code match candidate for V3 ingredients.

    Attributes:
        nutrient_code: Internal nutrient code candidate.
        display_name: Optional nutrient display name from the matcher catalog.
        source_catalog: Deterministic catalog used by the matcher.
        match_method: Deterministic matching method.
        matched_alias: Alias that matched the ingredient name.
        confidence: Candidate match confidence.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nutrient_code: str = Field(min_length=1, max_length=80)
    display_name: str | None = Field(default=None, max_length=120)
    source_catalog: str = Field(default="internal_nutrient_alias", max_length=80)
    match_method: NutrientCodeMatchMethod
    matched_alias: str | None = Field(default=None, max_length=120)
    confidence: float = Field(ge=0, le=1)


class SupplementSnapshotDomainCorrectionAudit(BaseModel):
    """Audit metadata for parser/domain correction suggestions or applications.

    Attributes:
        rule_id: Reviewed domain correction rule identifier.
        correction_type: Correction category.
        field_path: Field path affected by the rule.
        action: Whether the rule was only reported or applied.
        ingredient_index: Optional zero-based ingredient index.
        source: Stable audit source marker.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    rule_id: str = Field(min_length=1, max_length=160)
    correction_type: str = Field(min_length=1, max_length=80)
    field_path: str = Field(min_length=1, max_length=180)
    action: DomainCorrectionAction
    ingredient_index: int | None = Field(default=None, ge=0, le=80)
    source: Literal["parser_domain_correction"] = "parser_domain_correction"


class SupplementSnapshotIngredientV3(BaseModel):
    """V3 ingredient candidate requiring user confirmation.

    Attributes:
        display_name: Ingredient name shown to the user.
        original_name: Original visible ingredient name from OCR text.
        normalized_name: Normalized ingredient name for matching.
        amount: Ingredient amount per serving.
        unit: Ingredient unit.
        amount_text: Original amount text when numeric parsing is uncertain.
        daily_amount: Amount multiplied by daily servings when available.
        daily_unit: Daily amount unit.
        nutrient_code_candidates: Deterministic nutrient-code candidates.
        confidence: Extraction confidence.
        source: Candidate source marker.
        evidence_refs: Evidence span ids supporting this ingredient.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str = Field(min_length=1, max_length=120)
    original_name: str | None = Field(default=None, min_length=1, max_length=120)
    normalized_name: str | None = Field(default=None, max_length=120)
    amount: float | None = Field(default=None, ge=0, le=1_000_000)
    unit: str | None = Field(default=None, max_length=40)
    amount_text: str | None = Field(default=None, max_length=120)
    daily_amount: float | None = Field(default=None, ge=0, le=20_000_000)
    daily_unit: str | None = Field(default=None, max_length=40)
    nutrient_code_candidates: list[SupplementSnapshotNutrientCodeCandidate] = Field(
        default_factory=list,
        max_length=10,
    )
    confidence: float = Field(ge=0, le=1)
    source: IngredientSnapshotSource
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("evidence_refs")
    @classmethod
    def normalize_evidence_refs(cls, values: list[str]) -> list[str]:
        """Normalize evidence references.

        Args:
            values: Evidence span ids.

        Returns:
            Trimmed unique evidence span ids.
        """
        return _normalize_unique_strings(values)


class StructuredIntakeMethodV3(BaseModel):
    """V3 structured intake-method candidate derived only from label text.

    Attributes:
        frequency: Intake frequency candidate.
        times_per_day: Parsed times per day when label-stated.
        amount_per_time: Parsed amount per intake when label-stated.
        amount_unit: Parsed intake amount unit.
        time_of_day: Optional label-supported time-of-day values.
        with_food: Whether the label mentions taking with food.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    frequency: IntakeFrequency = "unknown"
    times_per_day: float | None = Field(default=None, ge=0, le=20)
    amount_per_time: float | None = Field(default=None, ge=0, le=1_000_000)
    amount_unit: str | None = Field(default=None, max_length=40)
    time_of_day: list[str] = Field(default_factory=list, max_length=8)
    with_food: WithFoodFlag = "unknown"

    @field_validator("time_of_day")
    @classmethod
    def normalize_time_of_day(cls, values: list[str]) -> list[str]:
        """Normalize time-of-day labels.

        Args:
            values: Candidate time labels.

        Returns:
            Trimmed unique time labels.
        """
        return _normalize_unique_strings(values)


class SupplementSnapshotIntakeMethodV3(BaseModel):
    """V3 label-supported intake method candidate.

    Attributes:
        text: Intake instruction text supported by the label.
        structured: Conservative structured candidate.
        evidence_refs: Evidence span ids supporting intake facts.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str | None = Field(default=None, max_length=500)
    structured: StructuredIntakeMethodV3 = Field(default_factory=StructuredIntakeMethodV3)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("evidence_refs")
    @classmethod
    def normalize_evidence_refs(cls, values: list[str]) -> list[str]:
        """Normalize evidence references.

        Args:
            values: Evidence span ids.

        Returns:
            Trimmed unique evidence span ids.
        """
        return _normalize_unique_strings(values)


class SupplementSnapshotPrecautionV3(BaseModel):
    """V3 label-supported precaution candidate.

    Attributes:
        text: Precaution text from the label.
        category: Conservative precaution category.
        severity: Label warning severity marker.
        evidence_refs: Evidence span ids supporting this precaution.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(min_length=1, max_length=500)
    category: PrecautionCategory = "unknown"
    severity: PrecautionSeverity = "unknown"
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("evidence_refs")
    @classmethod
    def normalize_evidence_refs(cls, values: list[str]) -> list[str]:
        """Normalize evidence references.

        Args:
            values: Evidence span ids.

        Returns:
            Trimmed unique evidence span ids.
        """
        return _normalize_unique_strings(values)


class SupplementSnapshotFunctionalClaimV3(BaseModel):
    """V3 label-supported functional claim candidate.

    Attributes:
        text: Functional claim text from the label.
        claim_type: Conservative claim category.
        evidence_refs: Evidence span ids supporting this claim.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(min_length=1, max_length=500)
    claim_type: FunctionalClaimType = "unknown"
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("evidence_refs")
    @classmethod
    def normalize_evidence_refs(cls, values: list[str]) -> list[str]:
        """Normalize evidence references.

        Args:
            values: Evidence span ids.

        Returns:
            Trimmed unique evidence span ids.
        """
        return _normalize_unique_strings(values)


class SupplementSnapshotLabelSectionV3(BaseModel):
    """V3 normalized label section candidate.

    Attributes:
        section_type: Normalized Phase 1 section type.
        heading_text: Section heading or anchor text.
        evidence_refs: Evidence span ids supporting this section.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    section_type: SnapshotSectionType
    heading_text: str | None = Field(default=None, max_length=120)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("evidence_refs")
    @classmethod
    def normalize_evidence_refs(cls, values: list[str]) -> list[str]:
        """Normalize evidence references.

        Args:
            values: Evidence span ids.

        Returns:
            Trimmed unique evidence span ids.
        """
        return _normalize_unique_strings(values)


class SupplementSnapshotEvidenceSpan(BaseModel):
    """Short redacted evidence excerpt supporting a V3 snapshot field.

    Attributes:
        span_id: Stable identifier referenced by snapshot fields.
        source_type: Evidence source category.
        section_type: Normalized label section category.
        text_excerpt: Short label-supported excerpt, never the full OCR text.
        page_index: Optional zero-based OCR page index.
        char_start: Optional start character offset in normalized OCR text.
        char_end: Optional end character offset in normalized OCR text.
        cell_ref: Optional layout cell reference.
        confidence: Optional OCR/layout confidence for this span.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    span_id: str = Field(min_length=1, max_length=120)
    source_type: EvidenceSourceType
    section_type: SnapshotSectionType = "unknown"
    text_excerpt: str = Field(min_length=1, max_length=240)
    page_index: int | None = Field(default=None, ge=0)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)
    cell_ref: str | None = Field(default=None, max_length=160)
    confidence: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_offsets(self) -> Self:
        """Validate optional character offsets.

        Returns:
            Validated evidence span.

        Raises:
            ValueError: If the end offset is not greater than the start offset.
        """
        if (
            self.char_start is not None
            and self.char_end is not None
            and self.char_end <= self.char_start
        ):
            raise ValueError("char_end must be greater than char_start.")
        return self


class SupplementParsedSnapshotV3(BaseModel):
    """Versioned parsed supplement-label preview snapshot for Phase 1.

    Attributes:
        schema_version: Fixed V3 schema version marker.
        requires_user_confirmation: Always true before registration.
        source: OCR/parser/storage metadata.
        layout_context: Bounded deterministic layout summary, when available.
        product: Product-level candidates.
        serving: Serving candidates.
        ingredients: Ingredient candidates requiring user review.
        label_sections: Normalized label section candidates.
        intake_method: Label-supported intake method candidate.
        precautions: Label-supported precaution candidates.
        functional_claims: Label-supported functional claim candidates.
        evidence_spans: Short redacted evidence snippets.
        domain_correction_audit: Rule ids and field paths for parser/domain corrections.
        low_confidence_fields: Field paths that need extra user review.
        warnings: Safe preview warnings.
        chronic_disease_indications: Chronic-disease conditions the labeled supplement
            targets (e.g. ``["cardiovascular", "dyslipidemia"]``). Empty list by default
            for backward compatibility. Drives B-persona accuracy metrics.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    schema_version: Literal["supplement-parsed-snapshot-v3"] = SUPPLEMENT_PARSED_SNAPSHOT_V3
    requires_user_confirmation: Literal[True] = True
    source: SupplementParsedSnapshotSourceV3
    layout_context: SupplementLayoutContextV1 | None = None
    product: SupplementSnapshotProductV3 = Field(default_factory=SupplementSnapshotProductV3)
    serving: SupplementSnapshotServingV3 = Field(default_factory=SupplementSnapshotServingV3)
    ingredients: list[SupplementSnapshotIngredientV3] = Field(default_factory=list, max_length=80)
    label_sections: list[SupplementSnapshotLabelSectionV3] = Field(
        default_factory=list,
        max_length=40,
    )
    intake_method: SupplementSnapshotIntakeMethodV3 = Field(
        default_factory=SupplementSnapshotIntakeMethodV3
    )
    precautions: list[SupplementSnapshotPrecautionV3] = Field(default_factory=list, max_length=40)
    functional_claims: list[SupplementSnapshotFunctionalClaimV3] = Field(
        default_factory=list,
        max_length=40,
    )
    evidence_spans: list[SupplementSnapshotEvidenceSpan] = Field(
        default_factory=list,
        max_length=160,
    )
    domain_correction_audit: list[SupplementSnapshotDomainCorrectionAudit] = Field(
        default_factory=list,
        max_length=120,
    )
    low_confidence_fields: list[str] = Field(default_factory=list, max_length=80)
    warnings: list[str] = Field(default_factory=list, max_length=50)
    chronic_disease_indications: list[
        Literal[
            "diabetes",
            "hypertension",
            "dyslipidemia",
            "cardiovascular",
            "osteoporosis",
            "chronic_kidney_disease",
            "liver_disease",
            "cognitive_decline",
        ]
    ] = Field(default_factory=list, max_length=8)

    @field_validator("low_confidence_fields", "warnings")
    @classmethod
    def normalize_string_lists(cls, values: list[str]) -> list[str]:
        """Normalize field path and warning lists.

        Args:
            values: Candidate field paths or warning strings.

        Returns:
            Trimmed unique strings.
        """
        return _normalize_unique_strings(values)

    @model_validator(mode="after")
    def validate_evidence_refs(self) -> Self:
        """Validate non-empty evidence references point to known spans.

        Returns:
            Validated V3 snapshot.

        Raises:
            ValueError: If any evidence reference is dangling.
        """
        span_ids = {span.span_id for span in self.evidence_spans}
        refs: list[str] = []
        refs.extend(self.product.evidence_refs)
        refs.extend(self.serving.evidence_refs)
        refs.extend(self.intake_method.evidence_refs)
        for barcode in self.product.barcode_candidates:
            refs.extend(barcode.evidence_refs)
        for ingredient in self.ingredients:
            refs.extend(ingredient.evidence_refs)
        for section in self.label_sections:
            refs.extend(section.evidence_refs)
        for precaution in self.precautions:
            refs.extend(precaution.evidence_refs)
        for claim in self.functional_claims:
            refs.extend(claim.evidence_refs)
        missing = sorted({ref for ref in refs if ref not in span_ids})
        if missing:
            raise ValueError(f"Unknown evidence_refs: {missing}")
        return self


def parse_supplement_snapshot(raw: Mapping[str, Any]) -> SupplementParsedSnapshotV3:
    """Parse a V3 or legacy parsed supplement snapshot into a V3 view.

    Args:
        raw: Persisted parsed snapshot mapping.

    Returns:
        V3 parsed supplement snapshot.
    """
    schema_version = raw.get("schema_version")
    if schema_version == SUPPLEMENT_PARSED_SNAPSHOT_V3:
        return SupplementParsedSnapshotV3.model_validate(raw)
    if schema_version == SUPPLEMENT_PARSED_SNAPSHOT_V2:
        return _upcast_v2_snapshot(raw)
    return upcast_legacy_parsed_snapshot(raw)


def upcast_legacy_parsed_snapshot(raw: Mapping[str, Any]) -> SupplementParsedSnapshotV3:
    """Convert the current legacy runtime snapshot shape into V3.

    Args:
        raw: Legacy parsed snapshot mapping.

    Returns:
        V3 parsed supplement snapshot.
    """
    parsed_product = _mapping_or_empty(raw.get("parsed_product"))
    parser_metadata = _mapping_or_empty(raw.get("parser_metadata"))
    provider = _coerce_ocr_provider(parser_metadata.get("input_provider"))
    if parser_metadata.get("raw_ocr_text_stored") is True:
        raise ValueError("Legacy snapshot cannot store raw OCR text.")
    if parser_metadata.get("raw_model_response_stored") is True:
        raise ValueError("Legacy snapshot cannot store raw model responses.")
    product = SupplementSnapshotProductV3(
        product_name=_string_or_none(parsed_product.get("product_name")),
        manufacturer=_string_or_none(parsed_product.get("manufacturer")),
    )
    serving = SupplementSnapshotServingV3(
        serving_size_text=_string_or_none(parsed_product.get("serving_size")),
        daily_servings=_float_or_none(parsed_product.get("daily_servings")),
    )
    ingredients = [
        SupplementSnapshotIngredientV3(
            display_name=str(item["display_name"]),
            original_name=_string_or_none(item.get("original_name")),
            amount=_float_or_none(item.get("amount")),
            unit=_string_or_none(item.get("unit")),
            confidence=_float_or_none(item.get("confidence")) or 0.0,
            source="ocr_llm_preview",
        )
        for item in _mapping_items(raw.get("ingredient_candidates"))
        if isinstance(item.get("display_name"), str) and item.get("display_name", "").strip()
    ]
    return SupplementParsedSnapshotV3(
        source=SupplementParsedSnapshotSourceV3(
            ocr_provider=provider,
        ),
        product=product,
        serving=serving,
        ingredients=ingredients,
        low_confidence_fields=list(_string_items(raw.get("low_confidence_fields"))),
        warnings=list(_string_items(raw.get("warnings"))),
    )


def _upcast_v2_snapshot(raw: Mapping[str, Any]) -> SupplementParsedSnapshotV3:
    """Convert a V2 parsed supplement snapshot into V3.

    Args:
        raw: V2 parsed snapshot mapping.

    Returns:
        V3 parsed supplement snapshot.
    """
    v2 = SupplementParsedSnapshotV2.model_validate(raw)
    evidence_refs = _collect_v2_evidence_refs(v2)
    ingredients = [
        SupplementSnapshotIngredientV3(
            display_name=item.display_name,
            original_name=item.original_name,
            normalized_name=item.normalized_name,
            amount=item.amount,
            unit=item.unit,
            daily_amount=item.daily_amount,
            daily_unit=item.unit,
            nutrient_code_candidates=[
                SupplementSnapshotNutrientCodeCandidate.model_validate(
                    candidate.model_dump(exclude_none=True)
                )
                for candidate in item.nutrient_code_candidates
            ],
            confidence=item.confidence,
            source=item.source,
            evidence_refs=item.evidence_refs,
        )
        for item in v2.ingredient_candidates
    ]
    return SupplementParsedSnapshotV3(
        source=SupplementParsedSnapshotSourceV3(
            analysis_id=v2.source.analysis_id,
            ocr_provider=v2.source.ocr_provider,
            ocr_confidence=v2.source.ocr_confidence,
            layout_available=v2.source.layout_available,
            raw_image_stored=v2.source.raw_image_stored,
            raw_ocr_text_stored=v2.source.raw_ocr_text_stored,
            raw_provider_payload_stored=v2.source.raw_provider_payload_stored,
        ),
        product=SupplementSnapshotProductV3(
            product_name=v2.product.product_name,
            manufacturer=v2.product.manufacturer,
            barcode_candidates=(
                [
                    SupplementSnapshotBarcodeCandidate(
                        barcode_text=v2.product.barcode_text,
                        barcode_format=v2.product.barcode_format,
                        source="manual",
                        confidence=1.0,
                    )
                ]
                if v2.product.barcode_text
                else []
            ),
        ),
        serving=SupplementSnapshotServingV3(
            serving_size_text=v2.serving.serving_size_text,
            serving_amount=v2.serving.serving_amount,
            serving_unit=v2.serving.serving_unit,
            daily_servings=v2.serving.daily_servings,
            evidence_refs=v2.serving.evidence_refs,
        ),
        ingredients=ingredients,
        label_sections=[
            SupplementSnapshotLabelSectionV3(
                section_type=_map_v2_section_type(section.section_type),
                heading_text=section.anchor_text,
            )
            for section in v2.label_sections
        ],
        intake_method=SupplementSnapshotIntakeMethodV3(
            text=v2.intake_method.text,
            structured=StructuredIntakeMethodV3(
                frequency=v2.intake_method.structured.frequency,
                time_of_day=v2.intake_method.structured.time_of_day,
                with_food=v2.intake_method.structured.with_food,
            ),
            evidence_refs=v2.intake_method.evidence_refs,
        ),
        precautions=[
            SupplementSnapshotPrecautionV3(
                text=item.text,
                category=item.category,
                evidence_refs=item.evidence_refs,
            )
            for item in v2.precautions
        ],
        functional_claims=[
            SupplementSnapshotFunctionalClaimV3(
                text=item.text,
                claim_type=item.claim_type,
                evidence_refs=item.evidence_refs,
            )
            for item in v2.functional_claims
        ],
        evidence_spans=_evidence_spans_from_legacy_refs(evidence_refs),
        low_confidence_fields=v2.low_confidence_fields,
        warnings=v2.warnings,
    )


def _collect_v2_evidence_refs(snapshot: SupplementParsedSnapshotV2) -> list[str]:
    """Collect evidence refs from a V2 snapshot.

    Args:
        snapshot: V2 parsed snapshot.

    Returns:
        Trimmed unique evidence references.
    """
    refs: list[str] = []
    refs.extend(snapshot.serving.evidence_refs)
    refs.extend(snapshot.intake_method.evidence_refs)
    for ingredient in snapshot.ingredient_candidates:
        refs.extend(ingredient.evidence_refs)
    for precaution in snapshot.precautions:
        refs.extend(precaution.evidence_refs)
    for claim in snapshot.functional_claims:
        refs.extend(claim.evidence_refs)
    return _normalize_unique_strings(refs)


def _evidence_spans_from_legacy_refs(refs: list[str]) -> list[SupplementSnapshotEvidenceSpan]:
    """Create bounded evidence spans for legacy ref-only snapshots.

    Args:
        refs: Legacy evidence references.

    Returns:
        Evidence spans keyed by the legacy references.
    """
    return [
        SupplementSnapshotEvidenceSpan(
            span_id=ref,
            source_type="label_layout",
            section_type=_section_type_from_legacy_ref(ref),
            text_excerpt=ref[:240],
        )
        for ref in refs
    ]


def _section_type_from_legacy_ref(ref: str) -> SnapshotSectionType:
    """Infer a Phase 1 section type from a legacy evidence ref.

    Args:
        ref: Legacy evidence reference.

    Returns:
        Phase 1 section type.
    """
    section_markers: tuple[tuple[tuple[str, ...], SnapshotSectionType], ...] = (
        (("nutrition_function_info",), "nutrition_info"),
        (("functionality",), "functional_info"),
        (("intake_method",), "intake_method"),
        (("allergen", "allergy"), "allergen_warning"),
        (("precautions",), "precautions"),
        (("ingredients",), "ingredients"),
    )
    for markers, section_type in section_markers:
        if any(marker in ref for marker in markers):
            return section_type
    return "unknown"


def _map_v2_section_type(section_type: str) -> SnapshotSectionType:
    """Map old layout section categories into Phase 1 section categories.

    Args:
        section_type: V2 layout section type.

    Returns:
        Phase 1 normalized section type.
    """
    if section_type == "nutrition_function_info":
        return "nutrition_info"
    if section_type == "functionality":
        return "functional_info"
    if section_type == "daily_intake":
        return "intake_method"
    if section_type in {"intake_method", "precautions", "allergen_warning", "ingredients"}:
        return section_type  # type: ignore[return-value]
    return "unknown"


def _coerce_ocr_provider(value: object) -> OCRSnapshotProvider:
    """Coerce legacy provider metadata into the bounded V3 provider enum.

    Args:
        value: Legacy provider metadata.

    Returns:
        Bounded OCR provider label.
    """
    if not isinstance(value, str):
        return "none"
    normalized = value.strip()
    allowed = {
        "google_vision_document",
        "clova_ocr",
        "paddleocr_local",
        "ollama_vision_assist",
        "manual",
        "intake-only",
        "noop",
        "none",
    }
    if normalized in allowed:
        return normalized  # type: ignore[return-value]
    if normalized.startswith("manual"):
        return "manual"
    return "none"


def _mapping_or_empty(value: object) -> Mapping[str, Any]:
    """Return a mapping value or an empty mapping.

    Args:
        value: Candidate mapping.

    Returns:
        Mapping or empty mapping.
    """
    if isinstance(value, Mapping):
        return value
    return {}


def _mapping_items(value: object) -> list[Mapping[str, Any]]:
    """Return mapping items from a candidate list.

    Args:
        value: Candidate list.

    Returns:
        Mapping items only.
    """
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _string_items(value: object) -> list[str]:
    """Return string items from a candidate list.

    Args:
        value: Candidate list.

    Returns:
        Trimmed unique string values.
    """
    if not isinstance(value, list):
        return []
    return _normalize_unique_strings([item for item in value if isinstance(item, str)])


def _string_or_none(value: object) -> str | None:
    """Return a trimmed string or None.

    Args:
        value: Candidate value.

    Returns:
        Trimmed string or None.
    """
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _float_or_none(value: object) -> float | None:
    """Return a float value or None.

    Args:
        value: Candidate value.

    Returns:
        Float value or None.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


__all__ = [
    "SUPPLEMENT_PARSED_SNAPSHOT_V2",
    "SUPPLEMENT_PARSED_SNAPSHOT_V3",
    "BarcodeCandidateSource",
    "EvidenceSourceType",
    "FunctionalClaimType",
    "IngredientSnapshotSource",
    "IntakeFrequency",
    "NutrientCodeCandidate",
    "NutrientCodeMatchMethod",
    "OCRSnapshotProvider",
    "PrecautionCategory",
    "PrecautionSeverity",
    "SnapshotSectionType",
    "StructuredIntakeMethod",
    "StructuredIntakeMethodV3",
    "SupplementParsedSnapshotSource",
    "SupplementParsedSnapshotSourceV3",
    "SupplementParsedSnapshotV2",
    "SupplementParsedSnapshotV3",
    "SupplementSnapshotBarcodeCandidate",
    "SupplementSnapshotDomainCorrectionAudit",
    "SupplementSnapshotEvidenceSpan",
    "SupplementSnapshotFunctionalClaim",
    "SupplementSnapshotFunctionalClaimV3",
    "SupplementSnapshotIngredientCandidate",
    "SupplementSnapshotIngredientV3",
    "SupplementSnapshotIntakeMethod",
    "SupplementSnapshotIntakeMethodV3",
    "SupplementSnapshotLabelSectionV3",
    "SupplementSnapshotNutrientCodeCandidate",
    "SupplementSnapshotPrecaution",
    "SupplementSnapshotPrecautionV3",
    "SupplementSnapshotProduct",
    "SupplementSnapshotProductV3",
    "SupplementSnapshotServing",
    "SupplementSnapshotServingV3",
    "WithFoodFlag",
    "parse_supplement_snapshot",
    "upcast_legacy_parsed_snapshot",
]
