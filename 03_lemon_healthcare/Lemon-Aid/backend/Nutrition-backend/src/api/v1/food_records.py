"""Current-user food record API routes."""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.contract import P1_7_AI_AGENT_DAILY_COACHING_READY_STATUS, route_contract
from src.api.v1.examples import (
    CONSENT_REQUIRED_EXAMPLE,
    UNAUTHORIZED_EXAMPLE,
    UNPROCESSABLE_ENTITY_EXAMPLE,
)
from src.config import Settings, get_settings
from src.db.dependencies import get_rls_context_session
from src.models.schemas.food_record import (
    FoodRecordCreate,
    FoodRecordListResponse,
    FoodRecordResponse,
    FoodRecordUpdate,
)
from src.models.schemas.privacy import ConsentType
from src.security.auth import AuthenticatedUser, require_analysis_read, require_analysis_write
from src.security.scopes import ApiScope
from src.services.food_records import (
    FoodRecordNotFoundError,
    create_food_record_service,
    delete_food_record_service,
    list_food_records_service,
    update_food_record_service,
)
from src.services.privacy import (
    ConsentRequiredError,
    record_sensitive_audit_event,
    require_user_consent,
)

router = APIRouter(prefix="/me/food-records", tags=["food-records"])


async def _require_sensitive_health_consent(
    session: AsyncSession,
    current_user: AuthenticatedUser,
    http_request: Request,
    settings: Settings,
    *,
    blocked_action: str,
) -> None:
    try:
        await require_user_consent(session, current_user, ConsentType.SENSITIVE_HEALTH_ANALYSIS)
    except ConsentRequiredError as exc:
        await record_sensitive_audit_event(
            session,
            current_user,
            action=blocked_action,
            resource_type="food_record",
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
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "food_record_not_found", "message": "Food record not found."},
    )


@router.get(
    "",
    response_model=FoodRecordListResponse,
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
async def list_food_records(
    http_request: Request,
    current_user: Annotated[AuthenticatedUser, Depends(require_analysis_read)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> FoodRecordListResponse:
    await _require_sensitive_health_consent(
        session,
        current_user,
        http_request,
        settings,
        blocked_action="food_record_list_blocked",
    )
    return FoodRecordListResponse(
        items=await list_food_records_service(
            session,
            current_user,
            settings,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )
    )


@router.post(
    "",
    response_model=FoodRecordResponse,
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
async def create_food_record(
    http_request: Request,
    request: FoodRecordCreate,
    current_user: Annotated[AuthenticatedUser, Depends(require_analysis_write)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> FoodRecordResponse:
    await _require_sensitive_health_consent(
        session,
        current_user,
        http_request,
        settings,
        blocked_action="food_record_create_blocked",
    )
    response = await create_food_record_service(session, current_user, settings, request)
    await record_sensitive_audit_event(
        session,
        current_user,
        action="food_record_created",
        resource_type="food_record",
        resource_id=str(response.id),
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={"meal_type": response.meal_type, "source": response.source},
    )
    return response


@router.patch(
    "/{food_record_id}",
    response_model=FoodRecordResponse,
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
async def update_food_record(
    food_record_id: UUID,
    http_request: Request,
    request: FoodRecordUpdate,
    current_user: Annotated[AuthenticatedUser, Depends(require_analysis_write)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> FoodRecordResponse:
    await _require_sensitive_health_consent(
        session,
        current_user,
        http_request,
        settings,
        blocked_action="food_record_update_blocked",
    )
    try:
        response = await update_food_record_service(
            session,
            current_user,
            settings,
            food_record_id,
            request,
        )
    except FoodRecordNotFoundError as exc:
        raise _not_found_error() from exc
    await record_sensitive_audit_event(
        session,
        current_user,
        action="food_record_updated",
        resource_type="food_record",
        resource_id=str(response.id),
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={"meal_type": response.meal_type, "source": response.source},
    )
    return response


@router.delete(
    "/{food_record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"content": {"application/json": {"examples": UNAUTHORIZED_EXAMPLE}}},
        403: {"content": {"application/json": {"examples": CONSENT_REQUIRED_EXAMPLE}}},
        404: {"description": "Food record not found."},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.ANALYSIS_WRITE,),
        consents=(ConsentType.SENSITIVE_HEALTH_ANALYSIS,),
        contract_status=P1_7_AI_AGENT_DAILY_COACHING_READY_STATUS,
    ),
)
async def delete_food_record(
    food_record_id: UUID,
    http_request: Request,
    current_user: Annotated[AuthenticatedUser, Depends(require_analysis_write)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    await _require_sensitive_health_consent(
        session,
        current_user,
        http_request,
        settings,
        blocked_action="food_record_delete_blocked",
    )
    try:
        await delete_food_record_service(session, current_user, settings, food_record_id)
    except FoodRecordNotFoundError as exc:
        raise _not_found_error() from exc
    await record_sensitive_audit_event(
        session,
        current_user,
        action="food_record_deleted",
        resource_type="food_record",
        resource_id=str(food_record_id),
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
