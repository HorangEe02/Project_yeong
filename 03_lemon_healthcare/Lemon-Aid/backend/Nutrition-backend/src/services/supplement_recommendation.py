"""Supplement impact preview orchestration service."""

from __future__ import annotations

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db.analysis_result import AnalysisResult
from src.models.schemas.supplement_recommendation import (
    SupplementImpactDataStatus,
    SupplementImpactPreviewRequest,
    SupplementImpactPreviewResponse,
    SupplementRecommendationActionLabel,
)
from src.models.schemas.user import UserProfile
from src.nutrition.deficiency_analysis import contains_forbidden_terms
from src.nutrition.kdris import get_kdris_dataset_context
from src.security.auth import AuthenticatedUser
from src.services.nutrition_diagnosis import get_latest_nutrition_analysis_result
from src.services.personalized_nutrition_risk import classify_personalized_supplement_risks
from src.services.supplement_contribution import load_supplement_contribution_result

SUPPLEMENT_IMPACT_ALGORITHM_VERSION = "supplement-impact-v1.0.0"
# NOTE: user-facing text is scanned against FORBIDDEN_TERMS ("진단","치료","처방",
# "복용량 변경") and rejected, so the disclaimer conveys "this is not a medical
# diagnosis — consult a doctor/pharmacist" WITHOUT using those exact tokens.
SUPPLEMENT_IMPACT_DISCLAIMER = (
    "이 결과는 라벨과 사용자가 확인한 입력 기록 기준의 건강관리 참고 정보이며, "
    "의학적 판단을 대신하지 않습니다. 개인 건강 상태를 확정하지 않으므로, "
    "자세한 사항은 반드시 의사·약사 등 전문가와 상담하시기 바랍니다."
)


async def build_supplement_impact_preview(
    session: AsyncSession,
    user: AuthenticatedUser,
    request: SupplementImpactPreviewRequest,
) -> SupplementImpactPreviewResponse:
    """Build a deterministic supplement impact preview for the current user.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        request: Preview request.

    Returns:
        Supplement impact preview response.

    Raises:
        ValueError: If generated user-facing wording violates safety rules.
    """
    latest_result = await get_latest_nutrition_analysis_result(session, user)
    profile, profile_warnings = resolve_preview_profile(request, latest_result)
    contribution_result = await load_supplement_contribution_result(
        session,
        user,
        selected_supplement_ids=request.selected_supplement_ids,
        include_all_active_supplements=request.include_all_active_supplements,
        profile=profile,
    )
    risk_result = classify_personalized_supplement_risks(
        profile=profile,
        latest_nutrition_result=latest_result,
        contributions=contribution_result.aggregates,
    )
    dataset_context = get_kdris_dataset_context()
    warnings = _combined_warnings(
        profile_warnings=profile_warnings,
        contribution_warnings=contribution_result.warnings,
        risk_warnings=risk_result.warnings,
        dataset_status=dataset_context["dataset_status"],
    )
    safe_user_message = _summary_message(
        data_status=risk_result.data_status,
        contribution_count=len(contribution_result.aggregates),
        deficiency_count=len(risk_result.deficiency_support_candidates),
        risk_count=len(risk_result.excess_or_duplicate_risks),
    )
    _validate_safe_messages(
        [
            safe_user_message,
            SUPPLEMENT_IMPACT_DISCLAIMER,
            *[
                insight.user_message
                for insight in (
                    *risk_result.deficiency_support_candidates,
                    *risk_result.excess_or_duplicate_risks,
                )
            ],
        ]
    )
    return SupplementImpactPreviewResponse(
        reference_version=dataset_context["dataset_version"],
        source_manifest_version=dataset_context["source_manifest_version"],
        data_status=risk_result.data_status,
        current_supplement_contributions=list(contribution_result.aggregates),
        deficiency_support_candidates=list(risk_result.deficiency_support_candidates),
        excess_or_duplicate_risks=list(risk_result.excess_or_duplicate_risks),
        missing_profile_fields=list(risk_result.missing_profile_fields),
        safe_user_message=safe_user_message,
        clinical_disclaimer=SUPPLEMENT_IMPACT_DISCLAIMER,
        warnings=warnings,
        requires_user_confirmation=_requires_user_confirmation(
            data_status=risk_result.data_status,
            warnings=warnings,
            response_labels=[
                insight.action_label
                for insight in (
                    *risk_result.deficiency_support_candidates,
                    *risk_result.excess_or_duplicate_risks,
                )
            ],
        ),
    )


def resolve_preview_profile(
    request: SupplementImpactPreviewRequest,
    latest_result: AnalysisResult | None,
) -> tuple[UserProfile | None, tuple[str, ...]]:
    """Resolve the profile used for supplement impact calculation.

    Args:
        request: Preview request.
        latest_result: Latest nutrition analysis result.

    Returns:
        Profile and safe warning strings.
    """
    if request.profile_override is not None:
        return request.profile_override, ()
    if latest_result is None:
        return None, ("profile_missing",)
    raw_profile = latest_result.input_snapshot.get("profile")
    if not isinstance(raw_profile, dict):
        return None, ("profile_missing",)
    try:
        return UserProfile.model_validate(raw_profile), ()
    except ValidationError:
        return None, ("profile_invalid",)


def _combined_warnings(
    *,
    profile_warnings: tuple[str, ...],
    contribution_warnings: tuple[str, ...],
    risk_warnings: tuple[str, ...],
    dataset_status: str,
) -> list[str]:
    """Combine warning sources into a deterministic warning list.

    Args:
        profile_warnings: Profile resolution warnings.
        contribution_warnings: Contribution calculation warnings.
        risk_warnings: Risk classification warnings.
        dataset_status: KDRI dataset status.

    Returns:
        Deduplicated warning list.
    """
    warnings = [*profile_warnings, *contribution_warnings, *risk_warnings]
    if dataset_status != "official_2025_approved":
        warnings.append(f"kdris_dataset_status:{dataset_status}")
    return list(dict.fromkeys(warnings))


def _summary_message(
    *,
    data_status: SupplementImpactDataStatus,
    contribution_count: int,
    deficiency_count: int,
    risk_count: int,
) -> str:
    """Build a safe user-facing preview summary.

    Args:
        data_status: Data readiness status.
        contribution_count: Number of contribution aggregates.
        deficiency_count: Number of low-intake overlap candidates.
        risk_count: Number of duplicate or upper-limit review insights.

    Returns:
        Safe summary message.
    """
    if contribution_count == 0:
        return "등록된 보충제 성분이 없어 현재 계산할 보충제 기여량이 없습니다."
    if data_status == SupplementImpactDataStatus.PARTIAL:
        return "보충제 성분은 계산했지만 개인화 비교에 필요한 입력이 일부 부족합니다."
    if risk_count > 0:
        return f"중복 또는 상한 섭취량 확인이 필요한 영양소 {risk_count}종이 있습니다."
    if deficiency_count > 0:
        return f"낮은 섭취로 표시된 영양소와 겹치는 보충제 성분 {deficiency_count}종이 있습니다."
    return "현재 입력 기준으로 우선 확인할 보충제 중복 또는 상한 위험이 없습니다."


def _requires_user_confirmation(
    *,
    data_status: SupplementImpactDataStatus,
    warnings: list[str],
    response_labels: list[SupplementRecommendationActionLabel],
) -> bool:
    """Return whether the UI should ask the user to review this preview.

    Args:
        data_status: Data readiness status.
        warnings: Warning list.
        response_labels: Insight labels included in the response.

    Returns:
        True when review is useful.
    """
    if data_status != SupplementImpactDataStatus.READY or warnings:
        return True
    review_labels = {
        SupplementRecommendationActionLabel.REVIEW_NEEDED,
        SupplementRecommendationActionLabel.AVOID_DUPLICATE,
        SupplementRecommendationActionLabel.DISCUSS_WITH_PROFESSIONAL,
    }
    return any(label in review_labels for label in response_labels)


def _validate_safe_messages(messages: list[str]) -> None:
    """Reject forbidden wording in generated response messages.

    Args:
        messages: User-facing messages.

    Raises:
        ValueError: If a forbidden term is present.
    """
    if contains_forbidden_terms(messages):
        raise ValueError("Supplement impact response contains unsafe user wording.")
