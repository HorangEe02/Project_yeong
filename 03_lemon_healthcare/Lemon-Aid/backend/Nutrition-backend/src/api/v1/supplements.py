"""Supplement API contract routes for P1 implementation."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.contract import (
    P1_2_INTAKE_READY_STATUS,
    P1_4_SUPPLEMENT_REGISTRATION_READY_STATUS,
    P1_7_SUPPLEMENT_RECOMMENDATION_READY_STATUS,
    route_contract,
)
from src.api.v1.examples import (
    CONSENT_REQUIRED_EXAMPLE,
    INSUFFICIENT_SCOPE_EXAMPLE,
    PAYLOAD_TOO_LARGE_EXAMPLE,
    SUPPLEMENT_ANALYSIS_RESPONSE_EXAMPLES,
    SUPPLEMENT_CREATE_REQUEST_EXAMPLES,
    SUPPLEMENT_IMPACT_PREVIEW_RESPONSE_EXAMPLES,
    SUPPLEMENT_RECOMMENDATION_EXPLAIN_REQUEST_EXAMPLES,
    SUPPLEMENT_RECOMMENDATION_EXPLAIN_RESPONSE_EXAMPLES,
    TOO_MANY_REQUESTS_EXAMPLE,
    UNAUTHORIZED_EXAMPLE,
    UNPROCESSABLE_ENTITY_EXAMPLE,
    UNSUPPORTED_MEDIA_TYPE_EXAMPLE,
    USER_SUPPLEMENT_LIST_RESPONSE_EXAMPLES,
    USER_SUPPLEMENT_RESPONSE_EXAMPLES,
)
from src.config import Settings, get_settings
from src.db.dependencies import (
    get_async_session,
    get_rls_context_session,
    rls_request_transaction,
)
from src.db.tx import persist_scope
from src.learning.factory import build_learning_object_store
from src.learning.pipeline import (
    build_confirmed_supplement_learning_metadata,
    collect_active_learning_consents,
)
from src.llm.ollama import (
    OllamaClientError,
    OllamaConfigurationError,
    OllamaStructuredOutputError,
)
from src.models.db.supplement import SupplementAnalysisRun
from src.models.schemas.privacy import ConsentType
from src.models.schemas.supplement import (
    SupplementAnalysisAccepted,
    SupplementAnalysisError,
    SupplementAnalysisPreview,
    SupplementAnalysisSessionResponse,
    SupplementAnalysisStatus,
    SupplementAnalysisStatusResponse,
    SupplementBarcodeLookupRequest,
    SupplementBarcodeLookupResponse,
    SupplementMultiImageAnalysisAccepted,
    SupplementMultiImageAnalysisPreview,
    SupplementMultiImageAnalysisStatusResponse,
    UserSupplementCreate,
    UserSupplementListResponse,
    UserSupplementResponse,
)
from src.models.schemas.supplement_comprehensive import (
    ComprehensiveAnalysisRequest,
    SupplementComprehensiveAnalysis,
)
from src.models.schemas.supplement_image import SupplementImagePipelineMetadata
from src.models.schemas.supplement_parser import SupplementOCRTextParseRequest
from src.models.schemas.supplement_recommendation import (
    SupplementAnalysisExplainRequest,
    SupplementAnalysisPreviewWithRecommendation,
    SupplementImpactPreviewRequest,
    SupplementImpactPreviewResponse,
    SupplementRecommendationExplainRequest,
    SupplementRecommendationExplainResponse,
)
from src.models.schemas.taxonomy import SupplementCategoryListResponse
from src.nutrition.comprehensive import compute_comprehensive
from src.ocr.factory import (
    OCRConfigurationError,
    SupplementOCRProviderSelector,
    build_supplement_image_analysis_adapters,
    build_supplement_image_analysis_adapters_for_provider,
    is_external_ocr_pipeline_enabled,
)
from src.security.auth import (
    AuthenticatedUser,
    require_scopes,
    require_supplement_delete,
    require_supplement_read,
    require_supplement_write,
)
from src.security.scopes import ApiScope
from src.security.subjects import build_owner_subject
from src.services.health_profile import get_latest_body_profile_snapshot
from src.services.medical_records import get_current_medical_context_summary
from src.services.nutrient_category_map import category_keys_for_ingredient_texts
from src.services.privacy import (
    AuditOutcome,
    ConsentRequiredError,
    record_sensitive_audit_event,
    require_user_consent,
)
from src.services.supplement_analysis_worker import (
    CapturedImage,
    CapturedRequest,
    run_multi_supplement_analysis_job,
    run_single_supplement_analysis_job,
)
from src.services.supplement_barcode_lookup import (
    BarcodeLookupServiceResult,
    SupplementBarcodeLookupService,
    attach_barcode_lookup_to_analysis,
    barcode_lookup_result_to_response,
    build_supplement_barcode_lookup_service,
)
from src.services.supplement_explanation import (
    SupplementExplanationError,
    explain_supplement_analysis_preview,
    explain_supplement_recommendation,
)
from src.services.supplement_image_analysis import (
    SupplementImageAnalysisAdapters,
    SupplementLearningEmbeddingInput,
    analyze_fused_supplement_images,
    analyze_supplement_image,
    store_supplement_learning_artifacts,
    store_supplement_learning_embedding_job,
)
from src.services.supplement_intake import (
    SupplementImageValidationError,
    SupplementIntakeConflictError,
    ValidatedSupplementImage,
    create_supplement_analysis_intake,
    read_and_validate_supplement_image,
    supplement_analysis_run_to_preview,
)
from src.services.supplement_parser import (
    SupplementAnalysisExpiredError,
    SupplementAnalysisNotFoundError,
    SupplementAnalysisStateError,
    SupplementParserConflictError,
    SupplementParserInputError,
    parse_supplement_analysis_ocr_text,
)
from src.services.supplement_recommendation import build_supplement_impact_preview
from src.services.supplement_registration import (
    SupplementPreviewExpiredError,
    SupplementPreviewNotFoundError,
    SupplementPreviewStateError,
    SupplementRegistrationValidationError,
    create_user_supplement_from_confirmation,
    get_user_supplement_record,
    list_user_supplement_records,
    soft_delete_user_supplement,
    user_supplement_to_response,
)
from src.services.taxonomy_catalog import (
    TaxonomyFilterNotFoundError,
    list_supplement_categories,
)

router = APIRouter(prefix="/supplements", tags=["supplements"])

__all__ = ["router", "user_supplement_to_response"]

SUPPLEMENT_AUTH_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"content": {"application/json": {"examples": UNAUTHORIZED_EXAMPLE}}},
    403: {"content": {"application/json": {"examples": INSUFFICIENT_SCOPE_EXAMPLE}}},
    422: {"content": {"application/json": {"examples": UNPROCESSABLE_ENTITY_EXAMPLE}}},
}

COMMON_SUPPLEMENT_RESPONSES: dict[int | str, dict[str, Any]] = {
    **SUPPLEMENT_AUTH_RESPONSES,
}

require_supplement_recommendation_read = require_scopes(
    ApiScope.SUPPLEMENT_READ,
    ApiScope.ANALYSIS_READ,
)
MAX_MULTI_IMAGE_ANALYSIS_IMAGES = 6
MULTI_IMAGE_ROLE_VALUES = frozenset(
    {
        "unknown",
        "front_label",
        "supplement_facts",
        "intake_method",
        "ingredients",
        "precautions",
        "barcode",
        "mixed",
    }
)
SUPPLEMENT_ANALYSIS_POLL_PATH = "/api/v1/supplements/analyses"

# Strong refs to in-flight async-analysis worker tasks. asyncio.create_task keeps
# only a weak reference, so without this set a fire-and-forget worker can be GC'd
# mid-run. Each task removes itself on completion (see _spawn_analysis_worker).
_ANALYSIS_WORKER_TASKS: set[asyncio.Task[None]] = set()


def _capture_request_metadata(http_request: Request) -> CapturedRequest:
    """Snapshot request network metadata for the detached worker's audits.

    The ``Request`` is gone once the 202 response is sent, but out-of-band audits
    still need the client IP, user-agent, and request-id to hash. Capture only
    those.

    Args:
        http_request: Current FastAPI request.

    Returns:
        Request metadata snapshot safe to retain across the response boundary.
    """
    raw_headers = {
        key: http_request.headers[key]
        for key in ("user-agent", "x-request-id")
        if key in http_request.headers
    }
    client_host = http_request.client.host if http_request.client else None
    return CapturedRequest.from_request(client_host, raw_headers)


def _spawn_analysis_worker(coro: Any) -> None:
    """Schedule a detached analysis worker task with a strong reference.

    Args:
        coro: Worker coroutine (``run_single_*`` / ``run_multi_*``) to run.
    """
    task = asyncio.create_task(coro)
    _ANALYSIS_WORKER_TASKS.add(task)
    task.add_done_callback(_ANALYSIS_WORKER_TASKS.discard)


async def _capture_validated_image(
    image: UploadFile,
    settings: Settings,
) -> tuple[ValidatedSupplementImage, bytes]:
    """Validate an upload and return its metadata plus retained bytes.

    The ``UploadFile`` is consumed once the request returns, so the validated
    bytes are read into memory for the detached worker. Reuses
    ``read_and_validate_supplement_image`` for identical validation semantics,
    then seeks back to re-read the raw bytes.

    Args:
        image: Uploaded supplement label image.
        settings: Runtime settings containing upload limits.

    Returns:
        Validated metadata and the raw uploaded bytes.

    Raises:
        SupplementImageValidationError: If the upload fails intake validation.
    """
    metadata = await read_and_validate_supplement_image(image, settings)
    await image.seek(0)
    image_bytes = await image.read()
    return metadata, image_bytes


def _supplement_http_error(status_code: int, *, code: str, message: str) -> HTTPException:
    """Build a stable supplement API error response.

    Args:
        status_code: HTTP status code.
        code: Stable application error code.
        message: Safe user-facing message.

    Returns:
        FastAPI HTTP exception.
    """
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


def get_supplement_image_analysis_adapters(
    settings: Annotated[Settings, Depends(get_settings)],
) -> SupplementImageAnalysisAdapters:
    """Build supplement image analysis adapters for the current settings.

    Args:
        settings: Application settings.

    Returns:
        Image analysis adapters.

    Raises:
        HTTPException: If OCR provider settings are incomplete or unsafe.
    """
    try:
        return build_supplement_image_analysis_adapters(settings)
    except OCRConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "ocr_provider_unconfigured",
                "message": str(exc),
            },
        ) from exc


def get_supplement_barcode_lookup_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> SupplementBarcodeLookupService:
    """Build the barcode lookup service for the current settings.

    Args:
        settings: Application settings.

    Returns:
        Barcode lookup service.
    """

    return build_supplement_barcode_lookup_service(settings)


def _required_supplement_analyze_consents(
    settings: Settings,
    ocr_provider: SupplementOCRProviderSelector = "configured",
) -> tuple[ConsentType, ...]:
    """Return consent buckets required for supplement image analysis.

    Args:
        settings: Application settings.
        ocr_provider: Request-selected OCR provider.

    Returns:
        Consent buckets required by the active OCR path.
    """
    consents = [ConsentType.OCR_IMAGE_PROCESSING]
    if is_external_ocr_pipeline_enabled(settings, ocr_provider):
        consents.append(ConsentType.EXTERNAL_OCR_PROCESSING)
    return tuple(consents)


def _select_supplement_image_analysis_adapters(
    *,
    settings: Settings,
    configured_adapters: SupplementImageAnalysisAdapters,
    ocr_provider: SupplementOCRProviderSelector,
) -> SupplementImageAnalysisAdapters:
    """Return an adapter bundle constrained to the request-selected provider.

    Args:
        settings: Application settings.
        configured_adapters: Default adapters built by dependency injection.
        ocr_provider: Provider selector submitted with the multipart request.

    Returns:
        Adapter bundle for this request.

    Raises:
        HTTPException: If the requested provider cannot be configured.
    """
    try:
        return build_supplement_image_analysis_adapters_for_provider(
            settings,
            ocr_provider,
            configured_adapters=configured_adapters,
        )
    except OCRConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "ocr_provider_unconfigured",
                "message": str(exc),
                "requested_ocr_provider": ocr_provider,
            },
        ) from exc


def _ocr_provider_warning_codes(codes: tuple[str, ...]) -> list[str]:
    """Return warning codes that indicate OCR/provider/parser failure.

    Args:
        codes: Warning codes produced by the image analysis service.

    Returns:
        Warning codes excluding image-quality review hints.
    """
    return [code for code in codes if not code.startswith("image_quality:")]


def _validate_multi_image_roles(
    image_count: int,
    image_roles: list[str] | None,
    image_roles_json: str | None = None,
) -> list[str]:
    """Validate optional multi-image role form values.

    Args:
        image_count: Number of uploaded images.
        image_roles: Optional client role values.
        image_roles_json: Optional JSON-encoded role list for clients that cannot
            repeat multipart form field names.

    Returns:
        One role value per image.

    Raises:
        HTTPException: If the role count or value is invalid.
    """
    if image_count < 1 or image_count > MAX_MULTI_IMAGE_ANALYSIS_IMAGES:
        raise _supplement_http_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="image_count_invalid",
            message=f"Upload between 1 and {MAX_MULTI_IMAGE_ANALYSIS_IMAGES} images.",
        )
    if image_roles is None and image_roles_json:
        image_roles = _parse_multi_image_roles_json(image_roles_json)
    if image_roles is None:
        return ["unknown"] * image_count
    normalized = [role.strip() for role in image_roles]
    if len(normalized) != image_count:
        raise _supplement_http_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="image_role_count_mismatch",
            message="image_roles must contain exactly one value per uploaded image.",
        )
    invalid = [role for role in normalized if role not in MULTI_IMAGE_ROLE_VALUES]
    if invalid:
        raise _supplement_http_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="image_role_invalid",
            message="image_roles contains an unsupported supplement image role.",
        )
    return normalized


def _parse_multi_image_roles_json(image_roles_json: str) -> list[str]:
    """Parse JSON-encoded role values from multipart form data.

    Args:
        image_roles_json: JSON string expected to contain only string role values.

    Returns:
        Role values parsed from JSON.

    Raises:
        HTTPException: If the JSON shape is invalid.
    """
    try:
        parsed = json.loads(image_roles_json)
    except json.JSONDecodeError as exc:
        raise _supplement_http_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="image_roles_invalid_json",
            message="image_roles_json must be a JSON array of role strings.",
        ) from exc
    if not isinstance(parsed, list) or not all(isinstance(role, str) for role in parsed):
        raise _supplement_http_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="image_roles_invalid_json",
            message="image_roles_json must be a JSON array of role strings.",
        )
    return parsed


def _multi_image_client_request_id(client_request_id: str | None, index: int) -> str | None:
    """Derive a per-image idempotency key hint for a multi-image batch.

    Args:
        client_request_id: Optional batch-level client id.
        index: Zero-based image index.

    Returns:
        Per-image client id hint, or None when the batch has no id.
    """
    if client_request_id is None or not client_request_id.strip():
        return None
    return f"{client_request_id.strip()}:{index + 1}"


def _session_image_client_request_id(
    analysis_group_id: str,
    client_request_id: str | None,
    image_role: str,
) -> str:
    """Build an idempotency hint scoped to an analysis session image upload.

    Args:
        analysis_group_id: Backend-created group identifier.
        client_request_id: Optional client-supplied image idempotency hint.
        image_role: Client-supplied image role.

    Returns:
        Bounded client idempotency hint for existing intake persistence.
    """
    suffix = client_request_id.strip() if client_request_id and client_request_id.strip() else None
    if suffix is None:
        suffix = f"{image_role}-{uuid4().hex[:12]}"
    return f"{analysis_group_id}:{suffix}"[:80]


async def _annotate_multi_image_record(
    session: AsyncSession,
    result_record: Any,
    *,
    image_role: str,
    analysis_group_id: str,
    image_count: int,
) -> None:
    """Persist non-sensitive batch metadata on a per-image preview.

    Args:
        session: Request-scoped async database session.
        result_record: Supplement analysis ORM row.
        image_role: Client-supplied or unknown image role.
        analysis_group_id: Ephemeral batch group identifier.
        image_count: Number of images in the batch.
    """
    async with persist_scope(session):
        parsed_snapshot = dict(result_record.parsed_snapshot or {})
        parsed_snapshot["image_role"] = image_role
        parsed_snapshot["multi_image_group_id"] = analysis_group_id
        pipeline_metadata = dict(parsed_snapshot.get("pipeline_metadata") or {})
        pipeline_metadata["image_count"] = image_count
        pipeline_metadata["image_role"] = image_role
        parsed_snapshot["pipeline_metadata"] = pipeline_metadata
        result_record.parsed_snapshot = parsed_snapshot


async def _refresh_multi_image_count(
    session: AsyncSession,
    analysis_runs: list[SupplementAnalysisRun],
) -> None:
    """Persist the latest group image count on every per-image snapshot.

    Args:
        session: Request-scoped async database session.
        analysis_runs: Current group rows loaded for the owner.
    """
    if not analysis_runs:
        return
    image_count = len(analysis_runs)
    async with persist_scope(session):
        for record in analysis_runs:
            parsed_snapshot = dict(record.parsed_snapshot or {})
            pipeline_metadata = dict(parsed_snapshot.get("pipeline_metadata") or {})
            pipeline_metadata["image_count"] = image_count
            parsed_snapshot["pipeline_metadata"] = pipeline_metadata
            record.parsed_snapshot = parsed_snapshot


def _build_multi_image_response(
    *,
    analysis_group_id: str,
    previews: list[SupplementAnalysisPreview],
    merge_strategy: Literal["single_product", "distinct_products"] = "single_product",
) -> SupplementMultiImageAnalysisPreview:
    """Build a sanitized aggregate response for a multi-image batch.

    Args:
        analysis_group_id: Ephemeral group identifier.
        previews: Per-image analysis previews.
        merge_strategy: ``single_product`` fuses every image into one
            ``merged_preview``; ``distinct_products`` keeps each image as its own
            product (no merged preview) so the client renders one tab per preview.

    Returns:
        Batch-level multi-image preview.
    """
    missing_sections = _aggregate_missing_sections(previews)
    pipeline_metadata = _aggregate_pipeline_metadata(previews, missing_sections)
    # distinct_products: each image is a different supplement, so do not fabricate a
    # cross-product merged preview — the client renders one tab per entry in previews.
    # single_product: keep fusing the batch into one merged preview as before.
    merged_preview = (
        None
        if merge_strategy == "distinct_products"
        else _build_merged_multi_image_preview(
            analysis_group_id=analysis_group_id,
            previews=previews,
            missing_sections=missing_sections,
            pipeline_metadata=pipeline_metadata,
        )
    )
    return SupplementMultiImageAnalysisPreview(
        analysis_group_id=analysis_group_id,
        image_count=len(previews),
        previews=previews,
        merged_preview=merged_preview,
        missing_required_sections=missing_sections,
        action_required=(
            "additional_label_image_required" if missing_sections else "review_required"
        ),
        pipeline_metadata=pipeline_metadata,
        expires_at=min((preview.expires_at for preview in previews), default=None),
        result_mode=merge_strategy,
    )


def _build_analysis_session_response(
    analysis_group_id: str,
    *,
    image_count: int = 0,
    max_images: int = MAX_MULTI_IMAGE_ANALYSIS_IMAGES,
) -> SupplementAnalysisSessionResponse:
    """Build a lightweight session response without raw image or OCR data.

    Args:
        analysis_group_id: Backend-created group identifier.
        image_count: Number of accepted images currently tied to the group.
        max_images: Maximum images accepted by the session.

    Returns:
        Sanitized multi-image analysis session response.
    """
    missing_required_sections: list[str] = []
    if image_count == 0:
        missing_required_sections = [
            "product_name",
            "supplement_facts",
            "intake_method",
            "precautions",
        ]
    return SupplementAnalysisSessionResponse(
        analysis_group_id=analysis_group_id,
        status=(
            "created"
            if image_count == 0
            else "receiving_images" if missing_required_sections else "ready_for_review"
        ),
        image_count=image_count,
        max_images=max_images,
        missing_required_sections=missing_required_sections,
        action_required=(
            "additional_label_image_required"
            if missing_required_sections or image_count == 0
            else "review_required"
        ),
    )


async def _load_multi_image_analysis_runs(
    session: AsyncSession,
    *,
    owner_subject: str,
    analysis_group_id: str,
) -> list[SupplementAnalysisRun]:
    """Load current-user analysis rows that belong to one multi-image group.

    Args:
        session: Request-scoped async database session.
        owner_subject: Issuer-qualified authenticated subject.
        analysis_group_id: Backend-created multi-image group identifier.

    Returns:
        Analysis rows ordered by creation time.
    """
    result = await session.scalars(
        select(SupplementAnalysisRun)
        .where(
            SupplementAnalysisRun.owner_subject == owner_subject,
            SupplementAnalysisRun.parsed_snapshot["multi_image_group_id"].as_string()
            == analysis_group_id,
        )
        .order_by(SupplementAnalysisRun.created_at.asc())
    )
    return list(result.all())


async def _load_supplement_analysis_run_for_owner(
    session: AsyncSession,
    *,
    owner_subject: str,
    analysis_id: UUID,
) -> SupplementAnalysisRun | None:
    """Load one current-user supplement analysis preview.

    Args:
        session: Request-scoped async database session.
        owner_subject: Issuer-qualified authenticated subject.
        analysis_id: Analysis preview identifier.

    Returns:
        Matching supplement analysis run, or None.
    """
    return await session.scalar(
        select(SupplementAnalysisRun).where(
            SupplementAnalysisRun.owner_subject == owner_subject,
            SupplementAnalysisRun.id == analysis_id,
        )
    )


def _build_merged_multi_image_preview(
    *,
    analysis_group_id: str,
    previews: list[SupplementAnalysisPreview],
    missing_sections: list[str],
    pipeline_metadata: SupplementImagePipelineMetadata,
) -> SupplementAnalysisPreview | None:
    """Build a bounded review preview from per-image batch evidence.

    Args:
        analysis_group_id: Ephemeral group identifier.
        previews: Per-image previews already sanitized by the intake pipeline.
        missing_sections: Batch-level missing section codes.
        pipeline_metadata: Aggregate non-sensitive pipeline metadata.

    Returns:
        A merged preview using one persisted preview id for confirmation traceability.
    """
    reviewable_previews = [preview for preview in previews if _has_preview_review_content(preview)]
    if not reviewable_previews:
        return None
    base = _select_merged_preview_base(reviewable_previews)
    merged = _MergedPreviewParts()
    for preview_index, preview in enumerate(previews, start=1):
        span_ref_map = _append_prefixed_evidence_spans(merged, preview, preview_index)
        _append_prefixed_label_sections(merged, preview, preview_index, span_ref_map)
        _append_unique_ingredients(merged, preview)
        _append_unique_precautions(merged, preview, span_ref_map)
        _append_unique_functional_claims(merged, preview, span_ref_map)

    intake_method = _select_intake_method(previews, merged.span_ref_maps)
    return base.model_copy(
        update={
            "parsed_product": _select_parsed_product(previews),
            "ingredient_candidates": merged.ingredients or base.ingredient_candidates,
            "suggested_category_keys": list(
                category_keys_for_ingredient_texts(
                    candidate.display_name
                    for candidate in (merged.ingredients or base.ingredient_candidates)
                )
            ),
            "layout_available": bool(merged.label_sections) or base.layout_available,
            "label_sections": merged.label_sections,
            "intake_method": intake_method,
            "precautions": merged.precautions,
            "functional_claims": merged.functional_claims,
            "evidence_spans": merged.evidence_spans,
            "action_required": (
                "additional_label_image_required" if missing_sections else "review_required"
            ),
            "missing_required_sections": missing_sections,
            "image_role": "mixed" if len(previews) > 1 else base.image_role,
            "multi_image_group_id": analysis_group_id,
            "pipeline_metadata": pipeline_metadata,
            "warnings": _merge_preview_warnings(previews),
            "expires_at": min(
                (preview.expires_at for preview in previews), default=base.expires_at
            ),
        },
        deep=True,
    )


def _has_preview_review_content(preview: SupplementAnalysisPreview) -> bool:
    """Return whether a preview has structured content worth merging.

    Args:
        preview: Per-image preview already sanitized for client display.

    Returns:
        True when the preview has any product, section, ingredient, intake,
        precaution, or claim content that can improve the batch-level review.
    """
    return (
        bool(preview.ingredient_candidates)
        or bool(preview.label_sections)
        or bool(preview.parsed_product.product_name)
        or bool(preview.parsed_product.manufacturer)
        or bool(preview.intake_method.text)
        or bool(preview.precautions)
        or bool(preview.functional_claims)
    )


class _MergedPreviewParts:
    """Mutable accumulators for a sanitized multi-image preview merge."""

    def __init__(self) -> None:
        self.label_sections: list[Any] = []
        self.evidence_spans: list[Any] = []
        self.ingredients: list[Any] = []
        self.precautions: list[Any] = []
        self.functional_claims: list[Any] = []
        self.section_keys: set[tuple[str, str, str]] = set()
        self.span_ids: set[str] = set()
        self.ingredient_keys: set[tuple[str, str, str, str]] = set()
        self.precaution_texts: set[str] = set()
        self.claim_texts: set[str] = set()
        self.span_ref_maps: dict[int, dict[str, str]] = {}


def _select_merged_preview_base(
    previews: list[SupplementAnalysisPreview],
) -> SupplementAnalysisPreview:
    """Select the persisted preview id that best represents the merged batch."""
    return max(
        previews,
        key=lambda preview: (
            len(preview.ingredient_candidates),
            len(preview.label_sections),
            bool(preview.parsed_product.product_name),
            bool(preview.intake_method.text),
        ),
    )


def _append_prefixed_evidence_spans(
    merged: _MergedPreviewParts,
    preview: SupplementAnalysisPreview,
    preview_index: int,
) -> dict[str, str]:
    """Append evidence spans with image-scoped ids to avoid cross-image collisions."""
    ref_map: dict[str, str] = {}
    for span in preview.evidence_spans:
        new_id = _bounded_prefixed_id("span", preview_index, span.span_id, max_length=120)
        suffix = 2
        while new_id in merged.span_ids:
            new_id = _bounded_prefixed_id(
                f"span{suffix}",
                preview_index,
                span.span_id,
                max_length=120,
            )
            suffix += 1
        merged.span_ids.add(new_id)
        ref_map[span.span_id] = new_id
        merged.evidence_spans.append(span.model_copy(update={"span_id": new_id}, deep=True))
    merged.span_ref_maps[preview_index] = ref_map
    return ref_map


def _append_prefixed_label_sections(
    merged: _MergedPreviewParts,
    preview: SupplementAnalysisPreview,
    preview_index: int,
    span_ref_map: dict[str, str],
) -> None:
    """Append unique label sections with image-scoped evidence references."""
    for section in preview.label_sections:
        key = (
            section.section_type,
            section.heading_text or "",
            section.text_bundle or "",
        )
        if key in merged.section_keys:
            continue
        merged.section_keys.add(key)
        merged.label_sections.append(
            section.model_copy(
                update={
                    "section_id": _bounded_prefixed_id(
                        "section",
                        preview_index,
                        section.section_id,
                        max_length=80,
                    ),
                    "evidence_refs": [span_ref_map.get(ref, ref) for ref in section.evidence_refs],
                },
                deep=True,
            )
        )


def _append_unique_ingredients(
    merged: _MergedPreviewParts,
    preview: SupplementAnalysisPreview,
) -> None:
    """Append bounded unique ingredient candidates from a per-image preview."""
    for ingredient in preview.ingredient_candidates:
        key = (
            ingredient.display_name,
            ingredient.nutrient_code or "",
            str(ingredient.amount),
            ingredient.unit or "",
        )
        if key in merged.ingredient_keys:
            continue
        merged.ingredient_keys.add(key)
        merged.ingredients.append(ingredient)


def _append_unique_precautions(
    merged: _MergedPreviewParts,
    preview: SupplementAnalysisPreview,
    span_ref_map: dict[str, str],
) -> None:
    """Append unique precaution candidates with remapped evidence refs."""
    for precaution in preview.precautions:
        key = precaution.text
        if key in merged.precaution_texts:
            continue
        merged.precaution_texts.add(key)
        merged.precautions.append(
            precaution.model_copy(
                update={
                    "evidence_refs": [
                        span_ref_map.get(ref, ref) for ref in precaution.evidence_refs
                    ]
                },
                deep=True,
            )
        )


def _append_unique_functional_claims(
    merged: _MergedPreviewParts,
    preview: SupplementAnalysisPreview,
    span_ref_map: dict[str, str],
) -> None:
    """Append unique functional claims with remapped evidence refs."""
    for claim in preview.functional_claims:
        key = claim.text
        if key in merged.claim_texts:
            continue
        merged.claim_texts.add(key)
        merged.functional_claims.append(
            claim.model_copy(
                update={
                    "evidence_refs": [span_ref_map.get(ref, ref) for ref in claim.evidence_refs]
                },
                deep=True,
            )
        )


def _select_intake_method(
    previews: list[SupplementAnalysisPreview],
    span_ref_maps: dict[int, dict[str, str]],
) -> Any:
    """Return the first label-supported intake method with remapped evidence refs."""
    for preview_index, preview in enumerate(previews, start=1):
        if not preview.intake_method.text:
            continue
        span_ref_map = span_ref_maps.get(preview_index, {})
        return preview.intake_method.model_copy(
            update={
                "evidence_refs": [
                    span_ref_map.get(ref, ref) for ref in preview.intake_method.evidence_refs
                ]
            },
            deep=True,
        )
    return previews[0].intake_method


def _select_parsed_product(previews: list[SupplementAnalysisPreview]) -> Any:
    """Return the richest parsed product candidate across a batch."""
    return max(
        (preview.parsed_product for preview in previews),
        key=lambda product: (
            bool(product.product_name),
            bool(product.manufacturer),
            bool(product.serving_size),
            product.daily_servings is not None,
        ),
    )


def _merge_preview_warnings(previews: list[SupplementAnalysisPreview]) -> list[str]:
    """Merge safe preview warnings in first-seen order."""
    warnings: list[str] = []
    seen: set[str] = set()
    for preview in previews:
        for warning in preview.warnings:
            if warning in seen:
                continue
            seen.add(warning)
            warnings.append(warning)
    return warnings


def _bounded_prefixed_id(
    prefix: str,
    preview_index: int,
    value: str,
    *,
    max_length: int,
) -> str:
    """Build a stable bounded id that identifies the source image."""
    return f"image{preview_index}-{prefix}-{value}"[:max_length]


def _aggregate_missing_sections(
    previews: list[SupplementAnalysisPreview],
) -> list[str]:
    """Infer batch-level missing sections from per-image previews.

    Args:
        previews: Per-image analysis previews.

    Returns:
        Required section codes still missing at the batch level.
    """
    has_facts = any(
        preview.ingredient_candidates
        or any(
            section.section_type in {"supplement_facts", "ingredients", "nutrition_info"}
            for section in preview.label_sections
        )
        for preview in previews
    )
    has_product_name = any(preview.parsed_product.product_name for preview in previews)
    has_intake = any(
        preview.intake_method.text
        or preview.image_role == "intake_method"
        or any(section.section_type == "intake_method" for section in preview.label_sections)
        for preview in previews
    )
    has_precautions = any(
        preview.precautions
        or any(
            section.section_type in {"precautions", "allergen_warning"}
            for section in preview.label_sections
        )
        for preview in previews
    )
    missing: list[str] = []
    if not has_product_name:
        missing.append("product_name")
    if not has_facts:
        missing.append("supplement_facts")
    if not has_intake:
        missing.append("intake_method")
    if not has_precautions:
        missing.append("precautions")
    return missing


def _aggregate_pipeline_metadata(
    previews: list[SupplementAnalysisPreview],
    missing_sections: list[str],
) -> SupplementImagePipelineMetadata:
    """Aggregate non-sensitive pipeline metadata for a multi-image response.

    Args:
        previews: Per-image analysis previews.
        missing_sections: Batch-level missing section codes.

    Returns:
        Sanitized aggregate pipeline metadata.
    """
    providers = {
        metadata.ocr_provider
        for preview in previews
        if (metadata := preview.pipeline_metadata).ocr_provider
    }
    parser_versions = {
        metadata.parser_contract_version
        for preview in previews
        if (metadata := preview.pipeline_metadata).parser_contract_version
    }
    return SupplementImagePipelineMetadata(
        intake_completed=all(preview.pipeline_metadata.intake_completed for preview in previews),
        image_count=len(previews),
        image_role="mixed" if len(previews) > 1 else previews[0].image_role,
        vision_roi_used=any(preview.pipeline_metadata.vision_roi_used for preview in previews),
        ocr_status=_aggregate_pipeline_status(
            [preview.pipeline_metadata.ocr_status for preview in previews]
        ),
        vision_status=_aggregate_pipeline_status(
            [preview.pipeline_metadata.vision_status for preview in previews]
        ),
        llm_status=_aggregate_pipeline_status(
            [preview.pipeline_metadata.llm_status for preview in previews]
        ),
        ocr_provider=_aggregate_label(providers),
        ocr_text_present=any(preview.pipeline_metadata.ocr_text_present for preview in previews),
        ocr_confidence_bucket=_aggregate_confidence_bucket(previews),
        roi_count=sum(preview.pipeline_metadata.roi_count for preview in previews),
        section_count=sum(preview.pipeline_metadata.section_count for preview in previews),
        llm_parser_used=any(preview.pipeline_metadata.llm_parser_used for preview in previews),
        parser_contract_version=_aggregate_label(parser_versions),
        missing_required_sections=missing_sections,
        raw_image_stored=False,
        raw_ocr_text_stored=False,
    )


def _aggregate_pipeline_status(values: list[str]) -> str:
    """Return one LED status for multiple preview stage statuses."""
    for stage_status in ("failed", "warning", "success"):
        if stage_status in values:
            return stage_status
    return "skipped"


def _aggregate_label(values: set[str | None]) -> str | None:
    """Return a stable aggregate label for provider/version fields."""
    labels = {value for value in values if value}
    if not labels:
        return None
    if len(labels) == 1:
        return next(iter(labels))
    return "mixed"


def _aggregate_confidence_bucket(previews: list[SupplementAnalysisPreview]) -> str:
    """Return the lowest non-empty OCR confidence bucket across previews."""
    buckets = [preview.pipeline_metadata.ocr_confidence_bucket for preview in previews]
    for bucket in ("low", "medium", "high", "unknown"):
        if bucket in buckets:
            return bucket
    return "none"


async def _require_sensitive_health_consent(
    session: AsyncSession,
    current_user: AuthenticatedUser,
    http_request: Request,
    settings: Settings,
) -> None:
    """Require sensitive-health consent for confirmed supplement storage.

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
            action="supplement_registration_blocked",
            resource_type="user_supplement",
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


async def _require_supplement_analyze_consents(
    *,
    session: AsyncSession,
    current_user: AuthenticatedUser,
    http_request: Request,
    settings: Settings,
    ocr_provider: SupplementOCRProviderSelector,
    blocked_action: str,
) -> None:
    """Enforce OCR (and conditional external-OCR) consent for image analysis.

    Shared by the async-submit paths; mirrors the synchronous routes' consent
    loop, the blocked-audit emission, and the 403 shape. Must run inside the
    request-owned RLS transaction so the blocked audit goes out-of-band.

    Args:
        session: Owner-scoped request-managed session.
        current_user: Authenticated owner.
        http_request: Current FastAPI request.
        settings: Application settings.
        ocr_provider: Request-selected OCR provider.
        blocked_action: Audit action name when the non-external consent is missing.

    Raises:
        HTTPException: 403 when a required consent grant is missing.
    """
    required_consents = _required_supplement_analyze_consents(settings, ocr_provider)
    missing_consents: list[ConsentType] = []
    last_consent_error: ConsentRequiredError | None = None
    for consent_type in required_consents:
        try:
            await require_user_consent(session, current_user, consent_type)
        except ConsentRequiredError as exc:
            missing_consents.append(consent_type)
            last_consent_error = exc
    if not missing_consents:
        return
    missing_values = [consent.value for consent in missing_consents]
    await record_sensitive_audit_event(
        session,
        current_user,
        action=(
            "supplement_external_ocr_blocked"
            if ConsentType.EXTERNAL_OCR_PROCESSING in missing_consents
            else blocked_action
        ),
        resource_type="supplement_analysis_run",
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
            "message": str(last_consent_error),
            "required_consents": missing_values,
        },
    ) from last_consent_error


async def _submit_async_single_analysis(
    *,
    http_request: Request,
    current_user: AuthenticatedUser,
    image: UploadFile,
    session: AsyncSession,
    settings: Settings,
    adapters: SupplementImageAnalysisAdapters,
    ocr_provider: SupplementOCRProviderSelector,
    client_request_id: str | None,
) -> SupplementAnalysisAccepted:
    """Accept a single-image analysis: pre-create the run and spawn the worker.

    Performs the synchronous validations that must return immediate errors
    (consent, image read+validate, idempotency conflict) inside a short
    request-owned RLS transaction, creates the run in ``processing`` status via
    ``create_supplement_analysis_intake(initial_status=PROCESSING)``, captures the
    image bytes, then schedules :func:`run_single_supplement_analysis_job` and
    returns 202. A reused (already-processing/terminal) row does NOT spawn a
    duplicate worker — its current status is returned as-is.

    Args:
        http_request: Current FastAPI request.
        current_user: Authenticated owner.
        image: Uploaded supplement label image.
        session: Request-scoped async session from ``get_async_session``.
        settings: Application settings.
        adapters: Default OCR/parser/vision adapters.
        ocr_provider: Request-selected OCR provider.
        client_request_id: Optional client idempotency key.

    Returns:
        202 accepted envelope pointing at the poll URL.

    Raises:
        HTTPException: 403 (consent), 409 (idempotency conflict), or the image
            validation status code (413/415/422).
    """
    selected_adapters = _select_supplement_image_analysis_adapters(
        settings=settings,
        configured_adapters=adapters,
        ocr_provider=ocr_provider,
    )
    request_snapshot = _capture_request_metadata(http_request)
    # Stable, non-null idempotency key so the worker reuses this pre-created run
    # rather than creating a separate one when the client omits client_request_id.
    effective_client_request_id = client_request_id or f"async-{uuid4()}"
    async with rls_request_transaction(session, current_user, settings):
        await _require_supplement_analyze_consents(
            session=session,
            current_user=current_user,
            http_request=http_request,
            settings=settings,
            ocr_provider=ocr_provider,
            blocked_action="supplement_image_intake_blocked",
        )
        learning_consents = await _collect_learning_consents_if_enabled(
            session,
            current_user,
            settings,
        )
        try:
            metadata, image_bytes = await _capture_validated_image(image, settings)
            intake = await create_supplement_analysis_intake(
                session=session,
                user=current_user,
                image_metadata=metadata,
                client_request_id=effective_client_request_id,
                settings=settings,
                initial_status=SupplementAnalysisStatus.PROCESSING,
            )
        except SupplementImageValidationError as exc:
            await record_sensitive_audit_event(
                session,
                current_user,
                action="supplement_image_intake_rejected",
                resource_type="supplement_analysis_run",
                resource_id=None,
                outcome="blocked",
                request=http_request,
                settings=settings,
                event_metadata={"validation_code": exc.code},
            )
            raise HTTPException(
                status_code=exc.status_code,
                detail={"code": exc.code, "message": exc.message},
            ) from exc
        except SupplementIntakeConflictError as exc:
            await record_sensitive_audit_event(
                session,
                current_user,
                action="supplement_image_intake_conflict",
                resource_type="supplement_analysis_run",
                resource_id=None,
                outcome="blocked",
                request=http_request,
                settings=settings,
                event_metadata={"client_request_id_present": bool(client_request_id)},
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "idempotency_conflict", "message": str(exc)},
            ) from exc

        record = intake.record
        analysis_id = record.id
        expires_at = record.expires_at
        current_status = SupplementAnalysisStatus(record.status)
        spawn_worker = not intake.reused_existing
        await record_sensitive_audit_event(
            session,
            current_user,
            action="supplement_image_intake_accepted",
            resource_type="supplement_analysis_run",
            resource_id=str(analysis_id),
            outcome="success",
            request=http_request,
            settings=settings,
            event_metadata={
                "client_request_id_present": bool(client_request_id),
                "image_mime_type": metadata.mime_type,
                "image_size_bytes": metadata.size_bytes,
                "reused_existing": intake.reused_existing,
                "worker_scheduled": spawn_worker,
                "async_worker": True,
            },
        )

    if spawn_worker:
        captured = CapturedImage(
            analysis_id=analysis_id,
            client_request_id=effective_client_request_id,
            image_bytes=image_bytes,
            content_type=image.content_type,
            filename=image.filename or "supplement-label",
        )
        _spawn_analysis_worker(
            run_single_supplement_analysis_job(
                analysis_id=analysis_id,
                captured=captured,
                user=current_user,
                settings=settings,
                adapters=selected_adapters,
                http_request=request_snapshot,
                learning_consents=learning_consents,
            )
        )
    return SupplementAnalysisAccepted(
        analysis_id=analysis_id,
        status=current_status,
        poll_url=f"{SUPPLEMENT_ANALYSIS_POLL_PATH}/{analysis_id}",
        expires_at=expires_at,
    )


@router.post(
    "/analyze",
    # response_model is None because this route returns a union: the accepted
    # envelope (SupplementAnalysisAccepted) when supplement_analyze_async_enabled
    # is on, or the full preview (SupplementAnalysisPreviewWithRecommendation) on
    # the synchronous path. Each branch returns its own validated Pydantic model.
    response_model=None,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        **SUPPLEMENT_AUTH_RESPONSES,
        202: {"content": {"application/json": {"examples": SUPPLEMENT_ANALYSIS_RESPONSE_EXAMPLES}}},
        413: {"content": {"application/json": {"examples": PAYLOAD_TOO_LARGE_EXAMPLE}}},
        409: {
            "description": "client_request_id was already used for different image bytes.",
        },
        415: {"content": {"application/json": {"examples": UNSUPPORTED_MEDIA_TYPE_EXAMPLE}}},
        429: {"content": {"application/json": {"examples": TOO_MANY_REQUESTS_EXAMPLE}}},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.SUPPLEMENT_WRITE,),
        consents=(ConsentType.OCR_IMAGE_PROCESSING,),
        conditional_consents=(ConsentType.EXTERNAL_OCR_PROCESSING,),
        contract_status=P1_2_INTAKE_READY_STATUS,
    ),
)
async def analyze_supplement_label(
    http_request: Request,
    background_tasks: BackgroundTasks,
    current_user: Annotated[AuthenticatedUser, Depends(require_supplement_write)],
    image: Annotated[UploadFile, File(description="Supplement label image file.")],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    adapters: Annotated[
        SupplementImageAnalysisAdapters,
        Depends(get_supplement_image_analysis_adapters),
    ],
    barcode_service: Annotated[
        SupplementBarcodeLookupService,
        Depends(get_supplement_barcode_lookup_service),
    ],
    client_request_id: Annotated[str | None, Form(max_length=80)] = None,
    ocr_provider: Annotated[SupplementOCRProviderSelector, Form()] = "configured",
    barcode_text: Annotated[str | None, Form(max_length=256)] = None,
    barcode_format: Annotated[str | None, Form(max_length=40)] = None,
    with_recommendation: Annotated[
        bool,
        Query(
            description=(
                "Opt-in: also return a safe recommendation for the scanned label in the "
                "same request (single-flow). Uses only OCR-consent context (no profile/medical). "
                "Default false preserves the analyze-then-explain two-step flow."
            )
        ),
    ] = False,
    recommendation_use_local_llm: Annotated[
        bool,
        Query(description="When with_recommendation, attempt local Ollama wording refinement."),
    ] = False,
) -> SupplementAnalysisPreviewWithRecommendation | SupplementAnalysisAccepted:
    """Create a supplement label preview that must be confirmed by the user.

    Args:
        http_request: Current FastAPI request.
        current_user: Authenticated owner.
        image: Uploaded supplement label image.
        session: Request-scoped async database session.
        settings: Application settings.
        client_request_id: Optional idempotency key generated by the client.
        ocr_provider: Request-level OCR provider selector for comparison testing.
        barcode_text: Optional mobile-scanned barcode text.
        barcode_format: Optional mobile scanner format label.

    Returns:
        Supplement parsing preview.

    Raises:
        HTTPException: If consent is missing, image validation fails, or idempotency conflicts.
    """
    if settings.supplement_analyze_async_enabled:
        # Async path (flag ON): create the run row in `processing`, hand the
        # pipeline to an in-process worker, and return 202 immediately so the
        # heavy OCR/parse never blocks the request past the mobile upload timeout.
        return await _submit_async_single_analysis(
            http_request=http_request,
            current_user=current_user,
            image=image,
            session=session,
            settings=settings,
            adapters=adapters,
            ocr_provider=ocr_provider,
            client_request_id=client_request_id,
        )
    selected_adapters = _select_supplement_image_analysis_adapters(
        settings=settings,
        configured_adapters=adapters,
        ocr_provider=ocr_provider,
    )
    required_consents = _required_supplement_analyze_consents(settings, ocr_provider)
    missing_consents: list[ConsentType] = []
    last_consent_error: ConsentRequiredError | None = None
    # Route-owned RLS transaction: owner reads/writes participate in one request
    # transaction that commits in the route body — before the response and the
    # post-commit learning BackgroundTask run. See rls_request_transaction.
    async with rls_request_transaction(session, current_user, settings):
        for consent_type in required_consents:
            try:
                await require_user_consent(session, current_user, consent_type)
            except ConsentRequiredError as exc:
                missing_consents.append(consent_type)
                last_consent_error = exc

        if missing_consents:
            missing_values = [consent.value for consent in missing_consents]
            await record_sensitive_audit_event(
                session,
                current_user,
                action=(
                    "supplement_external_ocr_blocked"
                    if ConsentType.EXTERNAL_OCR_PROCESSING in missing_consents
                    else "supplement_image_intake_blocked"
                ),
                resource_type="supplement_analysis_run",
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
                    "message": str(last_consent_error),
                    "required_consents": missing_values,
                },
            ) from last_consent_error

        try:
            learning_consents = await _collect_learning_consents_if_enabled(
                session,
                current_user,
                settings,
            )
            result = await analyze_supplement_image(
                session=session,
                user=current_user,
                image=image,
                client_request_id=client_request_id,
                settings=settings,
                adapters=selected_adapters,
                learning_consents=learning_consents,
            )
            if result.learning_artifacts is not None:
                background_tasks.add_task(
                    store_supplement_learning_artifacts,
                    user=current_user,
                    artifacts=result.learning_artifacts,
                    settings=settings,
                    object_store=build_learning_object_store(settings),
                )
            barcode_lookup_result: BarcodeLookupServiceResult | None = None
            if barcode_text and barcode_text.strip():
                barcode_lookup_result = await barcode_service.lookup(
                    barcode_text,
                    barcode_format=barcode_format,
                )
                result_record = await attach_barcode_lookup_to_analysis(
                    session,
                    result.record,
                    barcode_lookup_result,
                )
            else:
                result_record = result.record
        except SupplementImageValidationError as exc:
            await record_sensitive_audit_event(
                session,
                current_user,
                action="supplement_image_intake_rejected",
                resource_type="supplement_analysis_run",
                resource_id=None,
                outcome="blocked",
                request=http_request,
                settings=settings,
                event_metadata={"validation_code": exc.code},
            )
            raise HTTPException(
                status_code=exc.status_code,
                detail={"code": exc.code, "message": exc.message},
            ) from exc
        except SupplementIntakeConflictError as exc:
            await record_sensitive_audit_event(
                session,
                current_user,
                action="supplement_image_intake_conflict",
                resource_type="supplement_analysis_run",
                resource_id=None,
                outcome="blocked",
                request=http_request,
                settings=settings,
                event_metadata={"client_request_id_present": bool(client_request_id)},
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "idempotency_conflict",
                    "message": str(exc),
                },
            ) from exc

        # Success audits stay inside the request transaction so they run
        # out-of-band (record_audit_event branches on the request-managed
        # marker); outside the block they would take the legacy in-session
        # INSERT path that the lemon_app request role cannot perform post-flip.
        if result.ocr_attempted:
            provider_warning_codes = _ocr_provider_warning_codes(result.ocr_warning_codes)
            await record_sensitive_audit_event(
                session,
                current_user,
                action=(
                    "supplement_ocr_provider_failed"
                    if provider_warning_codes
                    else "supplement_ocr_provider_completed"
                ),
                resource_type="supplement_analysis_run",
                resource_id=str(result.record.id),
                outcome="failed" if provider_warning_codes else "success",
                request=http_request,
                settings=settings,
                event_metadata={
                    "ocr_provider": result.ocr_result.provider if result.ocr_result else None,
                    "ocr_confidence_present": (
                        result.ocr_result.confidence is not None if result.ocr_result else False
                    ),
                    "warning_codes": provider_warning_codes,
                    "raw_image_stored": False,
                    "raw_ocr_text_stored": False,
                },
            )

        await record_sensitive_audit_event(
            session,
            current_user,
            action=(
                "supplement_image_intake_reused"
                if result.reused_existing
                else "supplement_image_intake_created"
            ),
            resource_type="supplement_analysis_run",
            resource_id=str(result.record.id),
            outcome="success",
            request=http_request,
            settings=settings,
            event_metadata={
                "client_request_id_present": bool(client_request_id),
                "image_mime_type": result.image_metadata.mime_type,
                "image_size_bytes": result.image_metadata.size_bytes,
                "reused_existing": result.reused_existing,
                "ocr_provider": result.ocr_result.provider if result.ocr_result else None,
                "parser_used": result.parser_used,
                "vision_roi_used": result.vision_region is not None,
                "image_quality_status": (
                    result.image_quality_report.status if result.image_quality_report else None
                ),
                "image_quality_retake_reasons": (
                    list(result.image_quality_report.retake_reasons)
                    if result.image_quality_report
                    else []
                ),
                "learning_image_object_scheduled": result.learning_artifacts is not None,
                "barcode_text_present": bool(barcode_text and barcode_text.strip()),
                "barcode_lookup_status": (
                    barcode_lookup_result.status if barcode_lookup_result is not None else None
                ),
            },
        )
    combined = SupplementAnalysisPreviewWithRecommendation.model_validate(
        supplement_analysis_run_to_preview(result_record).model_dump()
    )
    if with_recommendation:
        # Single-flow opt-in: explain the just-scanned label using only OCR-consent
        # context (no profile/medical -> no extra consent). Degrade gracefully to a
        # preview-only response if recommendation generation is unavailable/unsafe.
        try:
            combined.recommendation = await explain_supplement_analysis_preview(
                result_record,
                SupplementAnalysisExplainRequest(use_local_llm=recommendation_use_local_llm),
                settings,
            )
        except (SupplementExplanationError, ValueError, OSError):
            combined.recommendation = None
    return combined


@router.post(
    "/analysis-sessions",
    response_model=SupplementAnalysisSessionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        **SUPPLEMENT_AUTH_RESPONSES,
        422: {"content": {"application/json": {"examples": UNPROCESSABLE_ENTITY_EXAMPLE}}},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.SUPPLEMENT_WRITE,),
        consents=(ConsentType.OCR_IMAGE_PROCESSING,),
        contract_status=P1_2_INTAKE_READY_STATUS,
    ),
)
async def create_supplement_analysis_session(
    http_request: Request,
    current_user: Annotated[AuthenticatedUser, Depends(require_supplement_write)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SupplementAnalysisSessionResponse:
    """Create a lightweight multi-image supplement analysis session id.

    Args:
        http_request: Current FastAPI request.
        current_user: Authenticated owner.
        session: Request-scoped async database session.
        settings: Application settings.

    Returns:
        Backend-created group id for subsequent session image uploads.

    Raises:
        HTTPException: If OCR image processing consent is missing.
    """
    try:
        await require_user_consent(
            session,
            current_user,
            ConsentType.OCR_IMAGE_PROCESSING,
        )
    except ConsentRequiredError as exc:
        await record_sensitive_audit_event(
            session,
            current_user,
            action="supplement_image_analysis_session_create_blocked",
            resource_type="supplement_analysis_run",
            resource_id=None,
            outcome="blocked",
            request=http_request,
            settings=settings,
            event_metadata={"missing_consents": [ConsentType.OCR_IMAGE_PROCESSING.value]},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "consent_required",
                "message": str(exc),
                "required_consents": [ConsentType.OCR_IMAGE_PROCESSING.value],
            },
        ) from exc

    response = _build_analysis_session_response(f"multi-{uuid4()}")
    await record_sensitive_audit_event(
        session,
        current_user,
        action="supplement_image_analysis_session_created",
        resource_type="supplement_analysis_run",
        resource_id=None,
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={
            "image_count": 0,
            "max_images": response.max_images,
            "raw_image_stored": False,
            "raw_ocr_text_stored": False,
        },
    )
    return response


@router.post(
    "/analysis-sessions/{analysis_group_id}/images",
    response_model=SupplementMultiImageAnalysisPreview,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        **SUPPLEMENT_AUTH_RESPONSES,
        413: {"content": {"application/json": {"examples": PAYLOAD_TOO_LARGE_EXAMPLE}}},
        409: {
            "description": "client_request_id was already used for different image bytes.",
        },
        415: {"content": {"application/json": {"examples": UNSUPPORTED_MEDIA_TYPE_EXAMPLE}}},
        422: {"content": {"application/json": {"examples": UNPROCESSABLE_ENTITY_EXAMPLE}}},
        429: {"content": {"application/json": {"examples": TOO_MANY_REQUESTS_EXAMPLE}}},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.SUPPLEMENT_WRITE,),
        consents=(ConsentType.OCR_IMAGE_PROCESSING,),
        conditional_consents=(ConsentType.EXTERNAL_OCR_PROCESSING,),
        contract_status=P1_2_INTAKE_READY_STATUS,
    ),
)
async def upload_supplement_analysis_session_image(
    http_request: Request,
    background_tasks: BackgroundTasks,
    analysis_group_id: Annotated[
        str,
        Path(
            min_length=1,
            max_length=120,
            description="Backend-created multi-image analysis group id.",
        ),
    ],
    current_user: Annotated[AuthenticatedUser, Depends(require_supplement_write)],
    image: Annotated[
        UploadFile,
        File(description="Supplement label image file for this analysis session."),
    ],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    adapters: Annotated[
        SupplementImageAnalysisAdapters,
        Depends(get_supplement_image_analysis_adapters),
    ],
    client_request_id: Annotated[str | None, Form(max_length=80)] = None,
    ocr_provider: Annotated[SupplementOCRProviderSelector, Form()] = "configured",
    image_role: Annotated[str, Form(max_length=80)] = "unknown",
) -> SupplementMultiImageAnalysisPreview:
    """Upload one image into a multi-photo supplement analysis session.

    Args:
        http_request: Current FastAPI request.
        analysis_group_id: Backend-created multi-image analysis group id.
        current_user: Authenticated owner.
        image: Uploaded supplement label image.
        session: Request-scoped async database session.
        settings: Application settings.
        adapters: Configured OCR/parser/vision adapters.
        client_request_id: Optional per-image client idempotency hint.
        ocr_provider: Request-level OCR provider selector.
        image_role: Role label for this image.

    Returns:
        Batch preview containing all current session image previews.

    Raises:
        HTTPException: If consent, image validation, role validation, or idempotency fails.
    """
    [validated_role] = _validate_multi_image_roles(1, [image_role])
    selected_adapters = _select_supplement_image_analysis_adapters(
        settings=settings,
        configured_adapters=adapters,
        ocr_provider=ocr_provider,
    )
    required_consents = _required_supplement_analyze_consents(settings, ocr_provider)
    missing_consents: list[ConsentType] = []
    last_consent_error: ConsentRequiredError | None = None
    # Route-owned RLS transaction (see rls_request_transaction): owner reads/writes
    # commit in the route body, before the post-commit learning BackgroundTask runs.
    async with rls_request_transaction(session, current_user, settings):
        for consent_type in required_consents:
            try:
                await require_user_consent(session, current_user, consent_type)
            except ConsentRequiredError as exc:
                missing_consents.append(consent_type)
                last_consent_error = exc

        if missing_consents:
            missing_values = [consent.value for consent in missing_consents]
            await record_sensitive_audit_event(
                session,
                current_user,
                action=(
                    "supplement_external_ocr_blocked"
                    if ConsentType.EXTERNAL_OCR_PROCESSING in missing_consents
                    else "supplement_image_analysis_session_image_blocked"
                ),
                resource_type="supplement_analysis_run",
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
                    "message": str(last_consent_error),
                    "required_consents": missing_values,
                },
            ) from last_consent_error

        existing_runs = await _load_multi_image_analysis_runs(
            session,
            owner_subject=build_owner_subject(current_user),
            analysis_group_id=analysis_group_id,
        )
        if len(existing_runs) >= MAX_MULTI_IMAGE_ANALYSIS_IMAGES:
            raise _supplement_http_error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="image_count_invalid",
                message=f"Upload between 1 and {MAX_MULTI_IMAGE_ANALYSIS_IMAGES} images.",
            )

        try:
            learning_consents = await _collect_learning_consents_if_enabled(
                session,
                current_user,
                settings,
            )
            result = await analyze_supplement_image(
                session=session,
                user=current_user,
                image=image,
                client_request_id=_session_image_client_request_id(
                    analysis_group_id,
                    client_request_id,
                    validated_role,
                ),
                settings=settings,
                adapters=selected_adapters,
                learning_consents=learning_consents,
            )
            if result.learning_artifacts is not None:
                background_tasks.add_task(
                    store_supplement_learning_artifacts,
                    user=current_user,
                    artifacts=result.learning_artifacts,
                    settings=settings,
                    object_store=build_learning_object_store(settings),
                )
            await _annotate_multi_image_record(
                session,
                result.record,
                image_role=validated_role,
                analysis_group_id=analysis_group_id,
                image_count=len(existing_runs) + 1,
            )
            if result.ocr_attempted:
                provider_warning_codes = _ocr_provider_warning_codes(result.ocr_warning_codes)
                await record_sensitive_audit_event(
                    session,
                    current_user,
                    action=(
                        "supplement_ocr_provider_failed"
                        if provider_warning_codes
                        else "supplement_ocr_provider_completed"
                    ),
                    resource_type="supplement_analysis_run",
                    resource_id=str(result.record.id),
                    outcome="failed" if provider_warning_codes else "success",
                    request=http_request,
                    settings=settings,
                    event_metadata={
                        "ocr_provider": result.ocr_result.provider if result.ocr_result else None,
                        "ocr_confidence_present": (
                            result.ocr_result.confidence is not None if result.ocr_result else False
                        ),
                        "warning_codes": provider_warning_codes,
                        "raw_image_stored": False,
                        "raw_ocr_text_stored": False,
                    },
                )
        except SupplementImageValidationError as exc:
            await record_sensitive_audit_event(
                session,
                current_user,
                action="supplement_image_analysis_session_image_rejected",
                resource_type="supplement_analysis_run",
                resource_id=None,
                outcome="blocked",
                request=http_request,
                settings=settings,
                event_metadata={"validation_code": exc.code},
            )
            raise HTTPException(
                status_code=exc.status_code,
                detail={"code": exc.code, "message": exc.message},
            ) from exc
        except SupplementIntakeConflictError as exc:
            await record_sensitive_audit_event(
                session,
                current_user,
                action="supplement_image_analysis_session_image_conflict",
                resource_type="supplement_analysis_run",
                resource_id=None,
                outcome="blocked",
                request=http_request,
                settings=settings,
                event_metadata={"client_request_id_present": bool(client_request_id)},
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "idempotency_conflict",
                    "message": str(exc),
                },
            ) from exc

        analysis_runs = await _load_multi_image_analysis_runs(
            session,
            owner_subject=build_owner_subject(current_user),
            analysis_group_id=analysis_group_id,
        )
        await _refresh_multi_image_count(session, analysis_runs)
        previews = [supplement_analysis_run_to_preview(record) for record in analysis_runs]
        response = _build_multi_image_response(
            analysis_group_id=analysis_group_id,
            previews=previews,
        )
        # In-transaction success audit → out-of-band writer (see route 1 note).
        await record_sensitive_audit_event(
            session,
            current_user,
            action="supplement_image_analysis_session_image_uploaded",
            resource_type="supplement_analysis_run",
            resource_id=None,
            outcome="success",
            request=http_request,
            settings=settings,
            event_metadata={
                "image_count": response.image_count,
                "ocr_provider": response.pipeline_metadata.ocr_provider,
                "missing_required_sections": list(response.missing_required_sections),
                "raw_image_stored": False,
                "raw_ocr_text_stored": False,
            },
        )
    return response


async def _submit_async_multi_analysis(
    *,
    http_request: Request,
    current_user: AuthenticatedUser,
    images: list[UploadFile],
    roles: list[str],
    session: AsyncSession,
    settings: Settings,
    adapters: SupplementImageAnalysisAdapters,
    ocr_provider: SupplementOCRProviderSelector,
    client_request_id: str | None,
    merge_strategy: Literal["single_product", "distinct_products"],
) -> SupplementMultiImageAnalysisAccepted:
    """Accept a multi-image batch: pre-create the runs and spawn the worker.

    Validates consent, reads+validates every image, and creates one
    ``processing`` run per image (pre-annotated with the generated
    ``analysis_group_id`` so the group poll can find them) inside a short
    request-owned RLS transaction, then schedules
    :func:`run_multi_supplement_analysis_job` and returns 202.

    Args:
        http_request: Current FastAPI request.
        current_user: Authenticated owner.
        images: Uploaded supplement label images.
        roles: Validated per-image role labels.
        session: Request-scoped async session from ``get_async_session``.
        settings: Application settings.
        adapters: Default OCR/parser/vision adapters.
        ocr_provider: Request-selected OCR provider.
        client_request_id: Optional batch idempotency hint.
        merge_strategy: ``single_product`` or ``distinct_products``.

    Returns:
        202 accepted batch envelope pointing at the group poll URL.

    Raises:
        HTTPException: 403 (consent), 409 (idempotency conflict), or the image
            validation status code (413/415/422).
    """
    selected_adapters = _select_supplement_image_analysis_adapters(
        settings=settings,
        configured_adapters=adapters,
        ocr_provider=ocr_provider,
    )
    request_snapshot = _capture_request_metadata(http_request)
    analysis_group_id = f"multi-{uuid4()}"
    # The worker reuses each pre-created run via its per-image idempotency key, so
    # the key must be stable and non-null even when the client omits
    # client_request_id (the group id is per-request unique). Without this the
    # worker's intake derives a null key and creates separate rows, orphaning the
    # processing rows this submit returned for polling.
    effective_client_request_id = client_request_id or analysis_group_id
    captured_images: list[CapturedImage] = []
    analysis_ids: list[UUID] = []
    expirations: list[datetime] = []
    async with rls_request_transaction(session, current_user, settings):
        await _require_supplement_analyze_consents(
            session=session,
            current_user=current_user,
            http_request=http_request,
            settings=settings,
            ocr_provider=ocr_provider,
            blocked_action="supplement_image_multi_intake_blocked",
        )
        learning_consents = await _collect_learning_consents_if_enabled(
            session,
            current_user,
            settings,
        )
        try:
            for index, image in enumerate(images):
                metadata, image_bytes = await _capture_validated_image(image, settings)
                per_image_request_id = _multi_image_client_request_id(
                    effective_client_request_id, index
                )
                intake = await create_supplement_analysis_intake(
                    session=session,
                    user=current_user,
                    image_metadata=metadata,
                    client_request_id=per_image_request_id,
                    settings=settings,
                    initial_status=SupplementAnalysisStatus.PROCESSING,
                )
                # Pre-annotate the group id so the group poll finds the still-
                # processing rows before the worker writes the parsed snapshot.
                await _annotate_multi_image_record(
                    session,
                    intake.record,
                    image_role=roles[index],
                    analysis_group_id=analysis_group_id,
                    image_count=len(images),
                )
                analysis_ids.append(intake.record.id)
                expirations.append(intake.record.expires_at)
                captured_images.append(
                    CapturedImage(
                        analysis_id=intake.record.id,
                        client_request_id=per_image_request_id,
                        image_bytes=image_bytes,
                        content_type=image.content_type,
                        filename=image.filename or "supplement-label",
                        image_role=roles[index],
                    )
                )
        except SupplementImageValidationError as exc:
            await record_sensitive_audit_event(
                session,
                current_user,
                action="supplement_image_multi_intake_rejected",
                resource_type="supplement_analysis_run",
                resource_id=None,
                outcome="blocked",
                request=http_request,
                settings=settings,
                event_metadata={"validation_code": exc.code},
            )
            raise HTTPException(
                status_code=exc.status_code,
                detail={"code": exc.code, "message": exc.message},
            ) from exc
        except SupplementIntakeConflictError as exc:
            await record_sensitive_audit_event(
                session,
                current_user,
                action="supplement_image_multi_intake_conflict",
                resource_type="supplement_analysis_run",
                resource_id=None,
                outcome="blocked",
                request=http_request,
                settings=settings,
                event_metadata={"client_request_id_present": bool(client_request_id)},
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "idempotency_conflict", "message": str(exc)},
            ) from exc

        await record_sensitive_audit_event(
            session,
            current_user,
            action="supplement_image_multi_intake_accepted",
            resource_type="supplement_analysis_run",
            resource_id=None,
            outcome="success",
            request=http_request,
            settings=settings,
            event_metadata={
                "image_count": len(images),
                "merge_strategy": merge_strategy,
                "raw_image_stored": False,
                "raw_ocr_text_stored": False,
                "async_worker": True,
            },
        )

    _spawn_analysis_worker(
        run_multi_supplement_analysis_job(
            analysis_group_id=analysis_group_id,
            captured_images=captured_images,
            image_roles=roles,
            merge_strategy=merge_strategy,
            user=current_user,
            settings=settings,
            adapters=selected_adapters,
            http_request=request_snapshot,
            learning_consents=learning_consents,
        )
    )
    return SupplementMultiImageAnalysisAccepted(
        analysis_group_id=analysis_group_id,
        analysis_ids=analysis_ids,
        status=SupplementAnalysisStatus.PROCESSING,
        poll_url=f"{SUPPLEMENT_ANALYSIS_POLL_PATH}/group/{analysis_group_id}",
        expires_at=min(expirations),
    )


@router.post(
    "/analyze-multi",
    # response_model is None because this route returns a union: the accepted
    # batch envelope (SupplementMultiImageAnalysisAccepted) when async is enabled,
    # or the full batch preview (SupplementMultiImageAnalysisPreview) on the
    # synchronous path. Each branch returns its own validated Pydantic model.
    response_model=None,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        **SUPPLEMENT_AUTH_RESPONSES,
        413: {"content": {"application/json": {"examples": PAYLOAD_TOO_LARGE_EXAMPLE}}},
        409: {
            "description": "client_request_id was already used for different image bytes.",
        },
        415: {"content": {"application/json": {"examples": UNSUPPORTED_MEDIA_TYPE_EXAMPLE}}},
        422: {"content": {"application/json": {"examples": UNPROCESSABLE_ENTITY_EXAMPLE}}},
        429: {"content": {"application/json": {"examples": TOO_MANY_REQUESTS_EXAMPLE}}},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.SUPPLEMENT_WRITE,),
        consents=(ConsentType.OCR_IMAGE_PROCESSING,),
        conditional_consents=(ConsentType.EXTERNAL_OCR_PROCESSING,),
        contract_status=P1_2_INTAKE_READY_STATUS,
    ),
)
async def analyze_supplement_label_multi(
    http_request: Request,
    background_tasks: BackgroundTasks,
    current_user: Annotated[AuthenticatedUser, Depends(require_supplement_write)],
    images: Annotated[
        list[UploadFile],
        File(description="Supplement label image files for one review batch."),
    ],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    adapters: Annotated[
        SupplementImageAnalysisAdapters,
        Depends(get_supplement_image_analysis_adapters),
    ],
    client_request_id: Annotated[str | None, Form(max_length=80)] = None,
    ocr_provider: Annotated[SupplementOCRProviderSelector, Form()] = "configured",
    image_roles: Annotated[list[str] | None, Form()] = None,
    image_roles_json: Annotated[str | None, Form(max_length=1000)] = None,
    merge_strategy: Annotated[
        Literal["single_product", "distinct_products"], Form()
    ] = "distinct_products",
) -> SupplementMultiImageAnalysisPreview | SupplementMultiImageAnalysisAccepted:
    """Create per-image previews for a multi-photo supplement label batch.

    Args:
        http_request: Current FastAPI request.
        current_user: Authenticated owner.
        images: Uploaded supplement label images.
        session: Request-scoped async database session.
        settings: Application settings.
        adapters: Configured OCR/parser/vision adapters.
        client_request_id: Optional batch idempotency hint.
        ocr_provider: Request-level OCR provider selector.
        image_roles: Optional role labels aligned one-to-one with ``images``.
        image_roles_json: Optional JSON-encoded roles for multipart clients that
            cannot repeat form field names.

    Returns:
        Batch preview containing existing per-image analysis previews.

    Raises:
        HTTPException: If consent, image validation, role validation, or idempotency fails.
    """
    roles = _validate_multi_image_roles(len(images), image_roles, image_roles_json)
    # One-shot single-product fusion runs synchronously: it OCRs every image and parses
    # ONCE into a SINGLE run so 3 photos of one product become one supplement. The async
    # per-image worker has no fusion mode, so route single_product through the sync fusion
    # path below; distinct_products still uses the async per-image worker.
    use_one_shot_fusion = (
        merge_strategy == "single_product" and settings.supplement_one_shot_fusion_enabled
    )
    if settings.supplement_analyze_async_enabled and not use_one_shot_fusion:
        # Async path (flag ON): pre-create every per-image run in `processing`,
        # hand the batch to an in-process worker, and return 202 immediately.
        return await _submit_async_multi_analysis(
            http_request=http_request,
            current_user=current_user,
            images=images,
            roles=roles,
            session=session,
            settings=settings,
            adapters=adapters,
            ocr_provider=ocr_provider,
            client_request_id=client_request_id,
            merge_strategy=merge_strategy,
        )
    selected_adapters = _select_supplement_image_analysis_adapters(
        settings=settings,
        configured_adapters=adapters,
        ocr_provider=ocr_provider,
    )
    required_consents = _required_supplement_analyze_consents(settings, ocr_provider)
    missing_consents: list[ConsentType] = []
    last_consent_error: ConsentRequiredError | None = None
    # Route-owned RLS transaction (see rls_request_transaction): all per-image
    # owner writes commit in the route body, before the post-commit learning
    # BackgroundTasks run.
    async with rls_request_transaction(session, current_user, settings):
        for consent_type in required_consents:
            try:
                await require_user_consent(session, current_user, consent_type)
            except ConsentRequiredError as exc:
                missing_consents.append(consent_type)
                last_consent_error = exc

        if missing_consents:
            missing_values = [consent.value for consent in missing_consents]
            await record_sensitive_audit_event(
                session,
                current_user,
                action=(
                    "supplement_external_ocr_blocked"
                    if ConsentType.EXTERNAL_OCR_PROCESSING in missing_consents
                    else "supplement_image_multi_intake_blocked"
                ),
                resource_type="supplement_analysis_run",
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
                    "message": str(last_consent_error),
                    "required_consents": missing_values,
                },
            ) from last_consent_error

        analysis_group_id = f"multi-{uuid4()}"
        previews: list[SupplementAnalysisPreview] = []
        try:
            learning_consents = await _collect_learning_consents_if_enabled(
                session,
                current_user,
                settings,
            )
            if merge_strategy == "single_product" and settings.supplement_one_shot_fusion_enabled:
                # One-shot fusion: OCR every image in-request, fuse the text, and
                # parse ONCE into a single run so the model reasons over the whole
                # label. Raw OCR text is never persisted.
                fused_result = await analyze_fused_supplement_images(
                    session=session,
                    user=current_user,
                    images=images,
                    image_roles=roles,
                    client_request_id=client_request_id,
                    settings=settings,
                    adapters=selected_adapters,
                    learning_consents=learning_consents,
                )
                # One learning artifact per image: the fused parse is a single
                # preview, but the section-detector dataset needs each image with
                # its own layout-bearing OCR result. Schedule one post-commit task
                # per image (all link to the single fused run id).
                for fused_learning_artifact in fused_result.learning_artifacts_per_image:
                    background_tasks.add_task(
                        store_supplement_learning_artifacts,
                        user=current_user,
                        artifacts=fused_learning_artifact,
                        settings=settings,
                        object_store=build_learning_object_store(settings),
                    )
                await _annotate_multi_image_record(
                    session,
                    fused_result.record,
                    image_role="mixed",
                    analysis_group_id=analysis_group_id,
                    image_count=len(images),
                )
                if fused_result.ocr_attempted:
                    provider_warning_codes = _ocr_provider_warning_codes(
                        fused_result.ocr_warning_codes
                    )
                    await record_sensitive_audit_event(
                        session,
                        current_user,
                        action=(
                            "supplement_ocr_provider_failed"
                            if provider_warning_codes
                            else "supplement_ocr_provider_completed"
                        ),
                        resource_type="supplement_analysis_run",
                        resource_id=str(fused_result.record.id),
                        outcome="failed" if provider_warning_codes else "success",
                        request=http_request,
                        settings=settings,
                        event_metadata={
                            "ocr_provider": (
                                fused_result.ocr_result.provider
                                if fused_result.ocr_result
                                else None
                            ),
                            "ocr_confidence_present": (
                                fused_result.ocr_result.confidence is not None
                                if fused_result.ocr_result
                                else False
                            ),
                            "warning_codes": provider_warning_codes,
                            "raw_image_stored": False,
                            "raw_ocr_text_stored": False,
                            "merge_strategy": "single_product",
                        },
                    )
                fused_response = _build_multi_image_response(
                    analysis_group_id=analysis_group_id,
                    previews=[supplement_analysis_run_to_preview(fused_result.record)],
                )
                # In-transaction success audit → out-of-band writer (see route 1 note).
                await record_sensitive_audit_event(
                    session,
                    current_user,
                    action="supplement_image_multi_intake_created",
                    resource_type="supplement_analysis_run",
                    resource_id=None,
                    outcome="success",
                    request=http_request,
                    settings=settings,
                    event_metadata={
                        "image_count": len(images),
                        "ocr_provider": fused_response.pipeline_metadata.ocr_provider,
                        "parser_used": fused_response.pipeline_metadata.llm_parser_used,
                        "vision_roi_used": fused_response.pipeline_metadata.vision_roi_used,
                        "missing_required_sections": list(fused_response.missing_required_sections),
                        "raw_image_stored": False,
                        "raw_ocr_text_stored": False,
                        "merge_strategy": "single_product",
                    },
                )
                return fused_response
            for index, image in enumerate(images):
                result = await analyze_supplement_image(
                    session=session,
                    user=current_user,
                    image=image,
                    client_request_id=_multi_image_client_request_id(client_request_id, index),
                    settings=settings,
                    adapters=selected_adapters,
                    learning_consents=learning_consents,
                )
                if result.learning_artifacts is not None:
                    background_tasks.add_task(
                        store_supplement_learning_artifacts,
                        user=current_user,
                        artifacts=result.learning_artifacts,
                        settings=settings,
                        object_store=build_learning_object_store(settings),
                    )
                await _annotate_multi_image_record(
                    session,
                    result.record,
                    image_role=roles[index],
                    analysis_group_id=analysis_group_id,
                    image_count=len(images),
                )
                if result.ocr_attempted:
                    provider_warning_codes = _ocr_provider_warning_codes(result.ocr_warning_codes)
                    await record_sensitive_audit_event(
                        session,
                        current_user,
                        action=(
                            "supplement_ocr_provider_failed"
                            if provider_warning_codes
                            else "supplement_ocr_provider_completed"
                        ),
                        resource_type="supplement_analysis_run",
                        resource_id=str(result.record.id),
                        outcome="failed" if provider_warning_codes else "success",
                        request=http_request,
                        settings=settings,
                        event_metadata={
                            "ocr_provider": (
                                result.ocr_result.provider if result.ocr_result else None
                            ),
                            "ocr_confidence_present": (
                                result.ocr_result.confidence is not None
                                if result.ocr_result
                                else False
                            ),
                            "warning_codes": provider_warning_codes,
                            "raw_image_stored": False,
                            "raw_ocr_text_stored": False,
                        },
                    )
                previews.append(supplement_analysis_run_to_preview(result.record))
        except SupplementImageValidationError as exc:
            await record_sensitive_audit_event(
                session,
                current_user,
                action="supplement_image_multi_intake_rejected",
                resource_type="supplement_analysis_run",
                resource_id=None,
                outcome="blocked",
                request=http_request,
                settings=settings,
                event_metadata={"validation_code": exc.code},
            )
            raise HTTPException(
                status_code=exc.status_code,
                detail={"code": exc.code, "message": exc.message},
            ) from exc
        except SupplementIntakeConflictError as exc:
            await record_sensitive_audit_event(
                session,
                current_user,
                action="supplement_image_multi_intake_conflict",
                resource_type="supplement_analysis_run",
                resource_id=None,
                outcome="blocked",
                request=http_request,
                settings=settings,
                event_metadata={"client_request_id_present": bool(client_request_id)},
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "idempotency_conflict",
                    "message": str(exc),
                },
            ) from exc

        response = _build_multi_image_response(
            analysis_group_id=analysis_group_id,
            previews=previews,
            merge_strategy=merge_strategy,
        )
        # In-transaction success audit → out-of-band writer (see route 1 note).
        await record_sensitive_audit_event(
            session,
            current_user,
            action="supplement_image_multi_intake_created",
            resource_type="supplement_analysis_run",
            resource_id=None,
            outcome="success",
            request=http_request,
            settings=settings,
            event_metadata={
                "image_count": response.image_count,
                "ocr_provider": response.pipeline_metadata.ocr_provider,
                "parser_used": response.pipeline_metadata.llm_parser_used,
                "vision_roi_used": response.pipeline_metadata.vision_roi_used,
                "missing_required_sections": list(response.missing_required_sections),
                "raw_image_stored": False,
                "raw_ocr_text_stored": False,
            },
        )
    return response


def _analysis_run_is_stale(record: SupplementAnalysisRun, settings: Settings) -> bool:
    """Return whether a still-processing run has exceeded the worker deadline.

    A run left in ``processing`` past ``updated_at + worker_deadline`` means the
    in-process worker died (process restart / crash) without flipping the row, so
    the poll treats it as a timeout rather than polling forever.

    Args:
        record: Supplement analysis run row.
        settings: Application settings supplying the worker deadline.

    Returns:
        True when the processing run is older than the worker deadline.
    """
    if record.status != SupplementAnalysisStatus.PROCESSING.value:
        return False
    deadline = timedelta(seconds=settings.supplement_analyze_worker_deadline_sec)
    return datetime.now(UTC) - record.updated_at > deadline


def _failed_analysis_error(record: SupplementAnalysisRun) -> SupplementAnalysisError:
    """Build a safe coded error for a failed run from its warnings.

    Never surfaces raw exception text — only a bounded coded warning string if the
    worker recorded one, otherwise the generic ``analysis_failed`` code.

    Args:
        record: Failed supplement analysis run row.

    Returns:
        Safe coded analysis error.
    """
    warnings = [warning for warning in (record.warnings or []) if isinstance(warning, str)]
    code = warnings[0] if warnings else "analysis_failed"
    return SupplementAnalysisError(
        code=code[:80],
        message="Supplement label analysis could not be completed. Please try again.",
    )


@router.get(
    "/analyses/{analysis_id}",
    response_model=SupplementAnalysisStatusResponse,
    responses={
        **COMMON_SUPPLEMENT_RESPONSES,
        404: {"description": "Supplement analysis run was not found."},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.SUPPLEMENT_READ,),
        contract_status=P1_2_INTAKE_READY_STATUS,
    ),
)
async def poll_supplement_analysis(
    analysis_id: Annotated[UUID, Path(description="Async analysis run id to poll.")],
    current_user: Annotated[AuthenticatedUser, Depends(require_supplement_read)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SupplementAnalysisStatusResponse:
    """Poll the status (and, when ready, the preview) of an async analysis run.

    Owner-isolated read (RLS): a different subject cannot read another owner's run
    — the GUC-scoped session returns no row and the route answers 404. A
    still-processing run past the worker deadline is reported as a coded timeout.

    Args:
        analysis_id: Async analysis run id to poll.
        current_user: Authenticated owner (read scope only).
        session: Owner-scoped read session with RLS GUCs set.
        settings: Application settings supplying the worker deadline.

    Returns:
        Poll body: processing, failed (with safe error), or the ready preview.

    Raises:
        HTTPException: 404 when the run is not owned by the caller or missing.
    """
    record = await session.get(SupplementAnalysisRun, analysis_id)
    if record is None or record.owner_subject != build_owner_subject(current_user):
        raise _supplement_http_error(
            status.HTTP_404_NOT_FOUND,
            code="analysis_not_found",
            message="Supplement analysis run was not found.",
        )
    if _analysis_run_is_stale(record, settings):
        return SupplementAnalysisStatusResponse(
            status=SupplementAnalysisStatus.FAILED,
            error=SupplementAnalysisError(
                code="analysis_timeout",
                message="Supplement label analysis timed out. Please try again.",
            ),
        )
    status_value = SupplementAnalysisStatus(record.status)
    if status_value == SupplementAnalysisStatus.PROCESSING:
        return SupplementAnalysisStatusResponse(status=status_value)
    if status_value == SupplementAnalysisStatus.FAILED:
        return SupplementAnalysisStatusResponse(
            status=status_value,
            error=_failed_analysis_error(record),
        )
    return SupplementAnalysisStatusResponse(
        status=status_value,
        preview=supplement_analysis_run_to_preview(record),
    )


@router.get(
    "/analyses/group/{analysis_group_id}",
    response_model=SupplementMultiImageAnalysisStatusResponse,
    responses={
        **COMMON_SUPPLEMENT_RESPONSES,
        404: {"description": "Multi-image analysis group was not found."},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.SUPPLEMENT_READ,),
        contract_status=P1_2_INTAKE_READY_STATUS,
    ),
)
async def poll_supplement_analysis_group(
    analysis_group_id: Annotated[
        str,
        Path(max_length=120, description="Async multi-image analysis group id to poll."),
    ],
    current_user: Annotated[AuthenticatedUser, Depends(require_supplement_read)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SupplementMultiImageAnalysisStatusResponse:
    """Poll the aggregate status (and, when ready, the preview) of an async batch.

    Loads every owner run annotated with ``analysis_group_id`` (RLS-isolated, so
    another owner sees an empty group → 404). Aggregates: failed if any run failed
    or timed out, processing if any run is still processing, otherwise ready with
    the batch preview built by :func:`_build_multi_image_response`.

    Args:
        analysis_group_id: Async multi-image analysis group id to poll.
        current_user: Authenticated owner (read scope only).
        session: Owner-scoped read session with RLS GUCs set.
        settings: Application settings supplying the worker deadline.

    Returns:
        Aggregate poll body: processing, failed (with safe error), or ready batch.

    Raises:
        HTTPException: 404 when the group has no runs owned by the caller.
    """
    records = await _load_multi_image_analysis_runs(
        session,
        owner_subject=build_owner_subject(current_user),
        analysis_group_id=analysis_group_id,
    )
    if not records:
        raise _supplement_http_error(
            status.HTTP_404_NOT_FOUND,
            code="analysis_group_not_found",
            message="Multi-image analysis group was not found.",
        )
    if any(
        record.status == SupplementAnalysisStatus.FAILED.value
        or _analysis_run_is_stale(record, settings)
        for record in records
    ):
        return SupplementMultiImageAnalysisStatusResponse(
            status=SupplementAnalysisStatus.FAILED,
            error=SupplementAnalysisError(
                code="analysis_failed",
                message="Supplement label analysis could not be completed. Please try again.",
            ),
        )
    if any(record.status == SupplementAnalysisStatus.PROCESSING.value for record in records):
        return SupplementMultiImageAnalysisStatusResponse(
            status=SupplementAnalysisStatus.PROCESSING,
        )
    previews = [supplement_analysis_run_to_preview(record) for record in records]
    # Recover the batch merge_strategy the submit persisted on each row so the
    # aggregate response carries the right result_mode (and a merged_preview only
    # for single_product). Prefer distinct_products if any row is flagged distinct,
    # and default to single_product for legacy rows without the field.
    merge_strategy: Literal["single_product", "distinct_products"] = (
        "distinct_products"
        if any(
            isinstance(record.parsed_snapshot, dict)
            and record.parsed_snapshot.get("multi_image_merge_strategy") == "distinct_products"
            for record in records
        )
        else "single_product"
    )
    return SupplementMultiImageAnalysisStatusResponse(
        status=SupplementAnalysisStatus.REQUIRES_CONFIRMATION,
        preview=_build_multi_image_response(
            analysis_group_id=analysis_group_id,
            previews=previews,
            merge_strategy=merge_strategy,
        ),
    )


@router.post(
    "/analysis-sessions/{analysis_group_id}/finalize",
    response_model=SupplementMultiImageAnalysisPreview,
    status_code=status.HTTP_200_OK,
    responses={
        **SUPPLEMENT_AUTH_RESPONSES,
        404: {"description": "Multi-image analysis session was not found."},
        422: {"content": {"application/json": {"examples": UNPROCESSABLE_ENTITY_EXAMPLE}}},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.SUPPLEMENT_WRITE,),
        consents=(ConsentType.OCR_IMAGE_PROCESSING,),
        contract_status=P1_2_INTAKE_READY_STATUS,
    ),
)
async def finalize_supplement_analysis_session(
    http_request: Request,
    analysis_group_id: Annotated[
        str,
        Path(
            min_length=1,
            max_length=120,
            description="Backend-created multi-image analysis group id.",
        ),
    ],
    current_user: Annotated[AuthenticatedUser, Depends(require_supplement_write)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SupplementMultiImageAnalysisPreview:
    """Rebuild a safe merged preview for an existing multi-image analysis batch.

    Args:
        http_request: Current FastAPI request.
        analysis_group_id: Backend-created multi-image analysis group id.
        current_user: Authenticated owner.
        session: Request-scoped async database session.
        settings: Application settings.

    Returns:
        Batch preview assembled from persisted, current-user per-image previews.

    Raises:
        HTTPException: If consent is missing or the group is absent.
    """
    try:
        await require_user_consent(
            session,
            current_user,
            ConsentType.OCR_IMAGE_PROCESSING,
        )
    except ConsentRequiredError as exc:
        await record_sensitive_audit_event(
            session,
            current_user,
            action="supplement_image_analysis_session_finalize_blocked",
            resource_type="supplement_analysis_run",
            resource_id=None,
            outcome="blocked",
            request=http_request,
            settings=settings,
            event_metadata={"missing_consents": [ConsentType.OCR_IMAGE_PROCESSING.value]},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "consent_required",
                "message": str(exc),
                "required_consents": [ConsentType.OCR_IMAGE_PROCESSING.value],
            },
        ) from exc

    analysis_runs = await _load_multi_image_analysis_runs(
        session,
        owner_subject=build_owner_subject(current_user),
        analysis_group_id=analysis_group_id,
    )
    if not analysis_runs:
        await record_sensitive_audit_event(
            session,
            current_user,
            action="supplement_image_analysis_session_finalize_missing",
            resource_type="supplement_analysis_run",
            resource_id=None,
            outcome="blocked",
            request=http_request,
            settings=settings,
            event_metadata={"analysis_group_id_present": bool(analysis_group_id)},
        )
        raise _supplement_http_error(
            status.HTTP_404_NOT_FOUND,
            code="analysis_session_not_found",
            message="Supplement analysis session was not found.",
        )

    previews = [supplement_analysis_run_to_preview(record) for record in analysis_runs]
    response = _build_multi_image_response(
        analysis_group_id=analysis_group_id,
        previews=previews,
    )
    await record_sensitive_audit_event(
        session,
        current_user,
        action="supplement_image_analysis_session_finalized",
        resource_type="supplement_analysis_run",
        resource_id=None,
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={
            "image_count": response.image_count,
            "missing_required_sections": list(response.missing_required_sections),
            "raw_image_stored": False,
            "raw_ocr_text_stored": False,
        },
    )
    return response


@router.post(
    "/barcode/lookup",
    response_model=SupplementBarcodeLookupResponse,
    status_code=status.HTTP_200_OK,
    responses={
        **SUPPLEMENT_AUTH_RESPONSES,
        200: {"description": "Review-only official barcode lookup result."},
        422: {"content": {"application/json": {"examples": UNPROCESSABLE_ENTITY_EXAMPLE}}},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.SUPPLEMENT_WRITE,),
        contract_status=P1_2_INTAKE_READY_STATUS,
    ),
)
async def lookup_supplement_barcode(
    http_request: Request,
    request: Annotated[SupplementBarcodeLookupRequest, Body()],
    current_user: Annotated[AuthenticatedUser, Depends(require_supplement_write)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    barcode_service: Annotated[
        SupplementBarcodeLookupService,
        Depends(get_supplement_barcode_lookup_service),
    ],
) -> SupplementBarcodeLookupResponse:
    """Look up review-only official product candidates by barcode.

    Args:
        http_request: Current FastAPI request.
        request: Barcode lookup request.
        current_user: Authenticated owner.
        session: Request-scoped async database session.
        settings: Application settings.
        barcode_service: Barcode lookup service.

    Returns:
        Barcode lookup response requiring user confirmation.

    Raises:
        HTTPException: If the barcode value is syntactically invalid.
    """

    result = await barcode_service.lookup(
        request.barcode_text,
        barcode_format=request.barcode_format,
    )
    response = barcode_lookup_result_to_response(result)
    await _record_barcode_lookup_audit(
        session,
        current_user,
        http_request,
        settings,
        response,
    )
    if result.status == "invalid_request":
        raise _supplement_http_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            code=result.error_code or "invalid_barcode",
            message=result.error_message or "Barcode value is invalid.",
        )
    return response


async def _record_barcode_lookup_audit(
    session: AsyncSession,
    current_user: AuthenticatedUser,
    http_request: Request,
    settings: Settings,
    response: SupplementBarcodeLookupResponse,
) -> None:
    """Record sanitized barcode lookup audit metadata.

    Args:
        session: Request-scoped async database session.
        current_user: Authenticated actor.
        http_request: Current FastAPI request.
        settings: Application settings.
        response: Barcode lookup response. Raw barcode values are not logged.

    Returns:
        None.
    """

    outcome: AuditOutcome = "success"
    if response.status == "invalid_request":
        outcome = "blocked"
    elif response.status == "provider_error":
        outcome = "failed"
    await record_sensitive_audit_event(
        session,
        current_user,
        action="supplement_barcode_lookup",
        resource_type="supplement_barcode",
        resource_id=None,
        outcome=outcome,
        request=http_request,
        settings=settings,
        event_metadata={
            "lookup_status": response.status,
            "barcode_hash": response.barcode_hash,
            "barcode_format": response.barcode_format,
            "barcode_symbology": response.barcode_symbology,
            "candidate_count": response.candidate_count,
            "provider_observations": [
                observation.model_dump(mode="json")
                for observation in response.provider_observations
            ],
            "raw_barcode_stored": False,
            "raw_provider_payload_stored": False,
            "auto_confirmed": False,
        },
    )


@router.post(
    "/analyses/{analysis_id}/ocr-text",
    response_model=SupplementAnalysisPreview,
    status_code=status.HTTP_200_OK,
    responses={
        **SUPPLEMENT_AUTH_RESPONSES,
        200: {"description": "Structured OCR text preview requiring user confirmation."},
        403: {"content": {"application/json": {"examples": CONSENT_REQUIRED_EXAMPLE}}},
        404: {"description": "Supplement analysis preview was not found for the current user."},
        409: {"description": "Supplement analysis preview is expired or not parseable."},
        502: {"description": "Local structured parser failed or returned invalid content."},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.SUPPLEMENT_WRITE,),
        consents=(ConsentType.OCR_IMAGE_PROCESSING,),
        contract_status=P1_2_INTAKE_READY_STATUS,
    ),
)
async def parse_supplement_analysis_ocr_text_preview(
    analysis_id: UUID,
    http_request: Request,
    request: Annotated[SupplementOCRTextParseRequest, Body()],
    current_user: Annotated[AuthenticatedUser, Depends(require_supplement_write)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SupplementAnalysisPreview:
    """Attach OCR text to an existing preview and return structured parse candidates.

    Args:
        analysis_id: Existing supplement analysis preview identifier.
        http_request: Current FastAPI request.
        request: OCR text and provider metadata. Raw OCR text is never persisted.
        current_user: Authenticated owner.
        session: Request-scoped async database session.
        settings: Application settings.

    Returns:
        Updated supplement preview that still requires user confirmation.

    Raises:
        HTTPException: If consent is missing, the preview is unavailable, OCR text
            is invalid, or the local parser cannot produce schema-valid output.
    """
    try:
        await require_user_consent(session, current_user, ConsentType.OCR_IMAGE_PROCESSING)
    except ConsentRequiredError as exc:
        await record_sensitive_audit_event(
            session,
            current_user,
            action="supplement_ocr_text_parse_blocked",
            resource_type="supplement_analysis_run",
            resource_id=str(analysis_id),
            outcome="blocked",
            request=http_request,
            settings=settings,
            event_metadata={"missing_consent": ConsentType.OCR_IMAGE_PROCESSING.value},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "consent_required",
                "message": str(exc),
                "required_consents": [ConsentType.OCR_IMAGE_PROCESSING.value],
            },
        ) from exc

    try:
        result = await parse_supplement_analysis_ocr_text(
            session=session,
            user=current_user,
            analysis_id=analysis_id,
            ocr_text=request.ocr_text,
            ocr_provider=request.ocr_provider,
            ocr_confidence=request.ocr_confidence,
            settings=settings,
        )
    except SupplementParserInputError as exc:
        await _record_ocr_text_parse_audit(
            session,
            current_user,
            http_request,
            settings,
            analysis_id,
            outcome="blocked",
            reason="invalid_ocr_text",
            request=request,
        )
        raise _supplement_http_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="invalid_ocr_text",
            message=str(exc),
        ) from exc
    except SupplementAnalysisNotFoundError as exc:
        await _record_ocr_text_parse_audit(
            session,
            current_user,
            http_request,
            settings,
            analysis_id,
            outcome="not_found",
            reason="analysis_not_found",
            request=request,
        )
        raise _supplement_http_error(
            status.HTTP_404_NOT_FOUND,
            code="supplement_analysis_not_found",
            message=str(exc),
        ) from exc
    except (
        SupplementAnalysisExpiredError,
        SupplementAnalysisStateError,
        SupplementParserConflictError,
    ) as exc:
        await _record_ocr_text_parse_audit(
            session,
            current_user,
            http_request,
            settings,
            analysis_id,
            outcome="blocked",
            reason="analysis_not_parseable",
            request=request,
        )
        raise _supplement_http_error(
            status.HTTP_409_CONFLICT,
            code="supplement_analysis_not_parseable",
            message=str(exc),
        ) from exc
    except (OllamaClientError, OllamaConfigurationError) as exc:
        await _record_ocr_text_parse_audit(
            session,
            current_user,
            http_request,
            settings,
            analysis_id,
            outcome="failed",
            reason="parser_unavailable",
            request=request,
        )
        raise _supplement_http_error(
            status.HTTP_502_BAD_GATEWAY,
            code="parser_unavailable",
            message="Local supplement parser is unavailable.",
        ) from exc
    except OllamaStructuredOutputError as exc:
        await _record_ocr_text_parse_audit(
            session,
            current_user,
            http_request,
            settings,
            analysis_id,
            outcome="failed",
            reason="parser_schema_invalid",
            request=request,
        )
        raise _supplement_http_error(
            status.HTTP_502_BAD_GATEWAY,
            code="parser_schema_invalid",
            message="Local supplement parser returned invalid structured output.",
        ) from exc

    await record_sensitive_audit_event(
        session,
        current_user,
        action="supplement_ocr_text_parsed",
        resource_type="supplement_analysis_run",
        resource_id=str(result.record.id),
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={
            "ocr_provider": result.record.ocr_provider,
            "ocr_confidence_present": result.record.ocr_confidence is not None,
            "parser_provider": settings.llm_provider,
            "parser_model": settings.ollama_model,
            "parser_schema": "SupplementStructuredParseResultV2",
            "schema_valid": True,
            "ingredient_count": len(result.parse_result.ingredient_candidates),
            "low_confidence_field_count": len(
                result.record.parsed_snapshot.get("low_confidence_fields", [])
            ),
            "raw_ocr_text_stored": False,
            "raw_llm_response_stored": False,
        },
    )
    return supplement_analysis_run_to_preview(result.record)


@router.post(
    "/analyses/{analysis_id}/explain",
    response_model=SupplementRecommendationExplainResponse,
    status_code=status.HTTP_200_OK,
    responses={
        **SUPPLEMENT_AUTH_RESPONSES,
        200: {"description": "Safe local explanation for a supplement analysis preview."},
        403: {"content": {"application/json": {"examples": CONSENT_REQUIRED_EXAMPLE}}},
        404: {"description": "Supplement analysis preview was not found for the current user."},
        409: {"description": "Supplement analysis preview is expired."},
        422: {"content": {"application/json": {"examples": UNPROCESSABLE_ENTITY_EXAMPLE}}},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.SUPPLEMENT_WRITE,),
        consents=(ConsentType.OCR_IMAGE_PROCESSING,),
        contract_status=P1_2_INTAKE_READY_STATUS,
    ),
)
async def explain_supplement_analysis_preview_route(
    analysis_id: UUID,
    http_request: Request,
    request: Annotated[SupplementAnalysisExplainRequest, Body()],
    current_user: Annotated[AuthenticatedUser, Depends(require_supplement_write)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SupplementRecommendationExplainResponse:
    """Explain a stored analysis preview before user-confirmed registration.

    Args:
        analysis_id: Existing supplement analysis preview identifier.
        http_request: Current FastAPI request.
        request: Explanation options.
        current_user: Authenticated owner.
        session: Request-scoped async database session.
        settings: Application settings.

    Returns:
        Safe explanation based only on sanitized parsed preview fields.

    Raises:
        HTTPException: If consent is missing, the preview is unavailable, expired,
            or fallback wording fails safety validation.
    """
    try:
        await require_user_consent(session, current_user, ConsentType.OCR_IMAGE_PROCESSING)
    except ConsentRequiredError as exc:
        await _record_analysis_preview_explain_audit(
            session,
            current_user,
            http_request,
            settings,
            analysis_id,
            outcome="blocked",
            reason="consent_required",
            response=None,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "consent_required",
                "message": str(exc),
                "required_consents": [ConsentType.OCR_IMAGE_PROCESSING.value],
            },
        ) from exc

    record = await _load_supplement_analysis_run_for_owner(
        session,
        owner_subject=build_owner_subject(current_user),
        analysis_id=analysis_id,
    )
    if record is None:
        await _record_analysis_preview_explain_audit(
            session,
            current_user,
            http_request,
            settings,
            analysis_id,
            outcome="not_found",
            reason="analysis_not_found",
            response=None,
        )
        raise _supplement_http_error(
            status.HTTP_404_NOT_FOUND,
            code="supplement_analysis_not_found",
            message="Supplement analysis preview was not found.",
        )
    if _analysis_preview_is_expired(record):
        await _record_analysis_preview_explain_audit(
            session,
            current_user,
            http_request,
            settings,
            analysis_id,
            outcome="blocked",
            reason="analysis_expired",
            response=None,
        )
        raise _supplement_http_error(
            status.HTTP_409_CONFLICT,
            code="supplement_analysis_expired",
            message="Supplement analysis preview has expired.",
        )

    profile_snapshot = None
    medical_context_summary = None
    sensitive_context_requested = request.include_profile_context or request.include_medical_context
    if sensitive_context_requested:
        try:
            await require_user_consent(
                session,
                current_user,
                ConsentType.SENSITIVE_HEALTH_ANALYSIS,
            )
        except ConsentRequiredError as exc:
            await _record_analysis_preview_explain_audit(
                session,
                current_user,
                http_request,
                settings,
                analysis_id,
                outcome="blocked",
                reason="sensitive_health_consent_required",
                response=None,
                profile_context_requested=request.include_profile_context,
                profile_context_included=False,
                medical_context_requested=request.include_medical_context,
                medical_context_included=False,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "consent_required",
                    "message": str(exc),
                    "required_consents": [ConsentType.SENSITIVE_HEALTH_ANALYSIS.value],
                },
            ) from exc
    if request.include_profile_context:
        profile_snapshot = await get_latest_body_profile_snapshot(session, current_user)
    if request.include_medical_context:
        medical_context_summary = await get_current_medical_context_summary(
            session,
            current_user,
            settings,
        )

    try:
        response = await explain_supplement_analysis_preview(
            record,
            request,
            settings,
            profile_snapshot=profile_snapshot,
            medical_context_summary=medical_context_summary,
        )
    except SupplementExplanationError as exc:
        await _record_analysis_preview_explain_audit(
            session,
            current_user,
            http_request,
            settings,
            analysis_id,
            outcome="blocked",
            reason="unsafe_supplement_explanation",
            response=None,
            profile_context_requested=request.include_profile_context,
            profile_context_included=profile_snapshot is not None,
            medical_context_requested=request.include_medical_context,
            medical_context_included=medical_context_summary is not None
            and medical_context_summary.available,
        )
        raise _supplement_http_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="unsafe_supplement_explanation",
            message=str(exc),
        ) from exc

    await _record_analysis_preview_explain_audit(
        session,
        current_user,
        http_request,
        settings,
        analysis_id,
        outcome="success",
        reason="explained",
        response=response,
        profile_context_requested=request.include_profile_context,
        profile_context_included=profile_snapshot is not None,
        medical_context_requested=request.include_medical_context,
        medical_context_included=medical_context_summary is not None
        and medical_context_summary.available,
    )
    return response


def _analysis_preview_is_expired(record: SupplementAnalysisRun) -> bool:
    """Return whether a stored analysis preview is no longer usable."""
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at <= datetime.now(UTC)


async def _record_analysis_preview_explain_audit(
    session: AsyncSession,
    current_user: AuthenticatedUser,
    http_request: Request,
    settings: Settings,
    analysis_id: UUID,
    *,
    outcome: AuditOutcome,
    reason: str,
    response: SupplementRecommendationExplainResponse | None,
    profile_context_requested: bool = False,
    profile_context_included: bool = False,
    medical_context_requested: bool = False,
    medical_context_included: bool = False,
) -> None:
    """Record sanitized audit metadata for analysis-preview explanations.

    Args:
        session: Request-scoped async database session.
        current_user: Authenticated actor.
        http_request: Current FastAPI request.
        settings: Runtime settings.
        analysis_id: Supplement analysis preview identifier.
        outcome: Sanitized audit outcome.
        reason: Stable reason code.
        response: Safe explanation response, if generated.
        profile_context_requested: Whether the request asked to use profile context.
        profile_context_included: Whether a profile snapshot was loaded.
        medical_context_requested: Whether the request asked to use medical context.
        medical_context_included: Whether medical summary rows were available.

    Returns:
        None.
    """
    await record_sensitive_audit_event(
        session,
        current_user,
        action="supplement_analysis_preview_explained",
        resource_type="supplement_analysis_run",
        resource_id=str(analysis_id),
        outcome=outcome,
        request=http_request,
        settings=settings,
        event_metadata={
            "reason": reason,
            "llm_used": response.llm_used if response is not None else False,
            "warning_count": len(response.warnings) if response is not None else 0,
            "blocked_term_count": (
                len(response.blocked_terms_detected) if response is not None else 0
            ),
            "raw_ocr_text_stored": False,
            "raw_provider_payload_stored": False,
            "raw_llm_response_stored": False,
            "raw_image_stored": False,
            "object_uri_stored": False,
            "profile_context_requested": profile_context_requested,
            "profile_context_included": profile_context_included,
            "raw_profile_payload_stored": False,
            "medical_context_requested": medical_context_requested,
            "medical_context_included": medical_context_included,
            "raw_medical_payload_stored": False,
        },
    )


async def _record_ocr_text_parse_audit(
    session: AsyncSession,
    current_user: AuthenticatedUser,
    http_request: Request,
    settings: Settings,
    analysis_id: UUID,
    *,
    outcome: AuditOutcome,
    reason: str,
    request: SupplementOCRTextParseRequest,
) -> None:
    """Record a sanitized OCR text parsing audit event.

    Args:
        session: Request-scoped async database session.
        current_user: Authenticated actor.
        http_request: Current FastAPI request.
        settings: Application settings.
        analysis_id: Supplement analysis preview identifier.
        outcome: Sanitized audit outcome.
        reason: Stable failure reason.
        request: OCR text parse request. Raw OCR text is intentionally not logged.

    Returns:
        None.
    """
    await record_sensitive_audit_event(
        session,
        current_user,
        action="supplement_ocr_text_parse_failed",
        resource_type="supplement_analysis_run",
        resource_id=str(analysis_id),
        outcome=outcome,
        request=http_request,
        settings=settings,
        event_metadata={
            "reason": reason,
            "ocr_provider": request.ocr_provider,
            "ocr_confidence_present": request.ocr_confidence is not None,
            "parser_provider": settings.llm_provider,
            "parser_model": settings.ollama_model,
            "parser_schema": "SupplementStructuredParseResultV2",
            "schema_valid": False if reason == "parser_schema_invalid" else None,
            "raw_ocr_text_stored": False,
            "raw_llm_response_stored": False,
        },
    )


@router.post(
    "",
    response_model=UserSupplementResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        **COMMON_SUPPLEMENT_RESPONSES,
        201: {"content": {"application/json": {"examples": USER_SUPPLEMENT_RESPONSE_EXAMPLES}}},
        403: {"content": {"application/json": {"examples": CONSENT_REQUIRED_EXAMPLE}}},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.SUPPLEMENT_WRITE,),
        consents=(ConsentType.SENSITIVE_HEALTH_ANALYSIS,),
        contract_status=P1_4_SUPPLEMENT_REGISTRATION_READY_STATUS,
    ),
)
async def create_user_supplement(
    http_request: Request,
    request: Annotated[
        UserSupplementCreate,
        Body(openapi_examples=SUPPLEMENT_CREATE_REQUEST_EXAMPLES),
    ],
    background_tasks: BackgroundTasks,
    current_user: Annotated[AuthenticatedUser, Depends(require_supplement_write)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserSupplementResponse:
    """Store a user-confirmed supplement record.

    Args:
        http_request: Current FastAPI request.
        request: User-confirmed supplement data.
        session: Request-scoped async database session.
        current_user: Authenticated owner.
        settings: Application settings.

    Returns:
        Persisted supplement response.

    Raises:
        HTTPException: If consent is missing, preview state is invalid, or payload is invalid.
    """
    # Route-owned RLS transaction (see rls_request_transaction): owner reads/writes
    # commit before the response is sent, so the post-commit learning-embedding
    # BackgroundTask runs against durable rows. The embedding enqueue itself
    # commits and reads FORCE-RLS learning tables, so it is deferred to a fresh
    # privileged session out-of-band instead of running inside this transaction.
    async with rls_request_transaction(session, current_user, settings):
        await _require_sensitive_health_consent(session, current_user, http_request, settings)
        try:
            result = await create_user_supplement_from_confirmation(
                session,
                current_user,
                request,
                settings,
            )
        except SupplementRegistrationValidationError as exc:
            raise _supplement_http_error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="invalid_supplement_confirmation",
                message=str(exc),
            ) from exc
        except SupplementPreviewNotFoundError as exc:
            raise _supplement_http_error(
                status.HTTP_404_NOT_FOUND,
                code="supplement_analysis_not_found",
                message=str(exc),
            ) from exc
        except (SupplementPreviewExpiredError, SupplementPreviewStateError) as exc:
            raise _supplement_http_error(
                status.HTTP_409_CONFLICT,
                code="supplement_analysis_not_confirmable",
                message=str(exc),
            ) from exc

        learning_consents = await _collect_learning_consents_if_enabled(
            session,
            current_user,
            settings,
        )
        embedding_input = SupplementLearningEmbeddingInput(
            analysis_id=result.supplement.source_analysis_run_id,
            metadata_snapshot=build_confirmed_supplement_learning_metadata(
                result.supplement,
                result.ingredients,
            ),
            learning_consents=learning_consents,
        )
        learning_scheduled = embedding_input.analysis_id is not None and bool(learning_consents)

        await record_sensitive_audit_event(
            session,
            current_user,
            action="supplement_registered",
            resource_type="user_supplement",
            resource_id=str(result.supplement.id),
            outcome="success",
            request=http_request,
            settings=settings,
            event_metadata={
                "analysis_id_present": request.analysis_id is not None,
                "ingredient_count": len(result.ingredients),
                "matched_product_id_present": result.supplement.matched_product_id is not None,
                "learning_embedding_job_scheduled": learning_scheduled,
            },
        )
        if learning_scheduled:
            background_tasks.add_task(
                store_supplement_learning_embedding_job,
                user=current_user,
                embedding_input=embedding_input,
                settings=settings,
            )
        return user_supplement_to_response(
            result.supplement,
            result.ingredients,
            categories=result.categories,
        )


async def _collect_learning_consents_if_enabled(
    session: AsyncSession,
    current_user: AuthenticatedUser,
    settings: Settings,
) -> tuple[ConsentType, ...]:
    """Collect learning consents only when learning flags can use them.

    Args:
        session: Request-scoped async database session.
        current_user: Authenticated owner.
        settings: Runtime settings.

    Returns:
        Active learning consents, or an empty tuple when learning is disabled.
    """
    if not settings.enable_image_learning_pipeline and not settings.enable_pgvector_storage:
        return ()
    return await collect_active_learning_consents(session, current_user)


@router.get(
    "/recommendations/latest",
    response_model=SupplementImpactPreviewResponse,
    responses={
        **SUPPLEMENT_AUTH_RESPONSES,
        200: {
            "content": {
                "application/json": {"examples": SUPPLEMENT_IMPACT_PREVIEW_RESPONSE_EXAMPLES}
            }
        },
        403: {"content": {"application/json": {"examples": CONSENT_REQUIRED_EXAMPLE}}},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.SUPPLEMENT_READ, ApiScope.ANALYSIS_READ),
        consents=(ConsentType.SENSITIVE_HEALTH_ANALYSIS,),
        contract_status=P1_7_SUPPLEMENT_RECOMMENDATION_READY_STATUS,
    ),
)
async def get_latest_supplement_recommendations(
    http_request: Request,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_supplement_recommendation_read),
    ],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SupplementImpactPreviewResponse:
    """Return the latest deterministic supplement impact preview.

    Args:
        http_request: Current FastAPI request.
        current_user: Authenticated owner.
        session: Request-scoped async database session.
        settings: Application settings.

    Returns:
        Deterministic supplement impact preview using all active supplements.

    Raises:
        HTTPException: If consent is missing or generated output is unsafe.
    """
    await _require_sensitive_health_consent(session, current_user, http_request, settings)
    try:
        response = await build_supplement_impact_preview(
            session,
            current_user,
            SupplementImpactPreviewRequest(),
        )
    except ValueError as exc:
        raise _supplement_http_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="invalid_supplement_recommendation",
            message=str(exc),
        ) from exc
    await record_sensitive_audit_event(
        session,
        current_user,
        action="supplement_recommendations_latest",
        resource_type="supplement_recommendation",
        resource_id=None,
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={
            "data_status": response.data_status.value,
            "contribution_count": len(response.current_supplement_contributions),
            "deficiency_candidate_count": len(response.deficiency_support_candidates),
            "risk_count": len(response.excess_or_duplicate_risks),
            "warning_count": len(response.warnings),
        },
    )
    return response


@router.post(
    "/recommendations/explain",
    response_model=SupplementRecommendationExplainResponse,
    responses={
        **SUPPLEMENT_AUTH_RESPONSES,
        200: {
            "content": {
                "application/json": {
                    "examples": SUPPLEMENT_RECOMMENDATION_EXPLAIN_RESPONSE_EXAMPLES
                }
            }
        },
        403: {"content": {"application/json": {"examples": CONSENT_REQUIRED_EXAMPLE}}},
        422: {"content": {"application/json": {"examples": UNPROCESSABLE_ENTITY_EXAMPLE}}},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.SUPPLEMENT_READ, ApiScope.ANALYSIS_READ),
        consents=(ConsentType.SENSITIVE_HEALTH_ANALYSIS,),
        contract_status=P1_7_SUPPLEMENT_RECOMMENDATION_READY_STATUS,
    ),
)
async def explain_supplement_recommendations(
    http_request: Request,
    request: Annotated[
        SupplementRecommendationExplainRequest,
        Body(openapi_examples=SUPPLEMENT_RECOMMENDATION_EXPLAIN_REQUEST_EXAMPLES),
    ],
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_supplement_recommendation_read),
    ],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SupplementRecommendationExplainResponse:
    """Explain deterministic supplement impact output with safety guardrails.

    Args:
        http_request: Current FastAPI request.
        request: Explanation request.
        current_user: Authenticated owner.
        session: Request-scoped async database session.
        settings: Application settings.

    Returns:
        Safe explanation response.

    Raises:
        HTTPException: If consent is missing or fallback wording fails safety validation.
    """
    await _require_sensitive_health_consent(session, current_user, http_request, settings)
    try:
        response = await explain_supplement_recommendation(request, settings)
    except SupplementExplanationError as exc:
        raise _supplement_http_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="unsafe_supplement_explanation",
            message=str(exc),
        ) from exc
    await record_sensitive_audit_event(
        session,
        current_user,
        action="supplement_recommendations_explained",
        resource_type="supplement_recommendation",
        resource_id=None,
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={
            "llm_used": response.llm_used,
            "warning_count": len(response.warnings),
            "blocked_term_count": len(response.blocked_terms_detected),
            "raw_ocr_text_stored": False,
            "raw_llm_response_stored": False,
        },
    )
    return response


@router.get(
    "",
    response_model=UserSupplementListResponse,
    responses={
        **COMMON_SUPPLEMENT_RESPONSES,
        200: {
            "content": {"application/json": {"examples": USER_SUPPLEMENT_LIST_RESPONSE_EXAMPLES}}
        },
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.SUPPLEMENT_READ,),
        contract_status=P1_4_SUPPLEMENT_REGISTRATION_READY_STATUS,
    ),
)
async def list_user_supplements(
    http_request: Request,
    current_user: Annotated[AuthenticatedUser, Depends(require_supplement_read)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    category_key: Annotated[str | None, Query(max_length=120)] = None,
    category_id: Annotated[UUID | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> UserSupplementListResponse:
    """List supplement records owned by the current user.

    Args:
        http_request: Current FastAPI request.
        session: Request-scoped async database session.
        current_user: Authenticated owner.
        settings: Application settings.
        limit: Maximum result count.
        offset: Result offset.
        category_key: Optional active supplement category key filter.
        category_id: Optional active supplement category id filter.
        q: Optional display-name or manufacturer substring filter.

    Returns:
        Paginated supplement list.

    Raises:
        HTTPException: If owner identity cannot be persisted safely.
    """
    try:
        response = await list_user_supplement_records(
            session,
            current_user,
            limit,
            offset,
            category_key=category_key,
            category_id=category_id,
            q=q,
        )
    except TaxonomyFilterNotFoundError as exc:
        raise _supplement_http_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="taxonomy_filter_not_found",
            message=str(exc),
        ) from exc
    except ValueError as exc:
        raise _supplement_http_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="invalid_supplement_query",
            message=str(exc),
        ) from exc
    await record_sensitive_audit_event(
        session,
        current_user,
        action="supplement_listed",
        resource_type="user_supplement",
        resource_id=None,
        outcome="success",
        request=http_request,
        settings=settings,
        event_metadata={
            "count": len(response.results),
            "limit": limit,
            "offset": offset,
            "category_key_present": category_key is not None,
            "category_id_present": category_id is not None,
            "q_present": bool(q),
        },
    )
    return response


@router.get(
    "/categories",
    response_model=SupplementCategoryListResponse,
    responses={**COMMON_SUPPLEMENT_RESPONSES},
    openapi_extra=route_contract(
        scopes=(ApiScope.SUPPLEMENT_READ,),
        contract_status=P1_4_SUPPLEMENT_REGISTRATION_READY_STATUS,
    ),
)
async def list_supplement_category_catalog(
    current_user: Annotated[AuthenticatedUser, Depends(require_supplement_read)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    q: Annotated[str | None, Query(max_length=120)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SupplementCategoryListResponse:
    """List active supplement categories for current-user filter UIs.

    Args:
        current_user: Authenticated caller; only used to enforce read scope.
        session: Request-scoped async database session.
        q: Optional category key or display-name substring.
        limit: Maximum result count.
        offset: Result offset.

    Returns:
        Paginated active supplement category catalog response.
    """
    del current_user
    return await list_supplement_categories(session, q=q, limit=limit, offset=offset)


@router.get(
    "/{supplement_id}",
    response_model=UserSupplementResponse,
    responses={
        **COMMON_SUPPLEMENT_RESPONSES,
        200: {"content": {"application/json": {"examples": USER_SUPPLEMENT_RESPONSE_EXAMPLES}}},
    },
    openapi_extra=route_contract(
        scopes=(ApiScope.SUPPLEMENT_READ,),
        contract_status=P1_4_SUPPLEMENT_REGISTRATION_READY_STATUS,
    ),
)
async def get_user_supplement(
    supplement_id: UUID,
    http_request: Request,
    current_user: Annotated[AuthenticatedUser, Depends(require_supplement_read)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserSupplementResponse:
    """Return one supplement record owned by the current user.

    Args:
        supplement_id: Persisted supplement identifier.
        http_request: Current FastAPI request.
        session: Request-scoped async database session.
        current_user: Authenticated owner.
        settings: Application settings.

    Returns:
        Supplement detail response.

    Raises:
        HTTPException: If the supplement does not exist for this owner.
    """
    result = await get_user_supplement_record(session, current_user, supplement_id)
    if result is None:
        await record_sensitive_audit_event(
            session,
            current_user,
            action="supplement_read",
            resource_type="user_supplement",
            resource_id=str(supplement_id),
            outcome="not_found",
            request=http_request,
            settings=settings,
        )
        raise _supplement_http_error(
            status.HTTP_404_NOT_FOUND,
            code="supplement_not_found",
            message="Supplement record was not found.",
        )
    await record_sensitive_audit_event(
        session,
        current_user,
        action="supplement_read",
        resource_type="user_supplement",
        resource_id=str(supplement_id),
        outcome="success",
        request=http_request,
        settings=settings,
    )
    return user_supplement_to_response(
        result.supplement,
        result.ingredients,
        categories=result.categories,
    )


@router.delete(
    "/{supplement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=COMMON_SUPPLEMENT_RESPONSES,
    openapi_extra=route_contract(
        scopes=(ApiScope.SUPPLEMENT_DELETE,),
        contract_status=P1_4_SUPPLEMENT_REGISTRATION_READY_STATUS,
    ),
)
async def delete_user_supplement(
    supplement_id: UUID,
    http_request: Request,
    current_user: Annotated[AuthenticatedUser, Depends(require_supplement_delete)],
    session: Annotated[AsyncSession, Depends(get_rls_context_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """Delete one supplement record owned by the current user.

    Args:
        supplement_id: Persisted supplement identifier.
        http_request: Current FastAPI request.
        session: Request-scoped async database session.
        current_user: Authenticated owner.
        settings: Application settings.

    Returns:
        Empty response after deletion.

    Raises:
        HTTPException: If the supplement does not exist for this owner.
    """
    deleted = await soft_delete_user_supplement(session, current_user, supplement_id)
    if not deleted:
        await record_sensitive_audit_event(
            session,
            current_user,
            action="supplement_delete",
            resource_type="user_supplement",
            resource_id=str(supplement_id),
            outcome="not_found",
            request=http_request,
            settings=settings,
        )
        raise _supplement_http_error(
            status.HTTP_404_NOT_FOUND,
            code="supplement_not_found",
            message="Supplement record was not found.",
        )
    await record_sensitive_audit_event(
        session,
        current_user,
        action="supplement_delete",
        resource_type="user_supplement",
        resource_id=str(supplement_id),
        outcome="success",
        request=http_request,
        settings=settings,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/analyze/comprehensive",
    response_model=SupplementComprehensiveAnalysis,
    status_code=status.HTTP_200_OK,
    responses=SUPPLEMENT_AUTH_RESPONSES,
)
async def analyze_supplement_comprehensive(
    request_body: ComprehensiveAnalysisRequest,
    _current_user: Annotated[AuthenticatedUser, Depends(require_supplement_write)],
) -> SupplementComprehensiveAnalysis:
    """5-card UI 의 5종 카드 데이터를 모두 채우는 종합 분석 결과를 반환한다.

    OCR `analyze` endpoint 가 반환한 ingredient candidate 와 사용자 프로필을
    받아 KDRIs 권장량/상한과 비교하고 만성질환 매트릭스와 교차하여 부족/과다/주의/점수/목적별
    카드 데이터를 산출한다. 본 endpoint 는 별도의 OCR 또는 LLM 호출 없이 빠르게(200ms 이내)
    응답한다.

    Args:
        request_body: 분석 요청 본문 (ingredients + user_profile + persona).
        _current_user: 인증된 사용자 (dev 모드에서는 mock).

    Returns:
        [SupplementComprehensiveAnalysis] — 5-card 모두 채울 수 있는 데이터.
    """
    return compute_comprehensive(request_body)
