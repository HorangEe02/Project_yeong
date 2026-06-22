"""Reminder preference API routes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.contract import P1_7_AI_AGENT_DAILY_COACHING_READY_STATUS, route_contract
from src.api.v1.examples import (
    CONSENT_REQUIRED_EXAMPLE,
    UNAUTHORIZED_EXAMPLE,
    UNPROCESSABLE_ENTITY_EXAMPLE,
)
from src.config import Settings, get_settings
from src.db.dependencies import get_rls_context_session
from src.db.tx import persist_scope
from src.models.db.notification import ReminderPreference
from src.models.schemas.notification import (
    ReminderPreferenceCreate,
    ReminderPreferenceListResponse,
    ReminderPreferenceResponse,
    ReminderPreferenceUpdate,
)
from src.models.schemas.privacy import ConsentType
from src.security.auth import AuthenticatedUser, require_analysis_read, require_analysis_write
from src.security.scopes import ApiScope
from src.security.subjects import build_owner_subject
from src.services.privacy import (
    ConsentRequiredError,
    record_sensitive_audit_event,
    require_user_consent,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


class ReminderPreferenceNotFoundError(ValueError):
    """Raised when a current-user reminder preference does not exist."""


async def _require_sensitive_health_consent(
    session: AsyncSession,
    current_user: AuthenticatedUser,
    http_request: Request,
    settings: Settings,
) -> None:
    """Require sensitive-health consent before mutating health reminders."""
    try:
        await require_user_consent(session, current_user, ConsentType.SENSITIVE_HEALTH_ANALYSIS)
    except ConsentRequiredError as exc:
        await record_sensitive_audit_event(
            session,
            current_user,
            action="reminder_preference_blocked",
            resource_type="reminder_preference",
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


def reminder_preference_to_response(record: ReminderPreference) -> ReminderPreferenceResponse:
    """Convert a DB reminder preference row to the public response."""
    return ReminderPreferenceResponse(
        id=record.id,
        category=record.category,
        time_of_day=record.time_of_day,
        timezone=record.timezone,
        enabled=record.enabled,
        message=record.message,
        created_at=record.created_at,
        updated_at=record.updated_at,
        disabled_at=record.disabled_at,
    )


async def create_reminder_preference_service(
    session: AsyncSession,
    user: AuthenticatedUser,
    request: ReminderPreferenceCreate,
) -> ReminderPreferenceResponse:
    """Persist a current-user reminder preference."""
    record = ReminderPreference(
        owner_subject=build_owner_subject(user),
        category=request.category.value,
        time_of_day=request.time_of_day,
        timezone=request.timezone,
        enabled=request.enabled,
        message=request.message,
        preference_metadata=request.metadata,
        disabled_at=None if request.enabled else datetime.now(UTC),
    )
    async with persist_scope(session):
        session.add(record)
        await session.flush()
        await session.refresh(record)
    return reminder_preference_to_response(record)


async def list_reminder_preferences_service(
    session: AsyncSession,
    user: AuthenticatedUser,
) -> list[ReminderPreferenceResponse]:
    """List current-user reminder preferences."""
    result = await session.scalars(
        select(ReminderPreference)
        .where(ReminderPreference.owner_subject == build_owner_subject(user))
        .order_by(ReminderPreference.created_at.desc())
    )
    return [reminder_preference_to_response(record) for record in result.all()]


async def update_reminder_preference_service(
    session: AsyncSession,
    user: AuthenticatedUser,
    reminder_id: UUID,
    request: ReminderPreferenceUpdate,
) -> ReminderPreferenceResponse:
    """Update a current-user reminder preference."""
    record = await _get_current_user_reminder(session, user, reminder_id)
    if request.time_of_day is not None:
        record.time_of_day = request.time_of_day
    if request.timezone is not None:
        record.timezone = request.timezone
    if request.message is not None:
        record.message = request.message
    if request.metadata is not None:
        record.preference_metadata = request.metadata
    if request.enabled is not None:
        record.enabled = request.enabled
        record.disabled_at = None if request.enabled else datetime.now(UTC)
    async with persist_scope(session):
        await session.flush()
        await session.refresh(record)
    return reminder_preference_to_response(record)


async def disable_reminder_preference_service(
    session: AsyncSession,
    user: AuthenticatedUser,
    reminder_id: UUID,
) -> ReminderPreferenceResponse:
    """Disable a current-user reminder preference."""
    record = await _get_current_user_reminder(session, user, reminder_id)
    record.enabled = False
    record.disabled_at = datetime.now(UTC)
    async with persist_scope(session):
        await session.flush()
        await session.refresh(record)
    return reminder_preference_to_response(record)


def select_enabled_reminders_for_dispatch(
    reminders: list[ReminderPreferenceResponse],
) -> list[ReminderPreferenceResponse]:
    """Return reminders eligible for future dispatch planning."""
    return [reminder for reminder in reminders if reminder.enabled]


async def _get_current_user_reminder(
    session: AsyncSession,
    user: AuthenticatedUser,
    reminder_id: UUID,
) -> ReminderPreference:
    """Load one current-user reminder preference or raise."""
    record = await session.scalar(
        select(ReminderPreference).where(
            ReminderPreference.owner_subject == build_owner_subject(user),
            ReminderPreference.id == reminder_id,
        )
    )
    if record is None:
        raise ReminderPreferenceNotFoundError("Reminder preference not found.")
    return record


def _not_found_error() -> HTTPException:
    """Return a stable reminder not-found API error."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "reminder_not_found", "message": "Reminder preference not found."},
    )


@router.get(
    "/reminders",
    response_model=ReminderPreferenceListResponse,
    responses={
        401: {"content": {"application/json": {"examples": UNAUTHORIZED_EXAMPLE}}},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.ANALYSIS_READ,),
        contract_status=P1_7_AI_AGENT_DAILY_COACHING_READY_STATUS,
    ),
)
async def list_reminder_preferences(
    current_user: Annotated[AuthenticatedUser, Depends(require_analysis_read)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
) -> ReminderPreferenceListResponse:
    """List current-user reminder preferences."""
    return ReminderPreferenceListResponse(
        items=await list_reminder_preferences_service(session, current_user)
    )


@router.post(
    "/reminders",
    response_model=ReminderPreferenceResponse,
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
async def create_reminder_preference(
    http_request: Request,
    request: ReminderPreferenceCreate,
    current_user: Annotated[AuthenticatedUser, Depends(require_analysis_write)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReminderPreferenceResponse:
    """Create a current-user health reminder preference."""
    await _require_sensitive_health_consent(session, current_user, http_request, settings)
    response = await create_reminder_preference_service(session, current_user, request)
    await record_sensitive_audit_event(
        session,
        current_user,
        action="reminder_preference_created",
        resource_type="reminder_preference",
        resource_id=str(response.id),
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={"category": response.category.value, "enabled": response.enabled},
    )
    return response


@router.patch(
    "/reminders/{reminder_id}",
    response_model=ReminderPreferenceResponse,
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
async def update_reminder_preference(
    reminder_id: UUID,
    http_request: Request,
    request: ReminderPreferenceUpdate,
    current_user: Annotated[AuthenticatedUser, Depends(require_analysis_write)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReminderPreferenceResponse:
    """Update a current-user health reminder preference."""
    await _require_sensitive_health_consent(session, current_user, http_request, settings)
    try:
        response = await update_reminder_preference_service(
            session, current_user, reminder_id, request
        )
    except ReminderPreferenceNotFoundError as exc:
        raise _not_found_error() from exc
    await record_sensitive_audit_event(
        session,
        current_user,
        action="reminder_preference_updated",
        resource_type="reminder_preference",
        resource_id=str(response.id),
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={"category": response.category.value, "enabled": response.enabled},
    )
    return response


@router.post(
    "/reminders/{reminder_id}/disable",
    response_model=ReminderPreferenceResponse,
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
async def disable_reminder_preference(
    reminder_id: UUID,
    http_request: Request,
    current_user: Annotated[AuthenticatedUser, Depends(require_analysis_write)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReminderPreferenceResponse:
    """Disable a current-user health reminder preference."""
    await _require_sensitive_health_consent(session, current_user, http_request, settings)
    try:
        response = await disable_reminder_preference_service(session, current_user, reminder_id)
    except ReminderPreferenceNotFoundError as exc:
        raise _not_found_error() from exc
    await record_sensitive_audit_event(
        session,
        current_user,
        action="reminder_preference_disabled",
        resource_type="reminder_preference",
        resource_id=str(response.id),
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={"category": response.category.value},
    )
    return response
