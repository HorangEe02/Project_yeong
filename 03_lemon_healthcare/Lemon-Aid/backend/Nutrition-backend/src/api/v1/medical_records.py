"""Current-user medical record and patient status routes."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.contract import route_contract
from src.api.v1.examples import CONSENT_REQUIRED_EXAMPLE, UNAUTHORIZED_EXAMPLE
from src.config import Settings, get_settings
from src.db.dependencies import get_rls_context_session
from src.models.schemas.medical import (
    MedicalRecordConfirmRequest,
    MedicalRecordCreateRequest,
    MedicalRecordListResponse,
    MedicalRecordResponse,
    PatientStatusSnapshotCreate,
    PatientStatusSnapshotResponse,
)
from src.models.schemas.privacy import ConsentType
from src.security.auth import (
    AuthenticatedUser,
    require_medical_read,
    require_medical_write,
)
from src.security.scopes import ApiScope
from src.services.medical_records import (
    MedicalRecordNotFoundError,
    MedicalRecordStateError,
    confirm_medical_record,
    create_medical_record,
    create_patient_status_snapshot,
    get_latest_patient_status_snapshot,
    list_medical_records,
    medical_record_to_response,
    medical_records_to_response,
    patient_status_to_response,
)
from src.services.privacy import (
    ConsentRequiredError,
    record_sensitive_audit_event,
    require_user_consent,
)

router = APIRouter(tags=["medical-records"])

MEDICAL_AUTH_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"content": {"application/json": {"examples": UNAUTHORIZED_EXAMPLE}}},
    403: {"content": {"application/json": {"examples": CONSENT_REQUIRED_EXAMPLE}}},
}


async def _require_sensitive_health_consent(
    *,
    session: AsyncSession,
    current_user: AuthenticatedUser,
    http_request: Request,
    settings: Settings,
    action: str,
    resource_type: str,
) -> None:
    """Require sensitive-health consent before medical record/status operations.

    Args:
        session: Request-scoped async database session.
        current_user: Authenticated owner.
        http_request: Current FastAPI request.
        settings: Application settings.
        action: Audit action to record when blocked.
        resource_type: Audit resource type.

    Raises:
        HTTPException: If sensitive-health consent is missing.
    """
    try:
        await require_user_consent(session, current_user, ConsentType.SENSITIVE_HEALTH_ANALYSIS)
    except ConsentRequiredError as exc:
        await record_sensitive_audit_event(
            session,
            current_user,
            action=action,
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
    "/medical-records",
    response_model=MedicalRecordResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        **MEDICAL_AUTH_RESPONSES,
        201: {"description": "Current-user medical record collection created."},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.MEDICAL_WRITE,),
        consents=(ConsentType.SENSITIVE_HEALTH_ANALYSIS,),
        contract_status="phase7_medical_records_api_ready",
    ),
)
async def create_current_user_medical_record(
    http_request: Request,
    request: Annotated[MedicalRecordCreateRequest, Body()],
    current_user: Annotated[AuthenticatedUser, Depends(require_medical_write)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MedicalRecordResponse:
    """Create a user-confirmed medical record collection.

    Args:
        http_request: Current FastAPI request.
        request: Medical record create payload.
        current_user: Authenticated owner.
        session: Request-scoped async database session.
        settings: Application settings.

    Returns:
        Medical record response without owner hash, consent snapshot, or source document id.

    Raises:
        HTTPException: If sensitive-health consent is missing.
    """
    await _require_sensitive_health_consent(
        session=session,
        current_user=current_user,
        http_request=http_request,
        settings=settings,
        action="medical_record_create_blocked",
        resource_type="medical_record_collection",
    )
    collection, conditions, medications = await create_medical_record(
        session,
        current_user,
        settings,
        request,
    )
    await record_sensitive_audit_event(
        session,
        current_user,
        action="medical_record_created",
        resource_type="medical_record_collection",
        resource_id=str(collection.id),
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={
            "record_type": collection.record_type,
            "source": collection.source,
            "status": collection.status,
            "condition_count": len(conditions),
            "medication_count": len(medications),
            "source_document_present": collection.source_document_id is not None,
        },
    )
    return medical_record_to_response(collection, conditions, medications)


@router.get(
    "/medical-records",
    response_model=MedicalRecordListResponse,
    responses={
        **MEDICAL_AUTH_RESPONSES,
        200: {"description": "Current-user medical record collections."},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.MEDICAL_READ,),
        consents=(ConsentType.SENSITIVE_HEALTH_ANALYSIS,),
        contract_status="phase7_medical_records_api_ready",
    ),
)
async def list_current_user_medical_records(
    http_request: Request,
    current_user: Annotated[AuthenticatedUser, Depends(require_medical_read)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    include_archived: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> MedicalRecordListResponse:
    """List current-user medical record collections.

    Args:
        http_request: Current FastAPI request.
        current_user: Authenticated owner.
        session: Request-scoped async database session.
        settings: Application settings.
        include_archived: Whether archived rows should be returned.
        limit: Maximum records to return.

    Returns:
        Medical record list without owner hashes, source document ids, or consent snapshots.

    Raises:
        HTTPException: If sensitive-health consent is missing.
    """
    await _require_sensitive_health_consent(
        session=session,
        current_user=current_user,
        http_request=http_request,
        settings=settings,
        action="medical_record_list_blocked",
        resource_type="medical_record_collection",
    )
    records = await list_medical_records(
        session,
        current_user,
        settings,
        include_archived=include_archived,
        limit=limit,
    )
    await record_sensitive_audit_event(
        session,
        current_user,
        action="medical_record_list_read",
        resource_type="medical_record_collection",
        resource_id=None,
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={"record_count": len(records), "include_archived": include_archived},
    )
    return medical_records_to_response(records)


@router.post(
    "/medical-records/{record_id}/confirm",
    response_model=MedicalRecordResponse,
    responses={
        **MEDICAL_AUTH_RESPONSES,
        200: {"description": "Medical record collection confirmed by the user."},
        404: {"description": "Medical record was not found."},
        409: {"description": "Medical record state does not allow confirmation."},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.MEDICAL_WRITE,),
        consents=(ConsentType.SENSITIVE_HEALTH_ANALYSIS,),
        contract_status="phase7_medical_records_api_ready",
    ),
)
async def confirm_current_user_medical_record(
    record_id: UUID,
    http_request: Request,
    request: Annotated[MedicalRecordConfirmRequest, Body()],
    current_user: Annotated[AuthenticatedUser, Depends(require_medical_write)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MedicalRecordResponse:
    """Confirm an existing current-user medical record collection.

    Args:
        record_id: Medical record collection id.
        http_request: Current FastAPI request.
        request: Confirmation payload.
        current_user: Authenticated owner.
        session: Request-scoped async database session.
        settings: Application settings.

    Returns:
        Confirmed medical record response.

    Raises:
        HTTPException: If consent is missing, the record is missing, or state is invalid.
    """
    await _require_sensitive_health_consent(
        session=session,
        current_user=current_user,
        http_request=http_request,
        settings=settings,
        action="medical_record_confirm_blocked",
        resource_type="medical_record_collection",
    )
    try:
        response = await confirm_medical_record(
            session,
            current_user,
            settings,
            record_id,
            request,
        )
    except MedicalRecordNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "medical_record_not_found", "message": str(exc)},
        ) from exc
    except MedicalRecordStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "medical_record_not_confirmable", "message": str(exc)},
        ) from exc
    await record_sensitive_audit_event(
        session,
        current_user,
        action="medical_record_confirmed",
        resource_type="medical_record_collection",
        resource_id=str(record_id),
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={"status": response.status.value},
    )
    return response


@router.post(
    "/patient/status",
    response_model=PatientStatusSnapshotResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        **MEDICAL_AUTH_RESPONSES,
        201: {"description": "Current-user non-diagnostic patient status snapshot created."},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.MEDICAL_WRITE,),
        consents=(ConsentType.SENSITIVE_HEALTH_ANALYSIS,),
        contract_status="phase7_patient_status_api_ready",
    ),
)
async def create_current_user_patient_status(
    http_request: Request,
    request: Annotated[PatientStatusSnapshotCreate, Body()],
    current_user: Annotated[AuthenticatedUser, Depends(require_medical_write)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PatientStatusSnapshotResponse:
    """Create a non-diagnostic current-user patient status snapshot.

    Args:
        http_request: Current FastAPI request.
        request: Patient status snapshot payload.
        current_user: Authenticated owner.
        session: Request-scoped async database session.
        settings: Application settings.

    Returns:
        Patient status response without owner hash or raw diagnostic fields.

    Raises:
        HTTPException: If sensitive-health consent is missing.
    """
    await _require_sensitive_health_consent(
        session=session,
        current_user=current_user,
        http_request=http_request,
        settings=settings,
        action="patient_status_create_blocked",
        resource_type="patient_status_snapshot",
    )
    snapshot = await create_patient_status_snapshot(session, current_user, settings, request)
    await record_sensitive_audit_event(
        session,
        current_user,
        action="patient_status_created",
        resource_type="patient_status_snapshot",
        resource_id=str(snapshot.id),
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={
            "summary_type": snapshot.summary_type,
            "data_quality": snapshot.data_quality,
            "risk_flag_count": len(snapshot.risk_flags or []),
            "generated_by": snapshot.generated_by,
        },
    )
    return patient_status_to_response(snapshot)


@router.get(
    "/patient/status/latest",
    response_model=PatientStatusSnapshotResponse,
    responses={
        **MEDICAL_AUTH_RESPONSES,
        200: {"description": "Latest non-diagnostic current-user patient status snapshot."},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.MEDICAL_READ,),
        consents=(ConsentType.SENSITIVE_HEALTH_ANALYSIS,),
        contract_status="phase7_patient_status_api_ready",
    ),
)
async def get_current_user_patient_status_latest(
    http_request: Request,
    current_user: Annotated[AuthenticatedUser, Depends(require_medical_read)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PatientStatusSnapshotResponse:
    """Return the latest non-diagnostic current-user patient status snapshot.

    Args:
        http_request: Current FastAPI request.
        current_user: Authenticated owner.
        session: Request-scoped async database session.
        settings: Application settings.

    Returns:
        Latest status snapshot, or a synthetic not-ready response.

    Raises:
        HTTPException: If sensitive-health consent is missing.
    """
    await _require_sensitive_health_consent(
        session=session,
        current_user=current_user,
        http_request=http_request,
        settings=settings,
        action="patient_status_read_blocked",
        resource_type="patient_status_snapshot",
    )
    response = await get_latest_patient_status_snapshot(session, current_user, settings)
    await record_sensitive_audit_event(
        session,
        current_user,
        action="patient_status_read",
        resource_type="patient_status_snapshot",
        resource_id=str(response.id) if response.id is not None else None,
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={"status": response.status, "data_quality": response.data_quality.value},
    )
    return response
