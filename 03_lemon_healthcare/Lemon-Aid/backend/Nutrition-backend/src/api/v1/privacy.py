"""Privacy, consent, deletion, and audit API routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings, get_settings
from src.db.dependencies import get_rls_context_session
from src.models.schemas.privacy import (
    ConsentActionResponse,
    ConsentStateResponse,
    ConsentType,
    DeletionRequestCreate,
    DeletionRequestResponse,
)
from src.security.auth import (
    AuthenticatedUser,
    require_privacy_delete,
    require_privacy_read,
    require_privacy_write,
)
from src.services.privacy import (
    consent_record_to_action_response,
    create_delete_all_user_data_request,
    deletion_request_to_response,
    get_consent_state,
    get_deletion_request,
    grant_consent,
    record_audit_event,
    revoke_consent,
)

router = APIRouter(prefix="/me", tags=["privacy"])


@router.get("/privacy/consents", response_model=ConsentStateResponse)
async def get_current_user_consents(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    current_user: Annotated[AuthenticatedUser, Depends(require_privacy_read)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ConsentStateResponse:
    """Return the current user's active consent state.

    Args:
        session: Request-scoped async database session.
        request: Current FastAPI request.
        current_user: Authenticated owner.
        settings: Application settings.

    Returns:
        Active policy consent states.
    """
    response = await get_consent_state(session, current_user)
    await record_audit_event(
        session,
        current_user,
        action="consent_state_read",
        resource_type="consent",
        resource_id=None,
        outcome="success",
        request=request,
        settings=settings,
        event_metadata={"count": len(response.consents)},
    )
    return response


@router.post(
    "/privacy/consents/{consent_type}",
    response_model=ConsentActionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def grant_current_user_consent(
    consent_type: ConsentType,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    current_user: Annotated[AuthenticatedUser, Depends(require_privacy_write)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ConsentActionResponse:
    """Grant one consent bucket for the current user.

    Args:
        consent_type: Consent bucket to grant.
        request: Current FastAPI request.
        session: Request-scoped async database session.
        current_user: Authenticated owner.
        settings: Application settings.

    Returns:
        Persisted consent grant event.
    """
    record = await grant_consent(session, current_user, consent_type, request, settings)
    return consent_record_to_action_response(record)


@router.delete("/privacy/consents/{consent_type}", response_model=ConsentActionResponse)
async def revoke_current_user_consent(
    consent_type: ConsentType,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    current_user: Annotated[AuthenticatedUser, Depends(require_privacy_write)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ConsentActionResponse:
    """Revoke one consent bucket for the current user.

    Args:
        consent_type: Consent bucket to revoke.
        request: Current FastAPI request.
        session: Request-scoped async database session.
        current_user: Authenticated owner.
        settings: Application settings.

    Returns:
        Persisted consent revocation event.
    """
    record = await revoke_consent(session, current_user, consent_type, request, settings)
    return consent_record_to_action_response(record)


@router.post(
    "/data-deletion-requests",
    response_model=DeletionRequestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_current_user_data_deletion_request(
    payload: DeletionRequestCreate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    current_user: Annotated[AuthenticatedUser, Depends(require_privacy_delete)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DeletionRequestResponse:
    """Create and immediately process a current-user deletion request.

    Args:
        payload: Deletion request payload.
        request: Current FastAPI request.
        session: Request-scoped async database session.
        current_user: Authenticated owner.
        settings: Application settings.

    Returns:
        Processed deletion request.
    """
    if payload.request_type.value != "all_user_data":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Unsupported deletion request type.",
        )

    deletion_request = await create_delete_all_user_data_request(
        session,
        current_user,
        request,
        settings,
    )
    return deletion_request_to_response(deletion_request)


@router.get(
    "/data-deletion-requests/{deletion_request_id}",
    response_model=DeletionRequestResponse,
)
async def get_current_user_data_deletion_request(
    deletion_request_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    current_user: Annotated[AuthenticatedUser, Depends(require_privacy_read)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DeletionRequestResponse:
    """Return one deletion request owned by the current user.

    Args:
        deletion_request_id: Deletion request identifier.
        request: Current FastAPI request.
        session: Request-scoped async database session.
        current_user: Authenticated owner.
        settings: Application settings.

    Returns:
        Owner-scoped deletion request.

    Raises:
        HTTPException: If the request is not found for this owner.
    """
    deletion_request = await get_deletion_request(
        session,
        current_user,
        deletion_request_id,
        settings,
    )
    if deletion_request is None:
        await record_audit_event(
            session,
            current_user,
            action="deletion_request_read",
            resource_type="deletion_request",
            resource_id=str(deletion_request_id),
            outcome="not_found",
            request=request,
            settings=settings,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deletion request not found.",
        )
    await record_audit_event(
        session,
        current_user,
        action="deletion_request_read",
        resource_type="deletion_request",
        resource_id=str(deletion_request_id),
        outcome="success",
        request=request,
        settings=settings,
    )
    return deletion_request_to_response(deletion_request)
