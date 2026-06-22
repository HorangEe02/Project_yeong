"""활동점수 API 라우터."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.algorithms.activity import calculate_activity_score
from src.api.v1.contract import P1_5_DEFICIENCY_DASHBOARD_READY_STATUS, route_contract
from src.api.v1.examples import (
    ACTIVITY_SCORE_REQUEST_EXAMPLES,
    ACTIVITY_SCORE_RESPONSE_EXAMPLES,
    CONSENT_REQUIRED_EXAMPLE,
    UNAUTHORIZED_EXAMPLE,
    UNPROCESSABLE_ENTITY_EXAMPLE,
)
from src.config import Settings, get_settings
from src.db.dependencies import get_rls_context_session
from src.models.schemas.algorithm import ActivityScoreRequest, ActivityScoreResponse
from src.models.schemas.privacy import ConsentType
from src.security.auth import AuthenticatedUser, require_analysis_read
from src.security.scopes import ApiScope
from src.services.privacy import (
    ConsentRequiredError,
    record_sensitive_audit_event,
    require_user_consent,
)

router = APIRouter(prefix="/activity", tags=["activity"])


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
    "/score",
    response_model=ActivityScoreResponse,
    responses={
        200: {"content": {"application/json": {"examples": ACTIVITY_SCORE_RESPONSE_EXAMPLES}}},
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
async def score_activity(
    request: Annotated[
        ActivityScoreRequest,
        Body(openapi_examples=ACTIVITY_SCORE_REQUEST_EXAMPLES),
    ],
    http_request: Request,
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    current_user: Annotated[AuthenticatedUser, Depends(require_analysis_read)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ActivityScoreResponse:
    """활동점수 v1-v4를 계산한다.

    인증·동의·감사 게이트가 모두 통과한 사용자에 대해서만 계산하며,
    응답 직전 ``activity_score_compute`` audit event 1건을 기록한다.

    Args:
        request: 활동점수 계산 요청.
        http_request: Current FastAPI request (audit logging).
        session: Request-scoped async database session.
        current_user: Authenticated owner.
        settings: Application settings.

    Returns:
        활동점수 계산 결과.

    Raises:
        HTTPException: When SENSITIVE_HEALTH_ANALYSIS consent is missing (403).
    """
    await _require_sensitive_health_consent(
        session,
        current_user,
        http_request,
        settings,
        blocked_action="activity_score_compute_blocked",
        resource_type="activity_score",
    )
    response = calculate_activity_score(request)
    await record_sensitive_audit_event(
        session,
        current_user,
        action="activity_score_compute",
        resource_type="activity_score",
        resource_id=None,
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={
            "bmi_category": response.bmi.category,
            "recommended_steps": response.recommended_steps,
        },
    )
    return response
