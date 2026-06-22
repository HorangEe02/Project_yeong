"""Current-user dashboard aggregation services."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings
from src.models.db.analysis_result import AnalysisResult
from src.models.db.health import HealthDailySummary
from src.models.db.supplement import SupplementAnalysisRun, UserSupplement
from src.models.schemas.analysis_result import AnalysisType
from src.models.schemas.dashboard import (
    DashboardActivitySummary,
    DashboardNutrientSummary,
    DashboardSummaryResponse,
    DashboardSupplementSummary,
    DashboardWeightSummary,
)
from src.security.auth import AuthenticatedUser
from src.security.subjects import build_owner_subject
from src.services.analysis_results import store_daily_health_score_result
from src.services.daily_health_score import build_daily_health_score
from src.services.nutrition_diagnosis import (
    NUTRITION_DIAGNOSIS_DISCLAIMER,
    build_nutrition_diagnosis_response,
    get_latest_nutrition_analysis_result,
)

DASHBOARD_ALGORITHM_VERSION = "dashboard-v1.0.0"
DEFAULT_DASHBOARD_DAYS = 30
SUPPLEMENT_REQUIRES_CONFIRMATION_STATUS = "requires_confirmation"


async def build_dashboard_summary(
    session: AsyncSession,
    user: AuthenticatedUser,
    as_of: date | None,
    days: int,
    settings: Settings,
) -> DashboardSummaryResponse:
    """Build a current-user dashboard summary from persisted read models.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        as_of: Optional local summary date.
        days: Health summary lookback window.
        settings: Application settings for daily-score WIKI retrieval.

    Returns:
        Dashboard summary response without owner identifiers or raw input snapshots.

    Raises:
        ValueError: If owner identity is invalid or a persisted nutrition snapshot is malformed.
    """
    owner_subject = build_owner_subject(user)
    now = datetime.now(UTC)
    summary_date = as_of or now.date()
    lookback_days = max(days, 1)

    nutrition_record = await get_latest_nutrition_analysis_result(session, user)
    activity_record = await _latest_analysis_result(
        session,
        owner_subject,
        AnalysisType.ACTIVITY_SCORE,
    )
    weight_record = await _latest_analysis_result(
        session,
        owner_subject,
        AnalysisType.WEIGHT_PREDICTION,
    )
    health_summaries = await _recent_health_summaries(
        session,
        owner_subject,
        summary_date,
        lookback_days,
    )
    registered_count = await _active_supplement_count(session, owner_subject)
    requires_review_count = await _requires_review_supplement_count(session, owner_subject, now)
    health_score = await build_daily_health_score(
        session,
        user,
        summary_date,
        settings,
        health_summaries=health_summaries,
    )
    if settings.persist_daily_health_score and health_score.data_status == "ready":
        # Opt-in (decision #7): unlocks the S-09 4-week trend chart. The store
        # function itself dedups to one row per owner per summary date.
        await store_daily_health_score_result(session, user, summary_date, health_score)

    return DashboardSummaryResponse(
        as_of=now,
        nutrition=_dashboard_nutrition_summary(nutrition_record),
        activity=_dashboard_activity_summary(health_summaries, activity_record),
        weight=_dashboard_weight_summary(health_summaries, weight_record),
        supplements=DashboardSupplementSummary(
            registered_count=registered_count,
            requires_review_count=requires_review_count,
        ),
        health_score=health_score,
        disclaimers=[NUTRITION_DIAGNOSIS_DISCLAIMER],
        algorithm_version=DASHBOARD_ALGORITHM_VERSION,
    )


def _dashboard_nutrition_summary(record: AnalysisResult | None) -> DashboardNutrientSummary:
    """Build the dashboard nutrition card summary from a persisted analysis row.

    Args:
        record: Latest owner-scoped nutrition analysis result.

    Returns:
        Dashboard nutrition summary.
    """
    diagnosis = build_nutrition_diagnosis_response(record)
    return DashboardNutrientSummary(
        data_status=diagnosis.data_status,
        latest_result_id=diagnosis.result_id,
        low_count=diagnosis.summary.deficient_or_low_count,
        high_count=diagnosis.summary.excessive_or_risky_count,
        dataset_version=diagnosis.summary.dataset_version,
        source_manifest_version=diagnosis.summary.source_manifest_version,
    )


def _dashboard_activity_summary(
    health_summaries: Sequence[HealthDailySummary],
    activity_record: AnalysisResult | None,
) -> DashboardActivitySummary:
    """Build the dashboard activity summary.

    Args:
        health_summaries: Recent health daily summaries ordered newest first.
        activity_record: Latest persisted activity score result.

    Returns:
        Dashboard activity summary.
    """
    latest_steps_row = next((row for row in health_summaries if row.steps is not None), None)
    latest_resting_heart_rate_row = next(
        (row for row in health_summaries if row.resting_heart_rate_bpm is not None),
        None,
    )
    latest_active_energy_row = next(
        (row for row in health_summaries if row.active_energy_kcal is not None),
        None,
    )
    latest_activity_row = next(
        (
            row
            for row in health_summaries
            if row.steps is not None
            or row.resting_heart_rate_bpm is not None
            or row.active_energy_kcal is not None
        ),
        None,
    )
    latest_steps = latest_steps_row.steps if latest_steps_row is not None else None
    latest_resting_heart_rate_bpm = (
        latest_resting_heart_rate_row.resting_heart_rate_bpm
        if latest_resting_heart_rate_row is not None
        else None
    )
    latest_active_energy_kcal = (
        _decimal_to_float(latest_active_energy_row.active_energy_kcal)
        if latest_active_energy_row is not None
        else None
    )
    activity_score = _number_from_snapshot(activity_record, "v4_score")
    return DashboardActivitySummary(
        data_status=(
            "ready"
            if latest_steps is not None
            or latest_resting_heart_rate_bpm is not None
            or latest_active_energy_kcal is not None
            or activity_score is not None
            else "not_ready"
        ),
        latest_steps=latest_steps,
        latest_resting_heart_rate_bpm=latest_resting_heart_rate_bpm,
        latest_active_energy_kcal=latest_active_energy_kcal,
        latest_activity_score=activity_score,
        measured_date=(
            latest_activity_row.measured_date if latest_activity_row is not None else None
        ),
    )


def _dashboard_weight_summary(
    health_summaries: Sequence[HealthDailySummary],
    weight_record: AnalysisResult | None,
) -> DashboardWeightSummary:
    """Build the dashboard weight summary.

    Args:
        health_summaries: Recent health daily summaries ordered newest first.
        weight_record: Latest persisted weight prediction result.

    Returns:
        Dashboard weight summary.
    """
    latest_weight_row = next((row for row in health_summaries if row.weight_kg is not None), None)
    latest_weight = (
        _decimal_to_float(latest_weight_row.weight_kg) if latest_weight_row is not None else None
    )
    predicted_weight = _short_term_predicted_weight(weight_record)
    return DashboardWeightSummary(
        data_status=(
            "ready" if latest_weight is not None or predicted_weight is not None else "not_ready"
        ),
        latest_weight_kg=latest_weight,
        predicted_weight_kg=predicted_weight,
        measured_date=latest_weight_row.measured_date if latest_weight_row is not None else None,
    )


async def _latest_analysis_result(
    session: AsyncSession,
    owner_subject: str,
    analysis_type: AnalysisType,
) -> AnalysisResult | None:
    """Load the latest owner-scoped analysis result for one analysis type.

    Args:
        session: Request-scoped async database session.
        owner_subject: Issuer-qualified owner subject.
        analysis_type: Analysis result type to load.

    Returns:
        Latest row or None.
    """
    statement = (
        select(AnalysisResult)
        .where(
            AnalysisResult.owner_subject == owner_subject,
            AnalysisResult.analysis_type == analysis_type.value,
        )
        .order_by(desc(AnalysisResult.created_at))
        .limit(1)
    )
    record: AnalysisResult | None = await session.scalar(statement)
    return record


async def _recent_health_summaries(
    session: AsyncSession,
    owner_subject: str,
    as_of: date,
    days: int,
) -> list[HealthDailySummary]:
    """Load recent health summaries for the dashboard lookback window.

    Args:
        session: Request-scoped async database session.
        owner_subject: Issuer-qualified owner subject.
        as_of: Last local date in the lookback window.
        days: Number of days to include.

    Returns:
        Health summary rows ordered newest first.
    """
    start_date = as_of - timedelta(days=days - 1)
    statement = (
        select(HealthDailySummary)
        .where(
            HealthDailySummary.owner_subject == owner_subject,
            HealthDailySummary.measured_date >= start_date,
            HealthDailySummary.measured_date <= as_of,
        )
        .order_by(desc(HealthDailySummary.measured_date), desc(HealthDailySummary.created_at))
    )
    result = await session.scalars(statement)
    return list(result.all())


async def _active_supplement_count(session: AsyncSession, owner_subject: str) -> int:
    """Count current-user active supplement records.

    Args:
        session: Request-scoped async database session.
        owner_subject: Issuer-qualified owner subject.

    Returns:
        Active supplement count.
    """
    statement = select(func.count(UserSupplement.id)).where(
        UserSupplement.owner_subject == owner_subject,
        UserSupplement.deleted_at.is_(None),
    )
    count = await session.scalar(statement)
    return int(count or 0)


async def _requires_review_supplement_count(
    session: AsyncSession,
    owner_subject: str,
    now: datetime,
) -> int:
    """Count unexpired supplement previews that still require user confirmation.

    Args:
        session: Request-scoped async database session.
        owner_subject: Issuer-qualified owner subject.
        now: Current server timestamp.

    Returns:
        Preview count requiring user review.
    """
    statement = select(func.count(SupplementAnalysisRun.id)).where(
        SupplementAnalysisRun.owner_subject == owner_subject,
        SupplementAnalysisRun.status == SUPPLEMENT_REQUIRES_CONFIRMATION_STATUS,
        SupplementAnalysisRun.expires_at > now,
        SupplementAnalysisRun.confirmed_at.is_(None),
    )
    count = await session.scalar(statement)
    return int(count or 0)


def _number_from_snapshot(record: AnalysisResult | None, key: str) -> float | None:
    """Read a numeric value from an analysis result snapshot.

    Args:
        record: Analysis result row.
        key: Result snapshot key.

    Returns:
        Float value or None.
    """
    if record is None:
        return None
    value = record.result_snapshot.get(key)
    if isinstance(value, int | float):
        return float(value)
    return None


def _short_term_predicted_weight(record: AnalysisResult | None) -> float | None:
    """Read the shortest-period predicted weight from a weight prediction result.

    Args:
        record: Weight prediction analysis result row.

    Returns:
        Predicted weight in kilograms, or None.
    """
    if record is None:
        return None
    predictions = record.result_snapshot.get("predictions")
    if not isinstance(predictions, list):
        return None
    prediction_rows = [
        prediction
        for prediction in predictions
        if isinstance(prediction, dict)
        and isinstance(prediction.get("days"), int)
        and isinstance(prediction.get("predicted_weight_kg"), int | float)
    ]
    if not prediction_rows:
        return None
    shortest_prediction: dict[str, Any] = min(
        prediction_rows,
        key=lambda prediction: prediction["days"],
    )
    return float(shortest_prediction["predicted_weight_kg"])


def _decimal_to_float(value: Decimal | None) -> float | None:
    """Convert an optional Decimal to float for API responses.

    Args:
        value: Decimal value from an ORM row.

    Returns:
        Float value or None.
    """
    if value is None:
        return None
    return float(value)
