"""Deterministic personalized nutrition risk classification for supplements."""

from __future__ import annotations

from dataclasses import dataclass

from src.models.db.analysis_result import AnalysisResult
from src.models.schemas.nutrition import NutrientAnalysisResult, NutrientStatus
from src.models.schemas.supplement_recommendation import (
    SupplementContributionAggregate,
    SupplementImpactDataStatus,
    SupplementInsightEvidence,
    SupplementNutritionInsight,
    SupplementRecommendationActionLabel,
)
from src.models.schemas.user import UserProfile
from src.nutrition.kdris import lookup_kdris_reference

SUPPLEMENT_RISK_DECIMALS = 3


@dataclass(frozen=True)
class PersonalizedNutritionRiskResult:
    """Risk classification output.

    Attributes:
        data_status: Data readiness status.
        deficiency_support_candidates: Low-intake nutrients overlapped by supplements.
        excess_or_duplicate_risks: Duplicate or upper-limit review insights.
        missing_profile_fields: Missing profile fields needed for personalization.
        warnings: Safe warning strings.
    """

    data_status: SupplementImpactDataStatus
    deficiency_support_candidates: tuple[SupplementNutritionInsight, ...]
    excess_or_duplicate_risks: tuple[SupplementNutritionInsight, ...]
    missing_profile_fields: tuple[str, ...]
    warnings: tuple[str, ...]


def classify_personalized_supplement_risks(
    *,
    profile: UserProfile | None,
    latest_nutrition_result: AnalysisResult | None,
    contributions: tuple[SupplementContributionAggregate, ...],
) -> PersonalizedNutritionRiskResult:
    """Classify supplement impact using deterministic nutrition rules.

    Args:
        profile: User profile used for KDRI lookup.
        latest_nutrition_result: Latest persisted nutrition analysis result.
        contributions: Supplement contribution aggregates.

    Returns:
        Risk classification result.
    """
    warnings: list[str] = []
    missing_profile_fields: list[str] = []
    analysis_by_code = _nutrition_results_by_code(latest_nutrition_result, warnings)

    if profile is None:
        missing_profile_fields.extend(["profile.age", "profile.sex", "profile.pregnancy_status"])
        warnings.append("profile_missing")

    if latest_nutrition_result is None:
        warnings.append("latest_nutrition_analysis_missing")
    elif not analysis_by_code:
        warnings.append("latest_nutrition_analysis_unusable")

    deficiency_candidates: list[SupplementNutritionInsight] = []
    risk_candidates: list[SupplementNutritionInsight] = []

    for aggregate in contributions:
        _classify_aggregate(
            aggregate=aggregate,
            profile=profile,
            analysis_by_code=analysis_by_code,
            deficiency_candidates=deficiency_candidates,
            risk_candidates=risk_candidates,
            warnings=warnings,
        )

    data_status = _data_status(
        profile=profile,
        latest_nutrition_result=latest_nutrition_result,
        contributions=contributions,
        warnings=warnings,
    )
    return PersonalizedNutritionRiskResult(
        data_status=data_status,
        deficiency_support_candidates=tuple(sorted(deficiency_candidates, key=_insight_sort_key)),
        excess_or_duplicate_risks=tuple(sorted(risk_candidates, key=_insight_sort_key)),
        missing_profile_fields=tuple(dict.fromkeys(missing_profile_fields)),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _nutrition_results_by_code(
    latest_nutrition_result: AnalysisResult | None,
    warnings: list[str],
) -> dict[str, NutrientAnalysisResult]:
    """Parse latest nutrition result rows into a nutrient-code map.

    Args:
        latest_nutrition_result: Persisted nutrition result.
        warnings: Mutable warning list.

    Returns:
        Nutrient-code keyed analysis result map.
    """
    if latest_nutrition_result is None:
        return {}
    raw_results = latest_nutrition_result.result_snapshot.get("results")
    if not isinstance(raw_results, list):
        warnings.append("latest_nutrition_results_missing")
        return {}
    parsed: dict[str, NutrientAnalysisResult] = {}
    for raw_result in raw_results:
        try:
            result = NutrientAnalysisResult.model_validate(raw_result)
        except ValueError:
            warnings.append("latest_nutrition_result_invalid")
            continue
        parsed[result.nutrient_code] = result
    return parsed


def _classify_aggregate(
    *,
    aggregate: SupplementContributionAggregate,
    profile: UserProfile | None,
    analysis_by_code: dict[str, NutrientAnalysisResult],
    deficiency_candidates: list[SupplementNutritionInsight],
    risk_candidates: list[SupplementNutritionInsight],
    warnings: list[str],
) -> None:
    """Classify one nutrient aggregate into insight buckets.

    Args:
        aggregate: Supplement contribution aggregate.
        profile: User profile.
        analysis_by_code: Latest nutrition analysis rows by nutrient code.
        deficiency_candidates: Mutable deficiency-support output list.
        risk_candidates: Mutable excess/duplicate output list.
        warnings: Mutable warning list.

    Returns:
        None.
    """
    analysis = analysis_by_code.get(aggregate.nutrient_code)
    reference = None
    if profile is not None:
        reference = lookup_kdris_reference(
            nutrient_code=aggregate.nutrient_code,
            age=profile.age,
            sex=profile.sex,
            pregnancy_status=profile.pregnancy_status,
        )

    review_needed = (
        aggregate.total_daily_amount is None
        or aggregate.reference_unit is None
        or bool(aggregate.warnings)
        or reference is None
    )
    if review_needed:
        risk_candidates.append(
            _build_insight(
                aggregate=aggregate,
                analysis=analysis,
                profile=profile,
                action_label=SupplementRecommendationActionLabel.REVIEW_NEEDED,
                reason_code=_review_reason_code(aggregate, reference is None),
                user_message="보충제 성분 계산에 확인이 필요한 항목이 있습니다.",
            )
        )
        warnings.append(f"supplement_contribution_review_needed:{aggregate.nutrient_code}")
        return

    if aggregate.contribution_count > 1 or len(aggregate.supplement_ids) > 1:
        risk_candidates.append(
            _build_insight(
                aggregate=aggregate,
                analysis=analysis,
                profile=profile,
                action_label=_profile_sensitive_label(
                    SupplementRecommendationActionLabel.AVOID_DUPLICATE,
                    profile,
                ),
                reason_code="duplicate_supplement_nutrient",
                user_message=(
                    "같은 영양소가 여러 보충제에서 겹칩니다. " "성분 중복 여부를 확인하세요."
                ),
            )
        )

    supplement_amount = aggregate.total_daily_amount
    recorded_amount = analysis.actual_amount if analysis is not None else None
    estimated_total = _estimated_total(recorded_amount, supplement_amount)
    if (
        reference is not None
        and reference.ul_amount is not None
        and estimated_total is not None
        and estimated_total > reference.ul_amount
    ):
        risk_candidates.append(
            _build_insight(
                aggregate=aggregate,
                analysis=analysis,
                profile=profile,
                action_label=_profile_sensitive_label(
                    SupplementRecommendationActionLabel.DISCUSS_WITH_PROFESSIONAL,
                    profile,
                ),
                reason_code="above_upper_intake_level",
                user_message=(
                    "입력 기준 총량이 상한 섭취량보다 높을 수 있어 " "전문가와 확인이 필요합니다."
                ),
            )
        )

    if analysis is not None and analysis.status in (NutrientStatus.DEFICIENT, NutrientStatus.LOW):
        deficiency_candidates.append(
            _build_insight(
                aggregate=aggregate,
                analysis=analysis,
                profile=profile,
                action_label=_profile_sensitive_label(
                    SupplementRecommendationActionLabel.INSIGHT,
                    profile,
                ),
                reason_code=f"latest_nutrition_{analysis.status.value}",
                user_message=(
                    "최근 영양 분석에서 낮게 표시된 영양소와 겹치는 "
                    "보충제 성분입니다. 라벨과 식이 기록을 함께 확인하세요."
                ),
            )
        )


def _build_insight(
    *,
    aggregate: SupplementContributionAggregate,
    analysis: NutrientAnalysisResult | None,
    profile: UserProfile | None,
    action_label: SupplementRecommendationActionLabel,
    reason_code: str,
    user_message: str,
) -> SupplementNutritionInsight:
    """Build a safe insight response item.

    Args:
        aggregate: Supplement contribution aggregate.
        analysis: Latest nutrition analysis row when available.
        profile: User profile when available.
        action_label: Safe action label.
        reason_code: Deterministic reason code.
        user_message: Safe user-facing message.

    Returns:
        Supplement nutrition insight.
    """
    reference_amount = analysis.reference_amount if analysis is not None else None
    reference_unit = aggregate.reference_unit or (analysis.reference_unit if analysis else None)
    ul_amount = analysis.ul_amount if analysis is not None else None
    if profile is not None and (reference_amount is None or ul_amount is None):
        reference = lookup_kdris_reference(
            nutrient_code=aggregate.nutrient_code,
            age=profile.age,
            sex=profile.sex,
            pregnancy_status=profile.pregnancy_status,
        )
        if reference is not None:
            reference_amount = reference.reference_amount
            ul_amount = reference.ul_amount
            reference_unit = reference.reference_unit

    supplement_amount = aggregate.total_daily_amount
    recorded_amount = analysis.actual_amount if analysis is not None else None
    return SupplementNutritionInsight(
        nutrient_code=aggregate.nutrient_code,
        nutrient_name=aggregate.nutrient_name or (analysis.nutrient_name if analysis else None),
        action_label=action_label,
        reason_code=reason_code,
        current_food_or_recorded_amount=recorded_amount,
        supplement_daily_amount=supplement_amount,
        estimated_total_amount=_estimated_total(recorded_amount, supplement_amount),
        reference_amount=reference_amount,
        reference_unit=reference_unit,
        ul_amount=ul_amount,
        contributing_supplements=aggregate.supplement_ids,
        evidence=_evidence_for_insight(aggregate, analysis),
        user_message=user_message,
    )


def _evidence_for_insight(
    aggregate: SupplementContributionAggregate,
    analysis: NutrientAnalysisResult | None,
) -> list[SupplementInsightEvidence]:
    """Build safe evidence records for an insight.

    Args:
        aggregate: Supplement contribution aggregate.
        analysis: Latest nutrition analysis row when available.

    Returns:
        Evidence records.
    """
    evidence = []
    if aggregate.supplement_ids:
        evidence.append(
            SupplementInsightEvidence(
                source_type="user_supplement",
                source_id=str(aggregate.supplement_ids[0]),
                field="daily_contribution",
                value_summary=(
                    f"{aggregate.nutrient_code}: "
                    f"{aggregate.total_daily_amount} {aggregate.reference_unit}"
                ),
            )
        )
    if analysis is not None:
        evidence.append(
            SupplementInsightEvidence(
                source_type="nutrition_analysis",
                source_id=analysis.nutrient_code,
                field="status",
                value_summary=f"{analysis.status.value}:{analysis.actual_amount}",
            )
        )
        if analysis.source_id is not None:
            evidence.append(
                SupplementInsightEvidence(
                    source_type="kdri_reference",
                    source_id=analysis.source_id,
                    field="reference",
                    value_summary=f"{analysis.reference_amount} {analysis.reference_unit}",
                )
            )
    return evidence


def _review_reason_code(
    aggregate: SupplementContributionAggregate,
    reference_missing: bool,
) -> str:
    """Return a deterministic review reason code.

    Args:
        aggregate: Contribution aggregate.
        reference_missing: Whether KDRI reference lookup failed.

    Returns:
        Stable reason code.
    """
    if reference_missing:
        return "kdri_reference_missing"
    if aggregate.total_daily_amount is None:
        return "unit_conversion_or_amount_review_needed"
    if aggregate.warnings:
        return aggregate.warnings[0]
    return "supplement_contribution_review_needed"


def _profile_sensitive_label(
    default_label: SupplementRecommendationActionLabel,
    profile: UserProfile | None,
) -> SupplementRecommendationActionLabel:
    """Escalate labels to professional discussion for sensitive profile contexts.

    Args:
        default_label: Default deterministic action label.
        profile: User profile when available.

    Returns:
        Safe action label.
    """
    if profile is None:
        return default_label
    if profile.pregnancy_status != "none" or profile.chronic_diseases:
        return SupplementRecommendationActionLabel.DISCUSS_WITH_PROFESSIONAL
    return default_label


def _estimated_total(
    recorded_amount: float | None, supplement_amount: float | None
) -> float | None:
    """Calculate estimated total amount when enough inputs are available.

    Args:
        recorded_amount: Latest nutrition-analysis amount.
        supplement_amount: Supplement contribution amount.

    Returns:
        Rounded total or None.
    """
    if recorded_amount is None or supplement_amount is None:
        return supplement_amount
    return round(recorded_amount + supplement_amount, SUPPLEMENT_RISK_DECIMALS)


def _data_status(
    *,
    profile: UserProfile | None,
    latest_nutrition_result: AnalysisResult | None,
    contributions: tuple[SupplementContributionAggregate, ...],
    warnings: list[str],
) -> SupplementImpactDataStatus:
    """Determine preview data readiness status.

    Args:
        profile: User profile.
        latest_nutrition_result: Latest nutrition result.
        contributions: Contribution aggregates.
        warnings: Warning list.

    Returns:
        Data status.
    """
    if not contributions:
        return SupplementImpactDataStatus.NOT_READY
    if profile is None or latest_nutrition_result is None or warnings:
        return SupplementImpactDataStatus.PARTIAL
    return SupplementImpactDataStatus.READY


def _insight_sort_key(insight: SupplementNutritionInsight) -> tuple[str, str]:
    """Return deterministic insight sort key.

    Args:
        insight: Supplement insight.

    Returns:
        Sort key tuple.
    """
    return (insight.nutrient_code, insight.reason_code)
