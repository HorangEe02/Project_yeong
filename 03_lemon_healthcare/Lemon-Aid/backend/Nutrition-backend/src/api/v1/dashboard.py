"""Dashboard API contract routes for P1 implementation."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.contract import P1_5_DEFICIENCY_DASHBOARD_READY_STATUS, route_contract
from src.api.v1.examples import (
    CONSENT_REQUIRED_EXAMPLE,
    DASHBOARD_SUMMARY_RESPONSE_EXAMPLES,
    INSUFFICIENT_SCOPE_EXAMPLE,
    UNAUTHORIZED_EXAMPLE,
    UNPROCESSABLE_ENTITY_EXAMPLE,
)
from src.config import Settings, get_settings
from src.db.dependencies import get_rls_context_session
from src.models.schemas.dashboard import DashboardSummaryResponse
from src.models.schemas.privacy import ConsentType
from src.security.auth import AuthenticatedUser, require_dashboard_read
from src.security.scopes import ApiScope
from src.services.dashboard import build_dashboard_summary
from src.services.privacy import (
    ConsentRequiredError,
    record_sensitive_audit_event,
    require_user_consent,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _unprocessable(exc: Exception) -> HTTPException:
    """Build a validation exception for dashboard routes.

    Args:
        exc: Original exception.

    Returns:
        HTTP 422 exception.
    """
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=str(exc),
    )


async def _require_sensitive_health_consent(
    session: AsyncSession,
    current_user: AuthenticatedUser,
    http_request: Request,
    settings: Settings,
) -> None:
    """Require sensitive-health consent before dashboard reads.

    Args:
        session: Request-scoped async database session.
        current_user: Authenticated owner.
        http_request: Current FastAPI request.
        settings: Application settings.

    Raises:
        HTTPException: If the required consent is missing.
    """
    try:
        await require_user_consent(session, current_user, ConsentType.SENSITIVE_HEALTH_ANALYSIS)
    except ConsentRequiredError as exc:
        await record_sensitive_audit_event(
            session,
            current_user,
            action="dashboard_summary_read_blocked",
            resource_type="dashboard_summary",
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


@router.get(
    "/summary",
    response_model=DashboardSummaryResponse,
    responses={
        200: {"content": {"application/json": {"examples": DASHBOARD_SUMMARY_RESPONSE_EXAMPLES}}},
        401: {"content": {"application/json": {"examples": UNAUTHORIZED_EXAMPLE}}},
        403: {
            "content": {
                "application/json": {
                    "examples": {
                        **INSUFFICIENT_SCOPE_EXAMPLE,
                        **CONSENT_REQUIRED_EXAMPLE,
                    }
                }
            }
        },
        422: {"content": {"application/json": {"examples": UNPROCESSABLE_ENTITY_EXAMPLE}}},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.DASHBOARD_READ,),
        consents=(ConsentType.SENSITIVE_HEALTH_ANALYSIS,),
        contract_status=P1_5_DEFICIENCY_DASHBOARD_READY_STATUS,
    ),
)
async def get_dashboard_summary(
    http_request: Request,
    current_user: Annotated[AuthenticatedUser, Depends(require_dashboard_read)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    as_of: Annotated[date | None, Query()] = None,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> DashboardSummaryResponse:
    """Return a current-user dashboard summary.

    Args:
        http_request: Current FastAPI request.
        current_user: Authenticated owner.
        session: Request-scoped async database session.
        settings: Application settings.
        as_of: Optional summary date.
        days: Lookback window in days.

    Returns:
        Dashboard summary response.

    Raises:
        HTTPException: If consent is missing or persisted snapshots are invalid.
    """
    await _require_sensitive_health_consent(session, current_user, http_request, settings)
    try:
        response = await build_dashboard_summary(session, current_user, as_of, days, settings)
    except ValueError as exc:
        raise _unprocessable(exc) from exc
    await record_sensitive_audit_event(
        session,
        current_user,
        action="dashboard_summary_read",
        resource_type="dashboard_summary",
        resource_id=None,
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={
            "nutrition_data_status": response.nutrition.data_status,
            "nutrition_low_count": response.nutrition.low_count,
            "nutrition_high_count": response.nutrition.high_count,
            "registered_supplement_count": response.supplements.registered_count,
            "requires_review_count": response.supplements.requires_review_count,
            "days": days,
        },
    )
    return response
