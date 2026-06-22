"""Health data API contract routes for P1 implementation."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.contract import P1_6_HEALTH_SYNC_READY_STATUS, route_contract
from src.api.v1.examples import (
    CONSENT_REQUIRED_EXAMPLE,
    HEALTH_SYNC_CONFLICT_EXAMPLE,
    HEALTH_SYNC_REQUEST_EXAMPLES,
    HEALTH_SYNC_RESPONSE_EXAMPLES,
    UNAUTHORIZED_EXAMPLE,
    UNPROCESSABLE_ENTITY_EXAMPLE,
)
from src.config import Settings, get_settings
from src.db.dependencies import get_rls_context_session
from src.models.schemas.health import (
    BodyProfileSnapshotCreate,
    BodyProfileSnapshotResponse,
    EmptyLatestBodyProfileResponse,
    HealthDailySummaryListResponse,
    HealthMetricSampleCreate,
    HealthMetricSampleResponse,
    HealthSyncRequest,
    HealthSyncResponse,
)
from src.models.schemas.privacy import ConsentType
from src.security.auth import AuthenticatedUser, require_health_read, require_health_write
from src.security.scopes import ApiScope
from src.services.health_profile import (
    HealthProfileConflictError,
    body_profile_to_response,
    create_body_profile_snapshot,
    create_health_metric_sample,
    daily_summaries_to_response,
    get_latest_body_profile_snapshot,
    list_health_daily_summaries,
    metric_sample_to_response,
)
from src.services.health_sync import (
    HealthSyncConflictError,
    health_sync_result_audit_metadata,
    health_sync_result_to_response,
)
from src.services.health_sync import (
    sync_health_daily_aggregates as sync_health_daily_aggregates_service,
)
from src.services.privacy import (
    ConsentRequiredError,
    record_sensitive_audit_event,
    require_user_consent,
)

router = APIRouter(prefix="/health", tags=["health"])

HEALTH_AUTH_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"content": {"application/json": {"examples": UNAUTHORIZED_EXAMPLE}}},
    403: {"content": {"application/json": {"examples": CONSENT_REQUIRED_EXAMPLE}}},
    422: {"content": {"application/json": {"examples": UNPROCESSABLE_ENTITY_EXAMPLE}}},
}


async def _require_health_device_consent(
    session: AsyncSession,
    current_user: AuthenticatedUser,
    http_request: Request,
    settings: Settings,
) -> None:
    """Require health-device-data consent before storing aggregates.

    Args:
        session: Request-scoped async database session.
        current_user: Authenticated owner.
        http_request: Current FastAPI request.
        settings: Application settings.

    Raises:
        HTTPException: If the required consent is missing.
    """
    try:
        await require_user_consent(session, current_user, ConsentType.HEALTH_DEVICE_DATA)
    except ConsentRequiredError as exc:
        await record_sensitive_audit_event(
            session,
            current_user,
            action="health_sync_blocked",
            resource_type="health_sync_batch",
            resource_id=None,
            outcome="blocked",
            request=http_request,
            settings=settings,
            event_metadata={"missing_consent": ConsentType.HEALTH_DEVICE_DATA.value},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "consent_required",
                "message": str(exc),
                "required_consents": [ConsentType.HEALTH_DEVICE_DATA.value],
            },
        ) from exc


async def _require_sensitive_health_consent(
    session: AsyncSession,
    current_user: AuthenticatedUser,
    http_request: Request,
    settings: Settings,
    *,
    action: str,
    resource_type: str,
) -> None:
    """Require sensitive-health consent before profile or status operations.

    Args:
        session: Request-scoped async database session.
        current_user: Authenticated owner.
        http_request: Current FastAPI request.
        settings: Application settings.
        action: Audit action to record when blocked.
        resource_type: Audit resource type.

    Raises:
        HTTPException: If the required consent is missing.
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
    "/sync",
    response_model=HealthSyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {"content": {"application/json": {"examples": HEALTH_SYNC_RESPONSE_EXAMPLES}}},
        401: {"content": {"application/json": {"examples": UNAUTHORIZED_EXAMPLE}}},
        403: {"content": {"application/json": {"examples": CONSENT_REQUIRED_EXAMPLE}}},
        409: {"content": {"application/json": {"examples": HEALTH_SYNC_CONFLICT_EXAMPLE}}},
        422: {"content": {"application/json": {"examples": UNPROCESSABLE_ENTITY_EXAMPLE}}},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.HEALTH_WRITE,),
        consents=(ConsentType.HEALTH_DEVICE_DATA,),
        contract_status=P1_6_HEALTH_SYNC_READY_STATUS,
    ),
)
async def sync_health_daily_aggregates(
    http_request: Request,
    request: Annotated[
        HealthSyncRequest,
        Body(openapi_examples=HEALTH_SYNC_REQUEST_EXAMPLES),
    ],
    current_user: Annotated[AuthenticatedUser, Depends(require_health_write)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthSyncResponse:
    """Sync current-user health aggregates from the mobile app.

    Args:
        http_request: Current FastAPI request.
        request: Daily health aggregate records.
        current_user: Authenticated owner.
        session: Request-scoped async database session.
        settings: Application settings.

    Returns:
        Health sync acceptance summary.

    Raises:
        HTTPException: If consent is missing or the client batch id conflicts.
    """
    await _require_health_device_consent(session, current_user, http_request, settings)
    try:
        result = await sync_health_daily_aggregates_service(session, current_user, request)
    except HealthSyncConflictError as exc:
        await record_sensitive_audit_event(
            session,
            current_user,
            action="health_sync_conflict",
            resource_type="health_sync_batch",
            resource_id=None,
            outcome="blocked",
            request=http_request,
            settings=settings,
            event_metadata={"client_batch_id_present": request.client_batch_id is not None},
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "idempotency_conflict", "message": str(exc)},
        ) from exc

    await record_sensitive_audit_event(
        session,
        current_user,
        action="health_sync_completed",
        resource_type="health_sync_batch",
        resource_id=str(result.batch.id),
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata=health_sync_result_audit_metadata(result),
    )
    return health_sync_result_to_response(result)


@router.post(
    "/profile-snapshots",
    response_model=BodyProfileSnapshotResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        **HEALTH_AUTH_RESPONSES,
        201: {"description": "Current-user body profile snapshot created."},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.HEALTH_WRITE,),
        consents=(ConsentType.SENSITIVE_HEALTH_ANALYSIS,),
        contract_status="phase7_health_profile_api_ready",
    ),
)
async def create_profile_snapshot(
    http_request: Request,
    request: Annotated[BodyProfileSnapshotCreate, Body()],
    current_user: Annotated[AuthenticatedUser, Depends(require_health_write)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BodyProfileSnapshotResponse:
    """Create a versioned current-user body profile snapshot.

    Args:
        http_request: Current FastAPI request.
        request: Body profile snapshot payload.
        current_user: Authenticated owner.
        session: Request-scoped async database session.
        settings: Application settings.

    Returns:
        Persisted profile snapshot without owner identifiers or consent snapshots.

    Raises:
        HTTPException: If sensitive-health consent is missing.
    """
    await _require_sensitive_health_consent(
        session,
        current_user,
        http_request,
        settings,
        action="body_profile_snapshot_blocked",
        resource_type="body_profile_snapshot",
    )
    snapshot = await create_body_profile_snapshot(session, current_user, request)
    await record_sensitive_audit_event(
        session,
        current_user,
        action="body_profile_snapshot_created",
        resource_type="body_profile_snapshot",
        resource_id=str(snapshot.id),
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={
            "source": snapshot.source,
            "has_birth_year": snapshot.birth_year is not None,
            "has_height_cm": snapshot.height_cm is not None,
            "has_weight_kg": snapshot.weight_kg is not None,
            "has_waist_cm": snapshot.waist_cm is not None,
        },
    )
    return body_profile_to_response(snapshot)


@router.get(
    "/profile-snapshots/latest",
    response_model=BodyProfileSnapshotResponse | EmptyLatestBodyProfileResponse,
    responses={
        **HEALTH_AUTH_RESPONSES,
        200: {"description": "Latest current-user body profile snapshot."},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.HEALTH_READ,),
        consents=(ConsentType.SENSITIVE_HEALTH_ANALYSIS,),
        contract_status="phase7_health_profile_api_ready",
    ),
)
async def get_latest_profile_snapshot(
    http_request: Request,
    current_user: Annotated[AuthenticatedUser, Depends(require_health_read)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BodyProfileSnapshotResponse | EmptyLatestBodyProfileResponse:
    """Return the latest current-user body profile snapshot.

    Args:
        http_request: Current FastAPI request.
        current_user: Authenticated owner.
        session: Request-scoped async database session.
        settings: Application settings.

    Returns:
        Latest profile snapshot, or a not-ready marker when none exists.

    Raises:
        HTTPException: If sensitive-health consent is missing.
    """
    await _require_sensitive_health_consent(
        session,
        current_user,
        http_request,
        settings,
        action="body_profile_snapshot_read_blocked",
        resource_type="body_profile_snapshot",
    )
    snapshot = await get_latest_body_profile_snapshot(session, current_user)
    await record_sensitive_audit_event(
        session,
        current_user,
        action="body_profile_snapshot_read",
        resource_type="body_profile_snapshot",
        resource_id=str(snapshot.id) if snapshot is not None else None,
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={"found": snapshot is not None},
    )
    if snapshot is None:
        return EmptyLatestBodyProfileResponse()
    return body_profile_to_response(snapshot)


@router.post(
    "/metric-samples",
    response_model=HealthMetricSampleResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        **HEALTH_AUTH_RESPONSES,
        201: {"description": "Current-user point-in-time health metric sample created."},
        409: {"description": "source_record_hash was already used for a different metric."},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.HEALTH_WRITE,),
        consents=(ConsentType.HEALTH_DEVICE_DATA,),
        contract_status="phase7_health_metric_api_ready",
    ),
)
async def create_metric_sample(
    http_request: Request,
    request: Annotated[HealthMetricSampleCreate, Body()],
    current_user: Annotated[AuthenticatedUser, Depends(require_health_write)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthMetricSampleResponse:
    """Create or reuse a current-user point-in-time health metric sample.

    Args:
        http_request: Current FastAPI request.
        request: Health metric sample payload.
        current_user: Authenticated owner.
        session: Request-scoped async database session.
        settings: Application settings.

    Returns:
        Metric sample response without owner identifiers or source hashes.

    Raises:
        HTTPException: If consent is missing or the idempotency hash conflicts.
    """
    await _require_health_device_consent(session, current_user, http_request, settings)
    try:
        sample = await create_health_metric_sample(session, current_user, request)
    except HealthProfileConflictError as exc:
        await record_sensitive_audit_event(
            session,
            current_user,
            action="health_metric_sample_conflict",
            resource_type="health_metric_sample",
            resource_id=None,
            outcome="blocked",
            request=http_request,
            settings=settings,
            event_metadata={"source_record_hash_present": request.source_record_hash is not None},
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "idempotency_conflict", "message": str(exc)},
        ) from exc
    await record_sensitive_audit_event(
        session,
        current_user,
        action="health_metric_sample_created",
        resource_type="health_metric_sample",
        resource_id=str(sample.id),
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={
            "metric_type": sample.metric_type,
            "unit": sample.unit,
            "source_platform": sample.source_platform,
            "quality_flag_count": len(sample.quality_flags or []),
            "source_record_hash_present": sample.source_record_hash is not None,
        },
    )
    return metric_sample_to_response(sample)


@router.get(
    "/daily-summary",
    response_model=HealthDailySummaryListResponse,
    responses={
        **HEALTH_AUTH_RESPONSES,
        200: {"description": "Current-user daily health summaries."},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.HEALTH_READ,),
        consents=(ConsentType.HEALTH_DEVICE_DATA,),
        contract_status="phase7_health_daily_summary_api_ready",
    ),
)
async def get_daily_summary(
    http_request: Request,
    current_user: Annotated[AuthenticatedUser, Depends(require_health_read)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=366)] = 31,
) -> HealthDailySummaryListResponse:
    """Return current-user daily health summaries.

    Args:
        http_request: Current FastAPI request.
        current_user: Authenticated owner.
        session: Request-scoped async database session.
        settings: Application settings.
        start_date: Optional inclusive start date.
        end_date: Optional inclusive end date.
        limit: Maximum rows to return.

    Returns:
        Daily summary list without owner identifiers or source hashes.

    Raises:
        HTTPException: If consent is missing or the date range is invalid.
    """
    await _require_health_device_consent(session, current_user, http_request, settings)
    try:
        summaries = await list_health_daily_summaries(
            session,
            current_user,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    await record_sensitive_audit_event(
        session,
        current_user,
        action="health_daily_summary_read",
        resource_type="health_daily_summary",
        resource_id=None,
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={
            "summary_count": len(summaries),
            "start_date_present": start_date is not None,
            "end_date_present": end_date is not None,
        },
    )
    return daily_summaries_to_response(summaries)
