"""Current-user medication profile API routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.contract import P1_7_AI_AGENT_DAILY_COACHING_READY_STATUS, route_contract
from src.api.v1.examples import (
    CONSENT_REQUIRED_EXAMPLE,
    UNAUTHORIZED_EXAMPLE,
    UNPROCESSABLE_ENTITY_EXAMPLE,
)
from src.config import Settings, get_settings
from src.db.dependencies import get_rls_context_session
from src.models.schemas.privacy import ConsentType
from src.models.schemas.user_medication import (
    UserMedicationCreate,
    UserMedicationListResponse,
    UserMedicationResponse,
    UserMedicationUpdate,
)
from src.security.auth import AuthenticatedUser, require_analysis_read, require_analysis_write
from src.security.scopes import ApiScope
from src.services.privacy import (
    ConsentRequiredError,
    record_sensitive_audit_event,
    require_user_consent,
)
from src.services.user_medications import (
    UserMedicationNotFoundError,
    create_user_medication_service,
    deactivate_user_medication_service,
    list_user_medications_service,
    update_user_medication_service,
)

router = APIRouter(prefix="/me/medications", tags=["user-medications"])


async def _require_sensitive_health_consent(
    session: AsyncSession,
    current_user: AuthenticatedUser,
    http_request: Request,
    settings: Settings,
    *,
    blocked_action: str,
) -> None:
    """Require sensitive-health consent before using saved medication data."""
    try:
        await require_user_consent(session, current_user, ConsentType.SENSITIVE_HEALTH_ANALYSIS)
    except ConsentRequiredError as exc:
        await record_sensitive_audit_event(
            session,
            current_user,
            action=blocked_action,
            resource_type="user_medication",
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


def _not_found_error() -> HTTPException:
    """Return a stable medication not-found API error."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "user_medication_not_found", "message": "User medication not found."},
    )


@router.get(
    "",
    response_model=UserMedicationListResponse,
    responses={
        401: {"content": {"application/json": {"examples": UNAUTHORIZED_EXAMPLE}}},
        403: {"content": {"application/json": {"examples": CONSENT_REQUIRED_EXAMPLE}}},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.ANALYSIS_READ,),
        consents=(ConsentType.SENSITIVE_HEALTH_ANALYSIS,),
        contract_status=P1_7_AI_AGENT_DAILY_COACHING_READY_STATUS,
    ),
)
async def list_user_medications(
    http_request: Request,
    current_user: Annotated[AuthenticatedUser, Depends(require_analysis_read)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserMedicationListResponse:
    """List saved medication names for the current user."""
    await _require_sensitive_health_consent(
        session,
        current_user,
        http_request,
        settings,
        blocked_action="user_medication_list_blocked",
    )
    return UserMedicationListResponse(
        items=await list_user_medications_service(session, current_user, settings)
    )


@router.post(
    "",
    response_model=UserMedicationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"content": {"application/json": {"examples": UNAUTHORIZED_EXAMPLE}}},
        403: {"content": {"application/json": {"examples": CONSENT_REQUIRED_EXAMPLE}}},
        422: {"content": {"application/json": {"examples": UNPROCESSABLE_ENTITY_EXAMPLE}}},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.ANALYSIS_WRITE,),
        consents=(ConsentType.SENSITIVE_HEALTH_ANALYSIS,),
        contract_status=P1_7_AI_AGENT_DAILY_COACHING_READY_STATUS,
    ),
)
async def create_user_medication(
    http_request: Request,
    request: UserMedicationCreate,
    current_user: Annotated[AuthenticatedUser, Depends(require_analysis_write)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserMedicationResponse:
    """Save a user-confirmed medication name."""
    await _require_sensitive_health_consent(
        session,
        current_user,
        http_request,
        settings,
        blocked_action="user_medication_create_blocked",
    )
    response = await create_user_medication_service(session, current_user, settings, request)
    await record_sensitive_audit_event(
        session,
        current_user,
        action="user_medication_created",
        resource_type="user_medication",
        resource_id=str(response.id),
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={"is_active": response.is_active},
    )
    return response


@router.patch(
    "/{medication_id}",
    response_model=UserMedicationResponse,
    responses={
        401: {"content": {"application/json": {"examples": UNAUTHORIZED_EXAMPLE}}},
        403: {"content": {"application/json": {"examples": CONSENT_REQUIRED_EXAMPLE}}},
        422: {"content": {"application/json": {"examples": UNPROCESSABLE_ENTITY_EXAMPLE}}},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.ANALYSIS_WRITE,),
        consents=(ConsentType.SENSITIVE_HEALTH_ANALYSIS,),
        contract_status=P1_7_AI_AGENT_DAILY_COACHING_READY_STATUS,
    ),
)
async def update_user_medication(
    medication_id: UUID,
    http_request: Request,
    request: UserMedicationUpdate,
    current_user: Annotated[AuthenticatedUser, Depends(require_analysis_write)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserMedicationResponse:
    """Update a saved medication row."""
    await _require_sensitive_health_consent(
        session,
        current_user,
        http_request,
        settings,
        blocked_action="user_medication_update_blocked",
    )
    try:
        response = await update_user_medication_service(
            session,
            current_user,
            settings,
            medication_id,
            request,
        )
    except UserMedicationNotFoundError as exc:
        raise _not_found_error() from exc
    await record_sensitive_audit_event(
        session,
        current_user,
        action="user_medication_updated",
        resource_type="user_medication",
        resource_id=str(response.id),
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={"is_active": response.is_active},
    )
    return response


@router.post(
    "/{medication_id}/deactivate",
    response_model=UserMedicationResponse,
    responses={
        401: {"content": {"application/json": {"examples": UNAUTHORIZED_EXAMPLE}}},
        403: {"content": {"application/json": {"examples": CONSENT_REQUIRED_EXAMPLE}}},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.ANALYSIS_WRITE,),
        consents=(ConsentType.SENSITIVE_HEALTH_ANALYSIS,),
        contract_status=P1_7_AI_AGENT_DAILY_COACHING_READY_STATUS,
    ),
)
async def deactivate_user_medication(
    medication_id: UUID,
    http_request: Request,
    current_user: Annotated[AuthenticatedUser, Depends(require_analysis_write)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserMedicationResponse:
    """Deactivate a saved medication row."""
    await _require_sensitive_health_consent(
        session,
        current_user,
        http_request,
        settings,
        blocked_action="user_medication_deactivate_blocked",
    )
    try:
        response = await deactivate_user_medication_service(
            session,
            current_user,
            settings,
            medication_id,
        )
    except UserMedicationNotFoundError as exc:
        raise _not_found_error() from exc
    await record_sensitive_audit_event(
        session,
        current_user,
        action="user_medication_deactivated",
        resource_type="user_medication",
        resource_id=str(response.id),
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={"is_active": response.is_active},
    )
    return response
