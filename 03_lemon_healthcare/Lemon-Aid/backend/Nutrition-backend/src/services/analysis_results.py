"""Persisted analysis result services."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.algorithms.activity import ACTIVITY_ALGORITHM_VERSION, calculate_activity_score
from src.db.tx import persist_scope
from src.models.db.analysis_result import AnalysisResult
from src.models.schemas.algorithm import ActivityScoreRequest, WeightPredictionRequest
from src.models.schemas.analysis_result import (
    AnalysisResultResponse,
    AnalysisResultSummary,
    AnalysisType,
)
from src.models.schemas.dashboard import DashboardHealthScoreSummary
from src.models.schemas.nutrition import NutritionAnalysisRequest
from src.nutrition.deficiency_analysis import (
    NUTRITION_ANALYSIS_ALGORITHM_VERSION,
    analyze_nutrient_intakes,
)
from src.nutrition.source_manifest import load_kdris_source_manifest
from src.prediction.weight import WEIGHT_PREDICTION_ALGORITHM_VERSION, predict_weight_periods
from src.security.auth import AuthenticatedUser
from src.security.subjects import build_owner_subject

__all__ = [
    "analysis_result_to_response",
    "analysis_result_to_summary",
    "build_owner_subject",
    "get_analysis_result",
    "list_analysis_results",
    "store_activity_score_result",
    "store_daily_health_score_result",
    "store_nutrition_analysis_result",
    "store_weight_prediction_result",
]


def _json_snapshot(model: BaseModel) -> dict[str, Any]:
    """Return a JSON-compatible snapshot for a Pydantic model.

    Args:
        model: Pydantic model to serialize.

    Returns:
        JSON-compatible dictionary snapshot.
    """
    return model.model_dump(mode="json")


def analysis_result_to_response(record: AnalysisResult) -> AnalysisResultResponse:
    """Convert a persisted ORM row to a detail API response.

    Args:
        record: Persisted analysis result row.

    Returns:
        Public detail response without owner identifiers or input snapshots.
    """
    return AnalysisResultResponse.model_validate(record)


def analysis_result_to_summary(record: AnalysisResult) -> AnalysisResultSummary:
    """Convert a persisted ORM row to a list API response item.

    Args:
        record: Persisted analysis result row.

    Returns:
        Public summary response without owner identifiers or snapshots.
        daily_health_score 행은 4주 추이 조회용 요약 필드(score/measured_date/label)를
        스냅샷에서 추출해 함께 내려준다 — 타 타입은 None (가이드 06 §4.1).
    """
    summary = AnalysisResultSummary.model_validate(record)
    if record.analysis_type != AnalysisType.DAILY_HEALTH_SCORE.value:
        return summary
    snapshot = record.result_snapshot or {}
    score = snapshot.get("score")
    measured_date = snapshot.get("measured_date")
    label = snapshot.get("label")
    return summary.model_copy(
        update={
            "score": score if isinstance(score, int) else None,
            "measured_date": measured_date if isinstance(measured_date, str) else None,
            "label": label if isinstance(label, str) else None,
        }
    )


async def _persist_result(
    session: AsyncSession,
    user: AuthenticatedUser,
    analysis_type: AnalysisType,
    algorithm_version: str,
    input_snapshot: dict[str, Any],
    result_snapshot: dict[str, Any],
    kdris_source_manifest_version: str | None = None,
) -> AnalysisResult:
    """Persist one server-computed analysis result.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        analysis_type: Type of analysis.
        algorithm_version: Server algorithm version.
        input_snapshot: Server-validated request payload.
        result_snapshot: Server-computed result payload.
        kdris_source_manifest_version: KDRIs manifest schema version for nutrition results.

    Returns:
        Persisted ORM row refreshed from the database.

    Raises:
        ValueError: If owner identity cannot be persisted safely.
    """
    record = AnalysisResult(
        owner_subject=build_owner_subject(user),
        analysis_type=analysis_type.value,
        algorithm_version=algorithm_version,
        kdris_source_manifest_version=kdris_source_manifest_version,
        input_snapshot=input_snapshot,
        result_snapshot=result_snapshot,
    )

    async with persist_scope(session):
        session.add(record)
        await session.flush()
        await session.refresh(record)
    return record


async def store_daily_health_score_result(
    session: AsyncSession,
    user: AuthenticatedUser,
    summary_date: date,
    health_score: DashboardHealthScoreSummary,
) -> AnalysisResult | None:
    """Persist at most one ready daily health score per owner per summary date.

    Unlike the request-driven store functions above, this persists a result the
    dashboard already computed, so there is no recalculation here. The dashboard
    read path has an implicit transaction open by the time this runs, which is
    why this commits directly instead of reusing ``_persist_result`` (whose
    ``session.begin()`` would raise on an already-begun session).

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        summary_date: Dashboard summary date the score was computed for.
        health_score: Server-computed daily health score block.

    Returns:
        The persisted row, or None when the score is not ready or a row for
        the same owner and summary date already exists (dedup guard — the
        dashboard is polled frequently).
    """
    if health_score.data_status != "ready" or health_score.score is None:
        return None

    owner_subject = build_owner_subject(user)
    existing_id = await session.scalar(
        select(AnalysisResult.id)
        .where(
            AnalysisResult.owner_subject == owner_subject,
            AnalysisResult.analysis_type == AnalysisType.DAILY_HEALTH_SCORE.value,
            AnalysisResult.input_snapshot["summary_date"].astext == summary_date.isoformat(),
        )
        .limit(1)
    )
    if existing_id is not None:
        return None

    record = AnalysisResult(
        owner_subject=owner_subject,
        analysis_type=AnalysisType.DAILY_HEALTH_SCORE.value,
        algorithm_version=health_score.algorithm_version,
        kdris_source_manifest_version=None,
        input_snapshot={
            "summary_date": summary_date.isoformat(),
            "weights": {
                "activity": health_score.components.activity.weight,
                "nutrition": health_score.components.nutrition.weight,
            },
        },
        result_snapshot=health_score.model_dump(mode="json"),
    )
    session.add(record)
    await session.commit()
    return record


async def store_activity_score_result(
    session: AsyncSession,
    user: AuthenticatedUser,
    request: ActivityScoreRequest,
) -> AnalysisResult:
    """Compute and persist an activity score result.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        request: Server-validated activity score request.

    Returns:
        Persisted analysis result row.
    """
    result = calculate_activity_score(request)
    return await _persist_result(
        session=session,
        user=user,
        analysis_type=AnalysisType.ACTIVITY_SCORE,
        algorithm_version=ACTIVITY_ALGORITHM_VERSION,
        input_snapshot=_json_snapshot(request),
        result_snapshot=_json_snapshot(result),
    )


async def store_weight_prediction_result(
    session: AsyncSession,
    user: AuthenticatedUser,
    request: WeightPredictionRequest,
) -> AnalysisResult:
    """Compute and persist a weight prediction result.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        request: Server-validated weight prediction request.

    Returns:
        Persisted analysis result row.
    """
    result = predict_weight_periods(
        weight_kg=request.weight_kg,
        height_cm=request.height_cm,
        age=request.age,
        sex=request.sex,
        daily_steps=request.daily_steps,
        daily_intake_kcal=request.daily_intake_kcal,
        periods_days=request.periods_days,
        body_fat_pct=request.body_fat_pct,
        alcohol_kcal=request.alcohol_kcal,
        walking_cadence_steps_per_min=request.walking_cadence_steps_per_min,
        walking_cadence_minutes=request.walking_cadence_minutes,
        exercise_average_heart_rate_bpm=request.exercise_average_heart_rate_bpm,
        heart_rate_exercise_minutes=request.heart_rate_exercise_minutes,
        chronic_diseases=request.chronic_diseases,
        prediction_checkins=request.prediction_checkins,
    )
    return await _persist_result(
        session=session,
        user=user,
        analysis_type=AnalysisType.WEIGHT_PREDICTION,
        algorithm_version=WEIGHT_PREDICTION_ALGORITHM_VERSION,
        input_snapshot=_json_snapshot(request),
        result_snapshot=_json_snapshot(result),
    )


async def store_nutrition_analysis_result(
    session: AsyncSession,
    user: AuthenticatedUser,
    request: NutritionAnalysisRequest,
) -> AnalysisResult:
    """Compute and persist a nutrition analysis result.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        request: Server-validated nutrition analysis request.

    Returns:
        Persisted analysis result row.

    Raises:
        ValueError: If a KDRIs reference cannot be found.
    """
    result = analyze_nutrient_intakes(profile=request.profile, intakes=request.intakes)
    manifest = load_kdris_source_manifest()
    return await _persist_result(
        session=session,
        user=user,
        analysis_type=AnalysisType.NUTRITION_ANALYSIS,
        algorithm_version=NUTRITION_ANALYSIS_ALGORITHM_VERSION,
        kdris_source_manifest_version=manifest["schema_version"],
        input_snapshot=_json_snapshot(request),
        result_snapshot=_json_snapshot(result),
    )


async def list_analysis_results(
    session: AsyncSession,
    user: AuthenticatedUser,
    analysis_type: AnalysisType | None,
    limit: int,
    offset: int,
) -> list[AnalysisResult]:
    """List persisted analysis results visible to the current owner.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        analysis_type: Optional analysis type filter.
        limit: Maximum row count.
        offset: Row offset.

    Returns:
        Persisted analysis rows ordered from newest to oldest.

    Raises:
        ValueError: If owner identity cannot be persisted safely.
    """
    statement = (
        select(AnalysisResult)
        .where(AnalysisResult.owner_subject == build_owner_subject(user))
        .order_by(desc(AnalysisResult.created_at))
        .limit(limit)
        .offset(offset)
    )
    if analysis_type is not None:
        statement = statement.where(AnalysisResult.analysis_type == analysis_type.value)

    result = await session.scalars(statement)
    return list(result.all())


async def get_analysis_result(
    session: AsyncSession,
    user: AuthenticatedUser,
    result_id: UUID,
) -> AnalysisResult | None:
    """Get one persisted analysis result if it belongs to the current owner.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        result_id: Persisted result identifier.

    Returns:
        Persisted row or None when not found for this owner.

    Raises:
        ValueError: If owner identity cannot be persisted safely.
    """
    statement = select(AnalysisResult).where(
        AnalysisResult.id == result_id,
        AnalysisResult.owner_subject == build_owner_subject(user),
    )
    record: AnalysisResult | None = await session.scalar(statement)
    return record
