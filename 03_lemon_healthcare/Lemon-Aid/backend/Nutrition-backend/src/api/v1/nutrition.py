"""영양 기준과 섭취 상태 분석 API 라우터."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.contract import P1_5_DEFICIENCY_DASHBOARD_READY_STATUS, route_contract
from src.api.v1.examples import (
    CONSENT_REQUIRED_EXAMPLE,
    INSUFFICIENT_SCOPE_EXAMPLE,
    KDRIS_LOOKUP_RESPONSE_EXAMPLES,
    NUTRITION_ANALYSIS_REQUEST_EXAMPLES,
    NUTRITION_ANALYSIS_RESPONSE_EXAMPLES,
    NUTRITION_DIAGNOSIS_LATEST_RESPONSE_EXAMPLES,
    UNAUTHORIZED_EXAMPLE,
    UNPROCESSABLE_ENTITY_EXAMPLE,
)
from src.config import Settings, get_settings
from src.db.dependencies import get_rls_context_session
from src.models.schemas.nutrition import (
    AuditKRRequest,
    AuditKRResponse,
    KDRILookupResponse,
    KDRIQuery,
    NutritionAnalysisRequest,
    NutritionAnalysisResponse,
    NutritionDiagnosisLatestResponse,
)
from src.models.schemas.privacy import ConsentType
from src.models.schemas.user import PregnancyStatus, Sex
from src.nutrition.audit_kr import score_audit_kr
from src.nutrition.deficiency_analysis import analyze_nutrient_intakes
from src.nutrition.kdris import get_kdris_dataset_context, get_kdris_for_profile
from src.nutrition.unit_converter import UnitConversionError
from src.security.auth import AuthenticatedUser, require_analysis_read
from src.security.scopes import ApiScope
from src.services.nutrition_diagnosis import get_latest_nutrition_diagnosis
from src.services.privacy import (
    ConsentRequiredError,
    record_sensitive_audit_event,
    require_user_consent,
)

router = APIRouter(prefix="/nutrition", tags=["nutrition"])


def _unprocessable(exc: Exception) -> HTTPException:
    """Build a validation exception for nutrition routes.

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
    """Require sensitive-health consent for current-user nutrition diagnosis reads.

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
            action="nutrition_diagnosis_read_blocked",
            resource_type="nutrition_diagnosis",
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
    "/kdris",
    response_model=KDRILookupResponse,
    responses={
        200: {"content": {"application/json": {"examples": KDRIS_LOOKUP_RESPONSE_EXAMPLES}}},
        422: {"content": {"application/json": {"examples": UNPROCESSABLE_ENTITY_EXAMPLE}}},
    },
)
async def lookup_kdris(
    age: Annotated[int, Query(ge=1, le=120, examples=[30])],
    sex: Annotated[Sex, Query(examples=["male"])],
    pregnancy_status: Annotated[PregnancyStatus, Query(examples=["none"])] = "none",
) -> KDRILookupResponse:
    """프로필 조건에 맞는 KDRIs 샘플 기준값을 조회한다.

    Args:
        age: 만 나이.
        sex: 성별.
        pregnancy_status: 임신/수유 상태.

    Returns:
        KDRIs 샘플 기준값 목록.
    """
    query = KDRIQuery(
        age=age,
        sex=sex,
        pregnancy_status=pregnancy_status,
    )
    dataset_context = get_kdris_dataset_context()
    return KDRILookupResponse(
        query=query,
        references=get_kdris_for_profile(
            age=age,
            sex=sex,
            pregnancy_status=pregnancy_status,
        ),
        dataset_status=dataset_context["dataset_status"],
        dataset_version=dataset_context["dataset_version"],
        source_manifest_version=dataset_context["source_manifest_version"],
    )


@router.post(
    "/analyze",
    response_model=NutritionAnalysisResponse,
    responses={
        200: {"content": {"application/json": {"examples": NUTRITION_ANALYSIS_RESPONSE_EXAMPLES}}},
        422: {"content": {"application/json": {"examples": UNPROCESSABLE_ENTITY_EXAMPLE}}},
    },
)
async def analyze_nutrition(
    request: Annotated[
        NutritionAnalysisRequest,
        Body(openapi_examples=NUTRITION_ANALYSIS_REQUEST_EXAMPLES),
    ],
) -> NutritionAnalysisResponse:
    """입력 섭취량을 KDRIs 샘플 기준값과 비교한다.

    Args:
        request: 영양소 섭취 상태 분석 요청.

    Returns:
        영양소별 섭취 상태 분석 결과.

    Raises:
        HTTPException: 기준값이 없거나 단위 환산이 불가능한 경우.
    """
    try:
        return analyze_nutrient_intakes(
            profile=request.profile,
            intakes=request.intakes,
        )
    except (UnitConversionError, ValueError) as exc:
        raise _unprocessable(exc) from exc


@router.post(
    "/audit-kr",
    response_model=AuditKRResponse,
    responses={
        422: {"content": {"application/json": {"examples": UNPROCESSABLE_ENTITY_EXAMPLE}}},
    },
)
async def score_audit_kr_self_check(request: AuditKRRequest) -> AuditKRResponse:
    """AUDIT-KR 10문항 점수를 합산하고 안전 라우팅 결과를 반환한다.

    Args:
        request: AUDIT-KR 10개 항목 점수.

    Returns:
        위험 음주/상담 우선 여부와 영양 우선 확인 항목.
    """
    return score_audit_kr(request)


@router.get(
    "/diagnosis/latest",
    response_model=NutritionDiagnosisLatestResponse,
    responses={
        200: {
            "content": {
                "application/json": {"examples": NUTRITION_DIAGNOSIS_LATEST_RESPONSE_EXAMPLES}
            }
        },
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
        scopes=(ApiScope.ANALYSIS_READ,),
        consents=(ConsentType.SENSITIVE_HEALTH_ANALYSIS,),
        contract_status=P1_5_DEFICIENCY_DASHBOARD_READY_STATUS,
    ),
)
async def get_latest_nutrition_diagnosis_for_user(
    http_request: Request,
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    current_user: Annotated[AuthenticatedUser, Depends(require_analysis_read)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> NutritionDiagnosisLatestResponse:
    """Return the latest persisted nutrition diagnosis for the current user.

    Args:
        http_request: Current FastAPI request.
        session: Request-scoped async database session.
        current_user: Authenticated owner.
        settings: Application settings.

    Returns:
        Latest nutrition diagnosis response or a not-ready response.

    Raises:
        HTTPException: If consent is missing or a persisted snapshot is invalid.
    """
    await _require_sensitive_health_consent(session, current_user, http_request, settings)
    try:
        response = await get_latest_nutrition_diagnosis(session, current_user)
    except ValueError as exc:
        raise _unprocessable(exc) from exc
    await record_sensitive_audit_event(
        session,
        current_user,
        action="nutrition_diagnosis_read",
        resource_type="nutrition_diagnosis",
        resource_id=str(response.result_id) if response.result_id else None,
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={
            "data_status": response.data_status,
            "deficient_or_low_count": response.summary.deficient_or_low_count,
            "excessive_or_risky_count": response.summary.excessive_or_risky_count,
        },
    )
    return response
