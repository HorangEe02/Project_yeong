"""예측 API 라우터."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.contract import P1_5_DEFICIENCY_DASHBOARD_READY_STATUS, route_contract
from src.api.v1.examples import (
    CONSENT_REQUIRED_EXAMPLE,
    UNAUTHORIZED_EXAMPLE,
    UNPROCESSABLE_ENTITY_EXAMPLE,
    WEIGHT_PREDICTION_REQUEST_EXAMPLES,
    WEIGHT_PREDICTION_RESPONSE_EXAMPLES,
)
from src.config import Settings, get_settings
from src.db.dependencies import get_rls_context_session
from src.models.schemas.algorithm import WeightPredictionRequest, WeightPredictionResponse
from src.models.schemas.privacy import ConsentType
from src.prediction.selector import predict_weight_periods_selected
from src.prediction.weight import calculate_alcohol_kcal_from_volume
from src.security.auth import AuthenticatedUser, require_analysis_read
from src.security.scopes import ApiScope
from src.services.privacy import (
    ConsentRequiredError,
    record_sensitive_audit_event,
    require_user_consent,
)

router = APIRouter(prefix="/predictions", tags=["predictions"])


async def _require_sensitive_health_consent(
    session: AsyncSession,
    current_user: AuthenticatedUser,
    http_request: Request,
    settings: Settings,
    *,
    blocked_action: str,
    resource_type: str,
) -> None:
    """Enforce SENSITIVE_HEALTH_ANALYSIS consent and audit the block on failure.

    Args:
        session: Request-scoped async database session.
        current_user: Authenticated owner.
        http_request: Current FastAPI request.
        settings: Application settings.
        blocked_action: Audit action name used when consent is missing.
        resource_type: Audit resource_type used when consent is missing.

    Raises:
        HTTPException: If the required consent is missing (HTTP 403).
    """
    try:
        await require_user_consent(session, current_user, ConsentType.SENSITIVE_HEALTH_ANALYSIS)
    except ConsentRequiredError as exc:
        await record_sensitive_audit_event(
            session,
            current_user,
            action=blocked_action,
            resource_type=resource_type,
            resource_id=None,
            outcome="blocked",
            request=http_request,
            settings=settings,
            event_metadata={"missing_consent": ConsentType.SENSITIVE_HEALTH_ANALYSIS.value},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "consent_required",
                "message": str(exc),
                "required_consents": [ConsentType.SENSITIVE_HEALTH_ANALYSIS.value],
            },
        ) from exc


@router.post(
    "/weight",
    response_model=WeightPredictionResponse,
    responses={
        200: {"content": {"application/json": {"examples": WEIGHT_PREDICTION_RESPONSE_EXAMPLES}}},
        401: {"content": {"application/json": {"examples": UNAUTHORIZED_EXAMPLE}}},
        403: {"content": {"application/json": {"examples": CONSENT_REQUIRED_EXAMPLE}}},
        422: {"content": {"application/json": {"examples": UNPROCESSABLE_ENTITY_EXAMPLE}}},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.ANALYSIS_READ,),
        consents=(ConsentType.SENSITIVE_HEALTH_ANALYSIS,),
        contract_status=P1_5_DEFICIENCY_DASHBOARD_READY_STATUS,
    ),
)
async def predict_weight(
    request: Annotated[
        WeightPredictionRequest,
        Body(openapi_examples=WEIGHT_PREDICTION_REQUEST_EXAMPLES),
    ],
    http_request: Request,
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    current_user: Annotated[AuthenticatedUser, Depends(require_analysis_read)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WeightPredictionResponse:
    """1주/1개월/3개월 등 기간별 체중 변화를 예측한다.

    인증·동의·감사 게이트가 모두 통과한 사용자에 대해서만 계산하며,
    응답 직전 ``weight_prediction_compute`` audit event 1건을 기록한다.

    Args:
        request: 체중 예측 요청.
        http_request: Current FastAPI request (audit logging).
        session: Request-scoped async database session.
        current_user: Authenticated owner.
        settings: Application settings.

    Returns:
        기간별 체중 예측 결과.

    Raises:
        HTTPException: When SENSITIVE_HEALTH_ANALYSIS consent is missing (403).
    """
    await _require_sensitive_health_consent(
        session,
        current_user,
        http_request,
        settings,
        blocked_action="weight_prediction_compute_blocked",
        resource_type="weight_prediction",
    )
    derived_alcohol_kcal = 0.0
    if request.alcohol_volume_ml > 0 and request.alcohol_abv_percent is not None:
        derived_alcohol_kcal = calculate_alcohol_kcal_from_volume(
            volume_ml=request.alcohol_volume_ml,
            abv_percent=request.alcohol_abv_percent,
        )
    response = predict_weight_periods_selected(
        weight_kg=request.weight_kg,
        height_cm=request.height_cm,
        age=request.age,
        sex=request.sex,
        daily_steps=request.daily_steps,
        daily_intake_kcal=request.daily_intake_kcal,
        periods_days=request.periods_days,
        body_fat_pct=request.body_fat_pct,
        alcohol_kcal=request.alcohol_kcal + derived_alcohol_kcal,
        walking_cadence_steps_per_min=request.walking_cadence_steps_per_min,
        walking_cadence_minutes=request.walking_cadence_minutes,
        exercise_average_heart_rate_bpm=request.exercise_average_heart_rate_bpm,
        heart_rate_exercise_minutes=request.heart_rate_exercise_minutes,
        chronic_diseases=request.chronic_diseases,
        prediction_checkins=request.prediction_checkins,
        feature_hall_lite_weight_prediction=settings.feature_hall_lite_weight_prediction,
        weight_prediction_engine=settings.weight_prediction_engine,
    )
    await record_sensitive_audit_event(
        session,
        current_user,
        action="weight_prediction_compute",
        resource_type="weight_prediction",
        resource_id=None,
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={
            "periods_days": list(request.periods_days),
            "engine": settings.weight_prediction_engine,
            "prediction_status": response.prediction_status,
            "prediction_checkin_count": len(request.prediction_checkins),
            "walking_cadence_used": request.walking_cadence_steps_per_min is not None,
            "exercise_heart_rate_used": request.exercise_average_heart_rate_bpm is not None,
        },
    )
    return response
