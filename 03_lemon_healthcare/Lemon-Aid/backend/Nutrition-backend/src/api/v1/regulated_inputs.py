"""Regulated prescription and lab OCR intake routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.contract import route_contract
from src.config import Settings, get_settings
from src.db.dependencies import get_rls_context_session
from src.models.schemas.privacy import ConsentType
from src.models.schemas.regulated import (
    LabResultOCRPreviewResponse,
    PrescriptionOCRPreviewResponse,
    RegulatedDocumentConfirmRequest,
    RegulatedDocumentConfirmResponse,
    RegulatedDocumentType,
)
from src.ocr.factory import OCRConfigurationError
from src.regulated.factory import build_regulated_ocr_adapters
from src.regulated.ocr_intake import (
    RegulatedDocumentConfigurationError,
    RegulatedDocumentExpiredError,
    RegulatedDocumentNotFoundError,
    RegulatedDocumentStateError,
    RegulatedDocumentTypeMismatchError,
    RegulatedImageValidationError,
    RegulatedMedicalOutputBlockedError,
    confirm_regulated_document,
    create_lab_result_ocr_preview,
    create_prescription_ocr_preview,
)
from src.security.auth import AuthenticatedUser, require_regulated_input_write
from src.security.scopes import ApiScope
from src.services.privacy import (
    ConsentRequiredError,
    record_sensitive_audit_event,
    require_user_consent,
)

router = APIRouter(prefix="/regulated-inputs", tags=["regulated-inputs"])


def _regulated_http_error(status_code: int, *, code: str, message: str) -> HTTPException:
    """Build a stable regulated input API error response.

    Args:
        status_code: HTTP status code.
        code: Stable application error code.
        message: Safe user-facing message.

    Returns:
        FastAPI HTTP exception.
    """
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _ensure_document_feature_enabled(
    settings: Settings,
    document_type: RegulatedDocumentType,
) -> None:
    """Fail closed when a regulated OCR intake feature flag is disabled.

    Args:
        settings: Runtime settings.
        document_type: Regulated document type.

    Raises:
        HTTPException: If the matching feature flag is disabled.
    """
    enabled = (
        settings.feature_prescription_ocr_intake
        if document_type == RegulatedDocumentType.PRESCRIPTION
        else settings.feature_lab_result_ocr_intake
    )
    if not enabled:
        raise _regulated_http_error(
            status.HTTP_404_NOT_FOUND,
            code="feature_disabled",
            message="Regulated OCR intake is not enabled.",
        )


def _required_ocr_consents(
    settings: Settings,
    document_type: RegulatedDocumentType,
) -> tuple[ConsentType, ...]:
    """Return consent buckets required for OCR preview creation.

    Args:
        settings: Runtime settings.
        document_type: Regulated document type.

    Returns:
        Required consent buckets.
    """
    specific = (
        ConsentType.PRESCRIPTION_OCR_INTAKE
        if document_type == RegulatedDocumentType.PRESCRIPTION
        else ConsentType.LAB_RESULT_OCR_INTAKE
    )
    consents = [ConsentType.SENSITIVE_HEALTH_ANALYSIS, specific]
    if settings.ocr_primary_provider == "google_vision":
        consents.append(ConsentType.EXTERNAL_OCR_PROCESSING)
    return tuple(consents)


async def _require_regulated_consents(
    *,
    session: AsyncSession,
    current_user: AuthenticatedUser,
    http_request: Request,
    settings: Settings,
    document_type: RegulatedDocumentType,
) -> None:
    """Require all consents needed for a regulated intake operation.

    Args:
        session: Request-scoped async database session.
        current_user: Authenticated owner.
        http_request: Current FastAPI request.
        settings: Runtime settings.
        document_type: Regulated document type.

    Raises:
        HTTPException: If any required consent is missing.
    """
    missing_consents: list[ConsentType] = []
    last_error: ConsentRequiredError | None = None
    for consent_type in _required_ocr_consents(settings, document_type):
        try:
            await require_user_consent(session, current_user, consent_type)
        except ConsentRequiredError as exc:
            missing_consents.append(consent_type)
            last_error = exc

    if not missing_consents:
        return

    missing_values = [consent.value for consent in missing_consents]
    await record_sensitive_audit_event(
        session,
        current_user,
        action=f"{document_type.value}_ocr_intake_blocked",
        resource_type="regulated_document",
        resource_id=None,
        outcome="blocked",
        request=http_request,
        settings=settings,
        event_metadata={"missing_consents": missing_values},
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "consent_required",
            "message": str(last_error),
            "required_consents": missing_values,
        },
    ) from last_error


@router.post(
    "/prescriptions/ocr",
    response_model=PrescriptionOCRPreviewResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {"description": "Prescription OCR preview requiring user confirmation."},
        403: {"description": "Required regulated consent is missing."},
        404: {"description": "Feature is disabled."},
        413: {"description": "Uploaded document image is too large."},
        415: {"description": "Uploaded document image type is unsupported."},
        422: {"description": "Image or OCR output is invalid."},
        503: {"description": "OCR provider or retention mode is not configured."},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.REGULATED_INPUT_WRITE,),
        consents=(ConsentType.SENSITIVE_HEALTH_ANALYSIS, ConsentType.PRESCRIPTION_OCR_INTAKE),
        conditional_consents=(ConsentType.EXTERNAL_OCR_PROCESSING,),
        contract_status="post_p1_regulated_intake_ready",
    ),
)
async def analyze_prescription_ocr(
    http_request: Request,
    current_user: Annotated[AuthenticatedUser, Depends(require_regulated_input_write)],
    image: Annotated[UploadFile, File(description="Prescription document image.")],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PrescriptionOCRPreviewResponse:
    """Create a prescription OCR preview that must be confirmed by the user.

    Args:
        http_request: Current FastAPI request.
        current_user: Authenticated owner.
        image: Uploaded prescription document image.
        session: Request-scoped async database session.
        settings: Runtime settings.

    Returns:
        Prescription OCR preview response.

    Raises:
        HTTPException: If feature flags, consent, image validation, OCR configuration,
            or prohibited-output checks fail.
    """
    document_type = RegulatedDocumentType.PRESCRIPTION
    _ensure_document_feature_enabled(settings, document_type)
    await _require_regulated_consents(
        session=session,
        current_user=current_user,
        http_request=http_request,
        settings=settings,
        document_type=document_type,
    )
    try:
        adapters = build_regulated_ocr_adapters(settings)
        response = await create_prescription_ocr_preview(
            session=session,
            user=current_user,
            image=image,
            settings=settings,
            adapters=adapters,
        )
    except OCRConfigurationError as exc:
        raise _regulated_http_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            code="ocr_provider_unconfigured",
            message=str(exc),
        ) from exc
    except RegulatedDocumentConfigurationError as exc:
        raise _regulated_http_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            code="regulated_retention_unconfigured",
            message=str(exc),
        ) from exc
    except RegulatedImageValidationError as exc:
        raise _regulated_http_error(exc.status_code, code=exc.code, message=exc.message) from exc
    except RegulatedMedicalOutputBlockedError as exc:
        raise _regulated_http_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="blocked_medical_output",
            message=str(exc),
        ) from exc

    await record_sensitive_audit_event(
        session,
        current_user,
        action="prescription_ocr_preview_created",
        resource_type="regulated_document",
        resource_id=str(response.document_id),
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={
            "document_type": response.document_type.value,
            "raw_image_stored": False,
            "raw_ocr_text_stored": False,
            "recognized_item_count": len(response.recognized_items),
            "warning_codes": response.warning_codes,
        },
    )
    return response


@router.post(
    "/lab-results/ocr",
    response_model=LabResultOCRPreviewResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {"description": "Lab result OCR preview requiring user confirmation."},
        403: {"description": "Required regulated consent is missing."},
        404: {"description": "Feature is disabled."},
        413: {"description": "Uploaded document image is too large."},
        415: {"description": "Uploaded document image type is unsupported."},
        422: {"description": "Image or OCR output is invalid."},
        503: {"description": "OCR provider or retention mode is not configured."},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.REGULATED_INPUT_WRITE,),
        consents=(ConsentType.SENSITIVE_HEALTH_ANALYSIS, ConsentType.LAB_RESULT_OCR_INTAKE),
        conditional_consents=(ConsentType.EXTERNAL_OCR_PROCESSING,),
        contract_status="post_p1_regulated_intake_ready",
    ),
)
async def analyze_lab_result_ocr(
    http_request: Request,
    current_user: Annotated[AuthenticatedUser, Depends(require_regulated_input_write)],
    image: Annotated[UploadFile, File(description="Lab result document image.")],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LabResultOCRPreviewResponse:
    """Create a lab result OCR preview that must be confirmed by the user.

    Args:
        http_request: Current FastAPI request.
        current_user: Authenticated owner.
        image: Uploaded lab result document image.
        session: Request-scoped async database session.
        settings: Runtime settings.

    Returns:
        Lab result OCR preview response.

    Raises:
        HTTPException: If feature flags, consent, image validation, OCR configuration,
            or prohibited-output checks fail.
    """
    document_type = RegulatedDocumentType.LAB_RESULT
    _ensure_document_feature_enabled(settings, document_type)
    await _require_regulated_consents(
        session=session,
        current_user=current_user,
        http_request=http_request,
        settings=settings,
        document_type=document_type,
    )
    try:
        adapters = build_regulated_ocr_adapters(settings)
        response = await create_lab_result_ocr_preview(
            session=session,
            user=current_user,
            image=image,
            settings=settings,
            adapters=adapters,
        )
    except OCRConfigurationError as exc:
        raise _regulated_http_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            code="ocr_provider_unconfigured",
            message=str(exc),
        ) from exc
    except RegulatedDocumentConfigurationError as exc:
        raise _regulated_http_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            code="regulated_retention_unconfigured",
            message=str(exc),
        ) from exc
    except RegulatedImageValidationError as exc:
        raise _regulated_http_error(exc.status_code, code=exc.code, message=exc.message) from exc
    except RegulatedMedicalOutputBlockedError as exc:
        raise _regulated_http_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="blocked_medical_output",
            message=str(exc),
        ) from exc

    await record_sensitive_audit_event(
        session,
        current_user,
        action="lab_result_ocr_preview_created",
        resource_type="regulated_document",
        resource_id=str(response.document_id),
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={
            "document_type": response.document_type.value,
            "raw_image_stored": False,
            "raw_ocr_text_stored": False,
            "recognized_item_count": len(response.recognized_items),
            "warning_codes": response.warning_codes,
        },
    )
    return response


@router.post(
    "/{document_id}/confirm",
    response_model=RegulatedDocumentConfirmResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Regulated OCR preview was confirmed by the user."},
        403: {"description": "Required regulated consent is missing."},
        404: {"description": "Feature is disabled or preview was not found."},
        409: {"description": "Preview is expired, finalized, or type-mismatched."},
        422: {"description": "Confirmed fields include prohibited medical output."},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.REGULATED_INPUT_WRITE,),
        consents=(ConsentType.SENSITIVE_HEALTH_ANALYSIS,),
        conditional_consents=(
            ConsentType.PRESCRIPTION_OCR_INTAKE,
            ConsentType.LAB_RESULT_OCR_INTAKE,
        ),
        contract_status="post_p1_regulated_intake_ready",
    ),
)
async def confirm_regulated_ocr_preview(
    document_id: UUID,
    http_request: Request,
    request: Annotated[RegulatedDocumentConfirmRequest, Body()],
    current_user: Annotated[AuthenticatedUser, Depends(require_regulated_input_write)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RegulatedDocumentConfirmResponse:
    """Confirm a regulated OCR preview after user review.

    Args:
        document_id: Preview identifier.
        http_request: Current FastAPI request.
        request: User-confirmed structured fields.
        current_user: Authenticated owner.
        session: Request-scoped async database session.
        settings: Runtime settings.

    Returns:
        Confirmation response.

    Raises:
        HTTPException: If feature flags, consent, preview state, or prohibited-output
            checks fail.
    """
    _ensure_document_feature_enabled(settings, request.document_type)
    await _require_regulated_consents(
        session=session,
        current_user=current_user,
        http_request=http_request,
        settings=settings,
        document_type=request.document_type,
    )
    try:
        response = await confirm_regulated_document(
            session=session,
            user=current_user,
            document_id=document_id,
            request=request,
            settings=settings,
        )
    except RegulatedDocumentNotFoundError as exc:
        raise _regulated_http_error(
            status.HTTP_404_NOT_FOUND,
            code="regulated_document_not_found",
            message=str(exc),
        ) from exc
    except (
        RegulatedDocumentExpiredError,
        RegulatedDocumentStateError,
        RegulatedDocumentTypeMismatchError,
    ) as exc:
        raise _regulated_http_error(
            status.HTTP_409_CONFLICT,
            code="regulated_document_not_confirmable",
            message=str(exc),
        ) from exc
    except RegulatedMedicalOutputBlockedError as exc:
        raise _regulated_http_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="blocked_medical_output",
            message=str(exc),
        ) from exc

    await record_sensitive_audit_event(
        session,
        current_user,
        action="regulated_document_confirmed",
        resource_type="regulated_document",
        resource_id=str(response.document_id),
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={
            "document_type": response.document_type.value,
            "raw_image_stored": False,
            "raw_ocr_text_stored": False,
        },
    )
    return response
