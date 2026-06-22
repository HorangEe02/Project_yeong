"""Meal image analysis API schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.models.schemas.taxonomy import FoodCatalogItemReference


class MealType(StrEnum):
    """Supported user meal buckets.

    Attributes:
        BREAKFAST: Morning meal.
        LUNCH: Midday meal.
        DINNER: Evening meal.
        SNACK: Snack or small meal.
        UNKNOWN: User has not classified the meal yet.
    """

    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"
    UNKNOWN = "unknown"


class MealAnalysisStatus(StrEnum):
    """Food image analysis preview states.

    Attributes:
        REQUIRES_CONFIRMATION: Preview must be reviewed or manually completed.
        CONFIRMED: Preview was confirmed into a user meal record.
        FAILED: Preview failed before confirmation.
    """

    REQUIRES_CONFIRMATION = "requires_confirmation"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class MealFoodCandidate(BaseModel):
    """Review-only food candidate shown to the user.

    Attributes:
        display_name: Candidate food name.
        portion_amount: Estimated or user-entered portion amount.
        portion_unit: Portion unit label.
        kcal: Estimated calories.
        carb_g: Estimated carbohydrate grams.
        protein_g: Estimated protein grams.
        fat_g: Estimated fat grams.
        sodium_mg: Estimated sodium milligrams.
        confidence: Candidate confidence from 0.0 to 1.0.
        source: Source that produced the candidate.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str = Field(min_length=1, max_length=160)
    portion_amount: float | None = Field(default=None, ge=0)
    portion_unit: str | None = Field(default=None, max_length=40)
    kcal: float | None = Field(default=None, ge=0)
    carb_g: float | None = Field(default=None, ge=0)
    protein_g: float | None = Field(default=None, ge=0)
    fat_g: float | None = Field(default=None, ge=0)
    sodium_mg: float | None = Field(default=None, ge=0)
    confidence: float = Field(ge=0, le=1)
    source: Literal["vision", "manual", "database_match"]


class MealFoodItemInput(BaseModel):
    """User-confirmed food item submitted during meal confirmation.

    Attributes:
        display_name: User-confirmed food name.
        portion_amount: User-confirmed portion amount.
        portion_unit: User-confirmed portion unit.
        kcal: User-confirmed or accepted estimated calories.
        carb_g: User-confirmed or accepted estimated carbohydrate grams.
        protein_g: User-confirmed or accepted estimated protein grams.
        fat_g: User-confirmed or accepted estimated fat grams.
        sodium_mg: User-confirmed or accepted estimated sodium milligrams.
        food_catalog_item_id: Optional curated food taxonomy item identifier.
        confidence: Optional detector confidence retained for traceability.
        source: Source of the confirmed row.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str = Field(min_length=1, max_length=160)
    portion_amount: float | None = Field(default=None, ge=0)
    portion_unit: str | None = Field(default=None, max_length=40)
    kcal: float | None = Field(default=None, ge=0)
    carb_g: float | None = Field(default=None, ge=0)
    protein_g: float | None = Field(default=None, ge=0)
    fat_g: float | None = Field(default=None, ge=0)
    sodium_mg: float | None = Field(default=None, ge=0)
    food_catalog_item_id: UUID | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    source: Literal["vision", "manual", "database_match"] = "manual"


class MealConfirmationRequest(BaseModel):
    """Request to confirm a meal image preview into a meal record.

    Attributes:
        analysis_id: Optional food image analysis id for preview traceability.
        food_items: User-confirmed food rows.
        meal_type: Optional user-confirmed meal bucket override.
        eaten_at: Optional user-confirmed meal timestamp override.
        user_confirmed: Must be true to prevent silent preview-to-record promotion.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    analysis_id: UUID | None = None
    food_items: list[MealFoodItemInput] = Field(min_length=1, max_length=40)
    meal_type: MealType | None = None
    eaten_at: datetime | None = None
    user_confirmed: Literal[True] = True


class MealRecordUpdateRequest(BaseModel):
    """Request to edit a confirmed meal record.

    Attributes:
        food_items: Replacement user-confirmed food rows. When omitted, food
            rows are kept unchanged.
        meal_type: Optional edited meal bucket.
        eaten_at: Optional edited meal timestamp.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    food_items: list[MealFoodItemInput] | None = Field(
        default=None,
        min_length=1,
        max_length=40,
    )
    meal_type: MealType | None = None
    eaten_at: datetime | None = None


class MealFoodItemResponse(BaseModel):
    """Persisted current-user food item response.

    Attributes:
        id: Persisted food item identifier.
        display_name: User-confirmed food name.
        portion_amount: User-confirmed portion amount.
        portion_unit: User-confirmed portion unit.
        kcal: Confirmed calories.
        carb_g: Confirmed carbohydrate grams.
        protein_g: Confirmed protein grams.
        fat_g: Confirmed fat grams.
        sodium_mg: Confirmed sodium milligrams.
        food_catalog_item_id: Curated food taxonomy item id when confirmed.
        catalog_item: Safe catalog taxonomy summary when available.
        confidence: Optional detector confidence retained for review traceability.
        source: Source of the confirmed row.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str
    portion_amount: float | None
    portion_unit: str | None
    kcal: float | None
    carb_g: float | None
    protein_g: float | None
    fat_g: float | None
    sodium_mg: float | None
    food_catalog_item_id: UUID | None
    catalog_item: FoodCatalogItemReference | None = None
    confidence: float | None
    source: Literal["vision", "manual", "database_match"]


class MealRecordResponse(BaseModel):
    """Persisted current-user meal response.

    Attributes:
        id: Persisted meal record identifier.
        status: Meal lifecycle status.
        meal_type: User-confirmed meal bucket.
        eaten_at: User-confirmed meal timestamp.
        food_items: User-confirmed food items.
        nutrition_summary: Bounded confirmed nutrition summary.
        confirmed_at: Confirmation timestamp.
        created_at: Server-side record creation timestamp.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: MealAnalysisStatus
    meal_type: MealType
    eaten_at: datetime
    food_items: list[MealFoodItemResponse]
    nutrition_summary: dict[str, object] = Field(default_factory=dict)
    confirmed_at: datetime
    created_at: datetime


class MealRecordListResponse(BaseModel):
    """Paginated current-user meal list response.

    Attributes:
        results: Confirmed meal records visible to the current owner.
        limit: Maximum requested row count.
        offset: Requested row offset.
    """

    results: list[MealRecordResponse]
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


class FoodImagePipelineMetadata(BaseModel):
    """Sanitized food image pipeline metadata for mobile smoke tests.

    Attributes:
        intake_completed: Whether image validation and hashing completed.
        detector_model: Detector model label when configured.
        classifier_model: Classifier model label when configured.
        detector_used: Whether a detector actually ran.
        classifier_used: Whether a classifier actually ran.
        raw_image_stored: Always false unless a future consented media object is linked.
        raw_provider_payload_stored: Always false.
        requires_manual_entry: Whether the UI should ask for manual food details.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    intake_completed: bool
    detector_model: str | None = Field(default=None, max_length=120)
    classifier_model: str | None = Field(default=None, max_length=120)
    detector_used: bool
    classifier_used: bool
    raw_image_stored: Literal[False] = False
    raw_provider_payload_stored: Literal[False] = False
    requires_manual_entry: bool


class MealImageAnalysisPreview(BaseModel):
    """Food image analysis preview response.

    Attributes:
        analysis_id: Food image analysis run identifier.
        meal_id: Linked meal preview identifier.
        status: Preview lifecycle status.
        meal_type: User-selected meal bucket.
        eaten_at: User-selected or server-defaulted meal timestamp.
        food_candidates: Review-only detected food candidates.
        nutrition_estimate_summary: Bounded nutrition estimate summary.
        warning_codes: Stable warning codes for the UI.
        pipeline_metadata: Sanitized pipeline metadata.
        algorithm_version: Backend preview algorithm contract version.
        created_at: Server-side analysis creation timestamp.
    """

    model_config = ConfigDict(extra="forbid")

    analysis_id: UUID
    meal_id: UUID
    status: MealAnalysisStatus
    meal_type: MealType
    eaten_at: datetime
    food_candidates: list[MealFoodCandidate] = Field(default_factory=list)
    nutrition_estimate_summary: dict[str, object] = Field(default_factory=dict)
    warning_codes: list[str] = Field(default_factory=list, max_length=20)
    pipeline_metadata: FoodImagePipelineMetadata
    algorithm_version: str = Field(min_length=1, max_length=80)
    created_at: datetime | None = None


class MealExplainRequest(BaseModel):
    """Request local RAG-backed explanation for a confirmed meal.

    Attributes:
        use_local_llm: Whether to attempt local Ollama refinement. The service
            falls back to deterministic wording when disabled or unavailable.
    """

    model_config = ConfigDict(extra="forbid")

    use_local_llm: bool = True


class MealExplanationSourceCitation(BaseModel):
    """Local WIKI source citation used to ground a meal explanation.

    Attributes:
        title: Document title inferred from Markdown heading or filename.
        source_path: Relative Markdown path under the configured WIKI root.
        heading: Best matching heading in the Markdown file.
        excerpt: Bounded excerpt used as retrieval context.
        score: Lexical retrieval score for deterministic ordering.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=160)
    source_path: str = Field(min_length=1, max_length=260)
    heading: str | None = Field(default=None, max_length=160)
    excerpt: str = Field(min_length=1, max_length=900)
    score: float = Field(ge=0)


class MealExplanationGuidance(BaseModel):
    """User-facing meal explanation bucket with constrained safety labels.

    Attributes:
        label: Safety category shown in the UI.
        message: Short non-diagnostic recommendation, caution, consultation, or
            confirmation message.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    label: Literal["권장", "주의", "상담 권고", "확인 필요"]
    message: str = Field(min_length=1, max_length=220)


class MealExplainResponse(BaseModel):
    """Safe explanation response for a confirmed meal record.

    Attributes:
        safe_user_message: Short summary suitable for the chat draft.
        explanation_bullets: Bounded explanation bullets derived from confirmed food data.
        guidance: Constrained recommendation/caution/consultation buckets.
        clinical_disclaimer: Fixed non-diagnostic disclaimer.
        llm_used: Whether local Ollama produced the final wording.
        source_citations: Local WIKI citations used for grounding.
        warnings: Stable warning codes for the UI/runtime.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    safe_user_message: str = Field(min_length=1, max_length=320)
    explanation_bullets: list[str] = Field(default_factory=list, max_length=6)
    guidance: list[MealExplanationGuidance] = Field(default_factory=list, max_length=8)
    clinical_disclaimer: str = Field(min_length=1, max_length=240)
    llm_used: bool = False
    source_citations: list[MealExplanationSourceCitation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list, max_length=12)
