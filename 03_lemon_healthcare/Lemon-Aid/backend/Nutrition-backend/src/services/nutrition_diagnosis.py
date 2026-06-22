"""Current-user persisted nutrition diagnosis read services."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db.analysis_result import AnalysisResult
from src.models.schemas.analysis_result import AnalysisType
from src.models.schemas.nutrition import (
    NutrientAnalysisResult,
    NutrientStatus,
    NutritionDiagnosisLatestResponse,
    NutritionDiagnosisSummary,
)
from src.nutrition.deficiency_analysis import contains_forbidden_terms
from src.security.auth import AuthenticatedUser
from src.security.subjects import build_owner_subject

NUTRITION_DIAGNOSIS_NOT_READY_MESSAGE = (
    "저장된 영양 분석 결과가 없어 대시보드에 표시할 부족 영양소 정보가 아직 없습니다."
)
NUTRITION_DIAGNOSIS_DISCLAIMER = "결과는 건강관리 참고 정보이며 개인 건강 상태를 확정하지 않습니다."


def _status_counts(results: Iterable[NutrientAnalysisResult]) -> dict[NutrientStatus, int]:
    """Count nutrient results by status.

    Args:
        results: Nutrient analysis results.

    Returns:
        Mapping from status to count.
    """
    counts = dict.fromkeys(NutrientStatus, 0)
    for result in results:
        counts[result.status] += 1
    return counts


def _summary_message(deficient_or_low_count: int, excessive_or_risky_count: int) -> str:
    """Build a safe user-facing summary message.

    Args:
        deficient_or_low_count: Number of nutrients below the configured reference range.
        excessive_or_risky_count: Number of nutrients above the configured reference range or UL.

    Returns:
        Safe summary message without diagnosis or treatment wording.
    """
    if deficient_or_low_count == 0 and excessive_or_risky_count == 0:
        return "현재 입력 기준으로 우선 확인할 부족 또는 과다 영양소가 없습니다."
    return (
        f"섭취량 확인이 필요한 낮은 섭취 영양소 {deficient_or_low_count}종, "
        f"과다 가능성 확인 영양소 {excessive_or_risky_count}종이 있습니다."
    )


def _empty_summary() -> NutritionDiagnosisSummary:
    """Build an empty nutrition summary for users without stored results.

    Returns:
        Empty diagnosis summary.
    """
    return NutritionDiagnosisSummary(
        total_count=0,
        deficient_count=0,
        low_count=0,
        adequate_count=0,
        excessive_count=0,
        risky_count=0,
        deficient_or_low_count=0,
        excessive_or_risky_count=0,
        summary_message=NUTRITION_DIAGNOSIS_NOT_READY_MESSAGE,
    )


def build_nutrition_diagnosis_response(
    record: AnalysisResult | None,
) -> NutritionDiagnosisLatestResponse:
    """Convert a persisted nutrition analysis result into the latest diagnosis response.

    Args:
        record: Latest owner-scoped nutrition analysis result, or None.

    Returns:
        Latest diagnosis response for mobile and dashboard reads.

    Raises:
        ValueError: If the persisted result snapshot is malformed or contains unsafe wording.
    """
    if record is None:
        return NutritionDiagnosisLatestResponse(
            data_status="not_ready",
            result_id=None,
            created_at=None,
            algorithm_version=None,
            summary=_empty_summary(),
            diagnoses=[],
            recommended_foods={},
            disclaimers=[NUTRITION_DIAGNOSIS_DISCLAIMER],
        )

    raw_results = record.result_snapshot.get("results")
    if not isinstance(raw_results, list):
        raise ValueError("Persisted nutrition analysis result is missing result rows.")

    diagnoses = [NutrientAnalysisResult.model_validate(result) for result in raw_results]
    user_messages = [diagnosis.user_message for diagnosis in diagnoses]
    if contains_forbidden_terms(user_messages):
        raise ValueError("Persisted nutrition analysis result contains unsafe user wording.")

    counts = _status_counts(diagnoses)
    deficient_or_low_count = (
        counts[NutrientStatus.DEFICIENT]
        + counts[NutrientStatus.LOW]
        + counts[NutrientStatus.AT_RISK_INADEQUATE]
        + counts[NutrientStatus.BELOW_RDA]
    )
    excessive_or_risky_count = (
        counts[NutrientStatus.EXCESSIVE]
        + counts[NutrientStatus.EXCESSIVE_NEAR_UL]
        + counts[NutrientStatus.RISKY]
    )
    summary = NutritionDiagnosisSummary(
        total_count=len(diagnoses),
        deficient_count=counts[NutrientStatus.DEFICIENT],
        low_count=counts[NutrientStatus.LOW],
        adequate_count=counts[NutrientStatus.ADEQUATE],
        excessive_count=counts[NutrientStatus.EXCESSIVE],
        risky_count=counts[NutrientStatus.RISKY],
        deficient_or_low_count=deficient_or_low_count,
        excessive_or_risky_count=excessive_or_risky_count,
        dataset_status=_optional_string(record.result_snapshot.get("dataset_status")),
        dataset_version=_optional_string(record.result_snapshot.get("dataset_version")),
        source_manifest_version=record.kdris_source_manifest_version
        or _optional_string(record.result_snapshot.get("source_manifest_version")),
        summary_message=_summary_message(deficient_or_low_count, excessive_or_risky_count),
    )
    return NutritionDiagnosisLatestResponse(
        data_status="ready",
        result_id=record.id,
        created_at=record.created_at,
        algorithm_version=record.algorithm_version,
        summary=summary,
        diagnoses=diagnoses,
        recommended_foods={},
        disclaimers=[NUTRITION_DIAGNOSIS_DISCLAIMER],
    )


async def get_latest_nutrition_analysis_result(
    session: AsyncSession,
    user: AuthenticatedUser,
) -> AnalysisResult | None:
    """Load the latest persisted nutrition analysis result for the current owner.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.

    Returns:
        Latest nutrition analysis row, or None when unavailable.

    Raises:
        ValueError: If owner identity cannot be persisted safely.
    """
    statement = (
        select(AnalysisResult)
        .where(
            AnalysisResult.owner_subject == build_owner_subject(user),
            AnalysisResult.analysis_type == AnalysisType.NUTRITION_ANALYSIS.value,
            # 챗 승인 스냅샷(store_app_health_analysis_result)도 같은 analysis_type을
            # {analysis_kind, snapshot} 형식으로 공유한다. 대시보드/진단/보충제 프리뷰는
            # results 행을 가진 파이프라인 형식만 읽어야 하므로 형식 자체로 구분한다.
            AnalysisResult.result_snapshot.has_key("results"),
        )
        .order_by(desc(AnalysisResult.created_at))
        .limit(1)
    )
    record: AnalysisResult | None = await session.scalar(statement)
    return record


async def get_latest_nutrition_diagnosis(
    session: AsyncSession,
    user: AuthenticatedUser,
) -> NutritionDiagnosisLatestResponse:
    """Return the latest persisted nutrition diagnosis response for the current user.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.

    Returns:
        Latest diagnosis response or a not-ready response.
    """
    record = await get_latest_nutrition_analysis_result(session, user)
    return build_nutrition_diagnosis_response(record)


def _optional_string(value: object) -> str | None:
    """Return a string value when the persisted snapshot value is a string.

    Args:
        value: Candidate snapshot value.

    Returns:
        String value or None.
    """
    return value if isinstance(value, str) else None
