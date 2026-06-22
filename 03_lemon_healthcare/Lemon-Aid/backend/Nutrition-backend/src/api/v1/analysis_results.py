"""Persisted analysis result API routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.examples import (
    ACTIVITY_SCORE_REQUEST_EXAMPLES,
    NUTRITION_ANALYSIS_REQUEST_EXAMPLES,
    UNPROCESSABLE_ENTITY_EXAMPLE,
    WEIGHT_PREDICTION_REQUEST_EXAMPLES,
)
from src.config import Settings, get_settings
from src.db.dependencies import get_rls_context_session
from src.models.schemas.algorithm import ActivityScoreRequest, WeightPredictionRequest
from src.models.schemas.analysis_result import (
    AnalysisResultListResponse,
    AnalysisResultResponse,
    AnalysisType,
)
from src.models.schemas.nutrition import NutritionAnalysisRequest
from src.nutrition.unit_converter import UnitConversionError
from src.security.auth import (
    AuthenticatedUser,
    require_analysis_delete,
    require_analysis_read,
    require_analysis_write,
)
from src.services.analysis_results import (
    analysis_result_to_response,
    analysis_result_to_summary,
    get_analysis_result,
    list_analysis_results,
    store_activity_score_result,
    store_nutrition_analysis_result,
    store_weight_prediction_result,
)
from src.services.privacy import (
    SENSITIVE_HEALTH_CONSENT,
    ConsentRequiredError,
    delete_analysis_result_for_user,
    record_sensitive_audit_event,
    require_user_consent,
)

router = APIRouter(prefix="/analysis-results", tags=["analysis-results"])


def _unprocessable(exc: Exception) -> HTTPException:
    """Build a validation exception for analysis persistence routes.

    Args:
        exc: Original exception.

    Returns:
        HTTP 422 exception with safe detail text.
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
    """Require active sensitive-health consent for analysis result storage.

    Args:
        session: Request-scoped async database session.
        current_user: Authenticated owner.
        http_request: Current FastAPI request.
        settings: Application settings.

    Raises:
        HTTPException: If the required consent is missing.
    """
    try:
        await require_user_consent(session, current_user, SENSITIVE_HEALTH_CONSENT)
    except ConsentRequiredError as exc:
        await record_sensitive_audit_event(
            session,
            current_user,
            action="analysis_result_create_blocked",
            resource_type="analysis_result",
            resource_id=None,
            outcome="blocked",
            request=http_request,
            settings=settings,
            event_metadata={"missing_consent": SENSITIVE_HEALTH_CONSENT.value},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


@router.post(
    "/activity-score",
    response_model=AnalysisResultResponse,
    status_code=status.HTTP_201_CREATED,
    responses={422: {"content": {"application/json": {"examples": UNPROCESSABLE_ENTITY_EXAMPLE}}}},
)
async def create_activity_score_result(
    http_request: Request,
    request: Annotated[
        ActivityScoreRequest,
        Body(openapi_examples=ACTIVITY_SCORE_REQUEST_EXAMPLES),
    ],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    current_user: Annotated[AuthenticatedUser, Depends(require_analysis_write)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AnalysisResultResponse:
    """Compute and persist an activity score result for the current user.

    Args:
        request: Activity score request.
        http_request: Current FastAPI request.
        session: Request-scoped async database session.
        current_user: Authenticated owner.
        settings: Application settings.

    Returns:
        Persisted result metadata and server-computed output snapshot.
    """
    await _require_sensitive_health_consent(session, current_user, http_request, settings)
    try:
        record = await store_activity_score_result(session, current_user, request)
    except ValueError as exc:
        raise _unprocessable(exc) from exc
    await record_sensitive_audit_event(
        session,
        current_user,
        action="analysis_result_created",
        resource_type="analysis_result",
        resource_id=str(record.id),
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={"analysis_type": AnalysisType.ACTIVITY_SCORE.value},
    )
    return analysis_result_to_response(record)


@router.post(
    "/weight-prediction",
    response_model=AnalysisResultResponse,
    status_code=status.HTTP_201_CREATED,
    responses={422: {"content": {"application/json": {"examples": UNPROCESSABLE_ENTITY_EXAMPLE}}}},
)
async def create_weight_prediction_result(
    http_request: Request,
    request: Annotated[
        WeightPredictionRequest,
        Body(openapi_examples=WEIGHT_PREDICTION_REQUEST_EXAMPLES),
    ],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    current_user: Annotated[AuthenticatedUser, Depends(require_analysis_write)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AnalysisResultResponse:
    """Compute and persist a weight prediction result for the current user.

    Args:
        request: Weight prediction request.
        http_request: Current FastAPI request.
        session: Request-scoped async database session.
        current_user: Authenticated owner.
        settings: Application settings.

    Returns:
        Persisted result metadata and server-computed output snapshot.
    """
    await _require_sensitive_health_consent(session, current_user, http_request, settings)
    try:
        record = await store_weight_prediction_result(session, current_user, request)
    except ValueError as exc:
        raise _unprocessable(exc) from exc
    await record_sensitive_audit_event(
        session,
        current_user,
        action="analysis_result_created",
        resource_type="analysis_result",
        resource_id=str(record.id),
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={"analysis_type": AnalysisType.WEIGHT_PREDICTION.value},
    )
    return analysis_result_to_response(record)


@router.post(
    "/nutrition",
    response_model=AnalysisResultResponse,
    status_code=status.HTTP_201_CREATED,
    responses={422: {"content": {"application/json": {"examples": UNPROCESSABLE_ENTITY_EXAMPLE}}}},
)
async def create_nutrition_analysis_result(
    http_request: Request,
    request: Annotated[
        NutritionAnalysisRequest,
        Body(openapi_examples=NUTRITION_ANALYSIS_REQUEST_EXAMPLES),
    ],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    current_user: Annotated[AuthenticatedUser, Depends(require_analysis_write)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AnalysisResultResponse:
    """Compute and persist a nutrition analysis result for the current user.

    Args:
        request: Nutrition analysis request.
        http_request: Current FastAPI request.
        session: Request-scoped async database session.
        current_user: Authenticated owner.
        settings: Application settings.

    Returns:
        Persisted result metadata and server-computed output snapshot.

    Raises:
        HTTPException: If KDRIs lookup or unit conversion fails.
    """
    await _require_sensitive_health_consent(session, current_user, http_request, settings)
    try:
        record = await store_nutrition_analysis_result(session, current_user, request)
    except (UnitConversionError, ValueError) as exc:
        raise _unprocessable(exc) from exc
    await record_sensitive_audit_event(
        session,
        current_user,
        action="analysis_result_created",
        resource_type="analysis_result",
        resource_id=str(record.id),
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={"analysis_type": AnalysisType.NUTRITION_ANALYSIS.value},
    )
    return analysis_result_to_response(record)


@router.get("", response_model=AnalysisResultListResponse)
async def list_current_user_analysis_results(
    http_request: Request,
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    current_user: Annotated[AuthenticatedUser, Depends(require_analysis_read)],
    settings: Annotated[Settings, Depends(get_settings)],
    analysis_type: Annotated[AnalysisType | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AnalysisResultListResponse:
    """List persisted analysis results for the current user.

    Args:
        session: Request-scoped async database session.
        http_request: Current FastAPI request.
        current_user: Authenticated owner.
        settings: Application settings.
        analysis_type: Optional analysis type filter.
        limit: Maximum result count.
        offset: Result offset.

    Returns:
        Owner-scoped analysis result summaries.
    """
    try:
        records = await list_analysis_results(session, current_user, analysis_type, limit, offset)
    except ValueError as exc:
        raise _unprocessable(exc) from exc
    await record_sensitive_audit_event(
        session,
        current_user,
        action="analysis_result_listed",
        resource_type="analysis_result",
        resource_id=None,
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={
            "analysis_type": analysis_type.value if analysis_type else None,
            "count": len(records),
        },
    )
    return AnalysisResultListResponse(
        results=[analysis_result_to_summary(record) for record in records],
        limit=limit,
        offset=offset,
    )


@router.get("/{result_id}", response_model=AnalysisResultResponse)
async def get_current_user_analysis_result(
    result_id: UUID,
    http_request: Request,
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    current_user: Annotated[AuthenticatedUser, Depends(require_analysis_read)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AnalysisResultResponse:
    """Get one persisted analysis result for the current user.

    Args:
        result_id: Persisted result identifier.
        http_request: Current FastAPI request.
        session: Request-scoped async database session.
        current_user: Authenticated owner.
        settings: Application settings.

    Returns:
        Owner-scoped persisted result detail.

    Raises:
        HTTPException: If the result does not exist for this owner.
    """
    try:
        record = await get_analysis_result(session, current_user, result_id)
    except ValueError as exc:
        raise _unprocessable(exc) from exc
    if record is None:
        await record_sensitive_audit_event(
            session,
            current_user,
            action="analysis_result_read",
            resource_type="analysis_result",
            resource_id=str(result_id),
            outcome="not_found",
            request=http_request,
            settings=settings,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis result not found.",
        )
    await record_sensitive_audit_event(
        session,
        current_user,
        action="analysis_result_read",
        resource_type="analysis_result",
        resource_id=str(result_id),
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={"analysis_type": record.analysis_type},
    )
    return analysis_result_to_response(record)


@router.delete("/{result_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_current_user_analysis_result(
    result_id: UUID,
    http_request: Request,
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    current_user: Annotated[AuthenticatedUser, Depends(require_analysis_delete)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """Delete one persisted analysis result for the current user.

    Args:
        result_id: Persisted result identifier.
        http_request: Current FastAPI request.
        session: Request-scoped async database session.
        current_user: Authenticated owner.
        settings: Application settings.

    Returns:
        Empty 204 response when deleted.

    Raises:
        HTTPException: If the result does not exist for this owner.
    """
    deleted = await delete_analysis_result_for_user(
        session,
        current_user,
        result_id,
        http_request,
        settings,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis result not found.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
