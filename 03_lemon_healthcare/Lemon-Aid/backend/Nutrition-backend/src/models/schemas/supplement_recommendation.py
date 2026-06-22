"""Supplement impact and recommendation insight API schemas."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.models.schemas.supplement import SupplementAnalysisPreview
from src.models.schemas.user import UserProfile


class SupplementImpactDataStatus(StrEnum):
    """Readiness status for supplement impact calculation."""

    READY = "ready"
    PARTIAL = "partial"
    NOT_READY = "not_ready"


class SupplementRecommendationActionLabel(StrEnum):
    """Allowed non-prescriptive action labels for supplement insights."""

    INSIGHT = "insight"
    REVIEW_NEEDED = "review_needed"
    AVOID_DUPLICATE = "avoid_duplicate"
    DISCUSS_WITH_PROFESSIONAL = "discuss_with_professional"


class SupplementInsightEvidence(BaseModel):
    """Trace one safe evidence item used in a supplement insight.

    Attributes:
        source_type: Source bucket used for the evidence.
        source_id: Stable source identifier such as supplement id or KDRI source id.
        field: Field name within the source.
        value_summary: Short bounded value summary safe for API responses.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_type: Literal["user_supplement", "nutrition_analysis", "kdri_reference"]
    source_id: str = Field(min_length=1, max_length=160)
    field: str = Field(min_length=1, max_length=80)
    value_summary: str = Field(min_length=1, max_length=240)


class SupplementContributionItem(BaseModel):
    """One user-confirmed supplement ingredient contribution.

    Attributes:
        supplement_id: Parent supplement id.
        supplement_name: User-confirmed supplement display name.
        ingredient_id: Ingredient row id.
        display_name: User-confirmed ingredient name.
        nutrient_code: Internal nutrient code.
        amount_per_serving: Ingredient amount per serving.
        unit: Ingredient unit from the confirmed row.
        daily_servings: User-confirmed daily serving count.
        daily_amount: Calculated daily amount before KDRI-unit conversion.
        source: Ingredient source marker retained from registration.
        confidence: Extraction or user-confirmation confidence.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    supplement_id: UUID
    supplement_name: str = Field(min_length=1, max_length=200)
    ingredient_id: UUID
    display_name: str = Field(min_length=1, max_length=160)
    nutrient_code: str = Field(min_length=1, max_length=80)
    amount_per_serving: float = Field(ge=0)
    unit: str = Field(min_length=1, max_length=40)
    daily_servings: float = Field(gt=0, le=20)
    daily_amount: float = Field(ge=0)
    source: str = Field(min_length=1, max_length=80)
    confidence: float = Field(ge=0, le=1)


class SupplementContributionAggregate(BaseModel):
    """Daily contribution totals grouped by nutrient code.

    Attributes:
        nutrient_code: Internal nutrient code.
        nutrient_name: KDRI nutrient name when available.
        reference_unit: KDRI reference unit when profile-specific lookup succeeds.
        total_daily_amount: Total amount converted to reference_unit, when possible.
        original_unit_totals: Daily totals grouped by confirmed ingredient unit.
        contribution_count: Number of ingredient rows included in the aggregate.
        supplement_ids: Supplement ids contributing this nutrient.
        items: Ingredient-level contributions included in the aggregate.
        warnings: Safe warning codes or messages for this nutrient aggregate.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nutrient_code: str = Field(min_length=1, max_length=80)
    nutrient_name: str | None = Field(default=None, max_length=160)
    reference_unit: str | None = Field(default=None, max_length=40)
    total_daily_amount: float | None = Field(default=None, ge=0)
    original_unit_totals: dict[str, float] = Field(default_factory=dict)
    contribution_count: int = Field(ge=0)
    supplement_ids: list[UUID] = Field(default_factory=list, max_length=100)
    items: list[SupplementContributionItem] = Field(default_factory=list, max_length=200)
    warnings: list[str] = Field(default_factory=list, max_length=20)


class SupplementNutritionInsight(BaseModel):
    """Non-prescriptive insight derived from deterministic supplement impact logic.

    Attributes:
        nutrient_code: Internal nutrient code.
        nutrient_name: KDRI nutrient name when available.
        action_label: Allowed safe action label.
        reason_code: Stable deterministic reason code.
        current_food_or_recorded_amount: Latest nutrition-analysis amount, when available.
        supplement_daily_amount: Supplement contribution in reference_unit.
        estimated_total_amount: Sum of recorded and supplement amounts, when available.
        reference_amount: KDRI reference amount when scalar comparison is possible.
        reference_unit: KDRI reference unit.
        ul_amount: Upper intake amount when available.
        contributing_supplements: Supplement ids contributing the nutrient.
        evidence: Safe source evidence supporting this insight.
        user_message: Safe user-facing message.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nutrient_code: str = Field(min_length=1, max_length=80)
    nutrient_name: str | None = Field(default=None, max_length=160)
    action_label: SupplementRecommendationActionLabel
    reason_code: str = Field(min_length=1, max_length=80)
    current_food_or_recorded_amount: float | None = Field(default=None, ge=0)
    supplement_daily_amount: float | None = Field(default=None, ge=0)
    estimated_total_amount: float | None = Field(default=None, ge=0)
    reference_amount: float | None = Field(default=None, ge=0)
    reference_unit: str | None = Field(default=None, max_length=40)
    ul_amount: float | None = Field(default=None, ge=0)
    contributing_supplements: list[UUID] = Field(default_factory=list, max_length=100)
    evidence: list[SupplementInsightEvidence] = Field(default_factory=list, max_length=20)
    user_message: str = Field(min_length=1, max_length=300)


class SupplementImpactPreviewRequest(BaseModel):
    """Request a deterministic supplement impact preview.

    Attributes:
        selected_supplement_ids: Optional subset of supplement ids to include.
        include_all_active_supplements: Whether to use all active supplements when no subset is sent.
        profile_override: Optional profile override for immediate preview only.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    selected_supplement_ids: list[UUID] = Field(default_factory=list, max_length=100)
    include_all_active_supplements: bool = True
    profile_override: UserProfile | None = None

    @model_validator(mode="after")
    def deduplicate_selected_ids(self) -> Self:
        """Preserve first-seen supplement ids for deterministic processing.

        Returns:
            Validated request with duplicate selected ids removed.
        """
        self.selected_supplement_ids = list(dict.fromkeys(self.selected_supplement_ids))
        return self


class SupplementImpactPreviewResponse(BaseModel):
    """Deterministic supplement impact preview response.

    Attributes:
        calculation_version: Server calculation algorithm version.
        reference_version: KDRI dataset version used for lookup.
        source_manifest_version: KDRI source manifest schema version.
        data_status: Whether the preview had enough data for personalized comparison.
        current_supplement_contributions: Current supplement contribution aggregates.
        deficiency_support_candidates: Nutrients whose low intake overlaps with supplement inputs.
        excess_or_duplicate_risks: Nutrients needing duplicate or upper-limit review.
        missing_profile_fields: Profile fields required for personalized comparison but missing.
        safe_user_message: Safe summary message.
        clinical_disclaimer: Fixed safety disclaimer.
        warnings: Safe calculation warning codes/messages.
        requires_user_confirmation: Whether the UI should ask the user to review inputs.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    calculation_version: Literal["supplement-impact-v1.0.0"] = "supplement-impact-v1.0.0"
    reference_version: str = Field(min_length=1, max_length=40)
    source_manifest_version: str | None = Field(default=None, max_length=40)
    data_status: SupplementImpactDataStatus
    current_supplement_contributions: list[SupplementContributionAggregate] = Field(
        default_factory=list,
        max_length=200,
    )
    deficiency_support_candidates: list[SupplementNutritionInsight] = Field(
        default_factory=list,
        max_length=200,
    )
    excess_or_duplicate_risks: list[SupplementNutritionInsight] = Field(
        default_factory=list,
        max_length=200,
    )
    missing_profile_fields: list[str] = Field(default_factory=list, max_length=20)
    safe_user_message: str = Field(min_length=1, max_length=300)
    clinical_disclaimer: str = Field(min_length=1, max_length=300)
    warnings: list[str] = Field(default_factory=list, max_length=80)
    requires_user_confirmation: bool = True


class SupplementRecommendationExplainRequest(BaseModel):
    """Request a safe explanation for a deterministic supplement impact preview.

    Attributes:
        preview: Deterministic preview to explain.
        locale: Response locale.
        use_local_llm: Whether to attempt local Ollama wording refinement.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    preview: SupplementImpactPreviewResponse
    locale: Literal["ko-KR"] = "ko-KR"
    use_local_llm: bool = False


class SupplementAnalysisExplainRequest(BaseModel):
    """Request a safe explanation for an OCR analysis preview.

    Attributes:
        locale: Response locale.
        use_local_llm: Whether to attempt local Ollama wording refinement.
        include_profile_context: Whether to include the current user's latest
            consent-gated health profile snapshot in the explanation context.
        include_medical_context: Whether to include bounded condition/medication
            summary buckets from the current user's consent-gated medical DB.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    locale: Literal["ko-KR"] = "ko-KR"
    use_local_llm: bool = False
    include_profile_context: bool = False
    include_medical_context: bool = False


class SupplementExplanationSourceCitation(BaseModel):
    """Source citation used to ground a safe local LLM explanation.

    Attributes:
        title: WIKI document title shown to the user.
        source_path: Relative path from the configured local WIKI root.
        heading: Matching heading inside the WIKI document, when available.
        excerpt: Bounded excerpt used as Gemma grounding context.
        score: Deterministic retrieval relevance score.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=160)
    source_path: str = Field(min_length=1, max_length=240)
    heading: str | None = Field(default=None, max_length=160)
    excerpt: str = Field(min_length=1, max_length=900)
    score: float = Field(ge=0)


class SupplementRecommendationExplainResponse(BaseModel):
    """Safe explanation response for supplement impact preview.

    Attributes:
        safe_user_message: Safe summary message.
        explanation_bullets: Bounded explanation bullets.
        clinical_disclaimer: Fixed safety disclaimer.
        blocked_terms_detected: Forbidden terms detected and blocked from LLM output.
        llm_used: Whether a local LLM output was accepted.
        source_citations: Local WIKI source citations used for explanation grounding.
        warnings: Safe warning codes/messages.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    safe_user_message: str = Field(min_length=1, max_length=300)
    explanation_bullets: list[str] = Field(default_factory=list, max_length=6)
    clinical_disclaimer: str = Field(min_length=1, max_length=300)
    blocked_terms_detected: list[str] = Field(default_factory=list, max_length=20)
    llm_used: bool = False
    source_citations: list[SupplementExplanationSourceCitation] = Field(
        default_factory=list,
        max_length=8,
    )
    warnings: list[str] = Field(default_factory=list, max_length=20)


class SupplementAnalysisPreviewWithRecommendation(SupplementAnalysisPreview):
    """OCR analysis preview optionally bundled with a same-request safe recommendation.

    Backward-compatible superset of :class:`SupplementAnalysisPreview`: all preview
    fields stay at the top level and ``recommendation`` is an added optional field
    (``None`` unless the caller opts in via ``with_recommendation``), so existing
    clients are unaffected.

    Attributes:
        recommendation: Safe recommendation/caution explanation for the scanned
            label, or ``None`` when not requested or when generation was skipped.
    """

    recommendation: SupplementRecommendationExplainResponse | None = None
