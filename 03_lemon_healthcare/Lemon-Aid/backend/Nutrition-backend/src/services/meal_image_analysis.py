"""Food image intake and preview persistence service."""

from __future__ import annotations

import functools
import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from http import HTTPStatus
from io import BytesIO
from typing import Any, Protocol
from uuid import UUID, uuid4

import anyio
from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings
from src.db.tx import persist_scope
from src.models.db.meal import (
    FoodCatalogItem,
    FoodCourse,
    FoodCuisine,
    FoodImageAnalysisRun,
    MealFoodItem,
    MealRecord,
)
from src.models.schemas.meal import (
    FoodImagePipelineMetadata,
    MealAnalysisStatus,
    MealConfirmationRequest,
    MealFoodCandidate,
    MealFoodItemInput,
    MealFoodItemResponse,
    MealImageAnalysisPreview,
    MealRecordListResponse,
    MealRecordResponse,
    MealRecordUpdateRequest,
    MealType,
)
from src.models.schemas.taxonomy import FoodCatalogItemReference
from src.security.auth import AuthenticatedUser
from src.security.subjects import build_owner_subject
from src.services.nutrition_scaling import compute_serving_nutrition
from src.services.supplement_intake import derive_idempotency_key, detect_image_mime
from src.services.taxonomy_catalog import (
    food_nutrition_per_100g,
    load_food_catalog_item_references,
    load_food_nutrition_by_class_ens,
    validate_food_catalog_filters,
)
from src.utils.image_safety import (
    ImageSafetyError,
    safe_load_with_bomb_guard,
    strip_image_metadata,
)
from src.vision.base import VisionError
from src.vision.food_dino_classifier import (
    FoodClassification,
    food_classifier_model_label,
    get_shared_food_dino_classifier,
)
from src.vision.food_yolo import FoodDetection, FoodYoloDetector, food_model_label

FOOD_IMAGE_ANALYSIS_ALGORITHM_VERSION = "food-image-preview-v1.0.0"
FOOD_IMAGE_ANALYSIS_WARNING_CODES = (
    "food_analysis_unavailable",
    "manual_entry_required",
)
FOOD_IMAGE_DETECTION_REVIEW_WARNING_CODES = ("food_detection_review_required",)
FOOD_IMAGE_DETECTOR_EMPTY_WARNING_CODES = (
    "food_detector_empty",
    "manual_entry_required",
)
FOOD_IMAGE_DETECTOR_UNAVAILABLE_WARNING_CODES = (
    "food_detector_unavailable",
    "manual_entry_required",
)
FOOD_IMAGE_CLASSIFICATION_REVIEW_WARNING_CODES = ("food_classification_review_required",)
FOOD_IMAGE_CLASSIFIER_EMPTY_WARNING_CODES = (
    "food_classifier_empty",
    "manual_entry_required",
)
FOOD_IMAGE_CLASSIFIER_UNAVAILABLE_WARNING_CODES = (
    "food_classifier_unavailable",
    "manual_entry_required",
)
ALLOWED_IMAGE_MIME_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
READ_CHUNK_SIZE_BYTES = 64 * 1024


@dataclass(frozen=True)
class ValidatedMealImage:
    """Validated food image metadata.

    Attributes:
        sha256: SHA-256 hex digest of normalized image bytes.
        mime_type: Detected and accepted image MIME type.
        size_bytes: Normalized image size in bytes.
        width: Decoded image width in pixels.
        height: Decoded image height in pixels.
        normalized_bytes: Sanitized in-memory bytes used only for current-request
            detector inference. Not stored in the database or API response.
    """

    sha256: str
    mime_type: str
    size_bytes: int
    width: int
    height: int
    normalized_bytes: bytes = field(repr=False, compare=False)


@dataclass(frozen=True)
class MealImageAnalysisStoreResult:
    """Stored food image preview result.

    Attributes:
        meal_record: Persisted or reused meal preview row.
        analysis_run: Persisted or reused food image analysis run row.
        image_metadata: Validated image metadata.
        reused_existing: Whether idempotency returned an existing analysis run.
    """

    meal_record: MealRecord
    analysis_run: FoodImageAnalysisRun
    image_metadata: ValidatedMealImage
    reused_existing: bool


@dataclass(frozen=True)
class MealConfirmationStoreResult:
    """Stored user-confirmed meal result.

    Attributes:
        meal_record: Confirmed meal row.
        food_items: Persisted user-confirmed food item rows.
        analysis_run: Linked food image analysis run when provided.
    """

    meal_record: MealRecord
    food_items: list[MealFoodItem]
    analysis_run: FoodImageAnalysisRun | None
    catalog_item_refs: dict[UUID, FoodCatalogItemReference] = field(default_factory=dict)


@dataclass(frozen=True)
class FoodDetectionResult:
    """Sanitized food detector outcome for one request.

    Attributes:
        detections: Review-only detector candidates.
        detector_model: Sanitized model label when configured.
        detector_used: Whether detector inference ran.
        warning_codes: Stable warning codes for the preview.
    """

    detections: tuple[FoodDetection, ...]
    detector_model: str | None
    detector_used: bool
    warning_codes: tuple[str, ...]


@dataclass(frozen=True)
class FoodClassificationResult:
    """Sanitized food classifier outcome for one request.

    Attributes:
        classification: Review-only classifier candidate when available.
        classifier_model: Sanitized classifier model label when configured.
        classifier_used: Whether classifier inference ran.
        warning_codes: Stable warning codes for the preview.
    """

    classification: FoodClassification | None
    classifier_model: str | None
    classifier_used: bool
    warning_codes: tuple[str, ...]


@dataclass(frozen=True)
class FoodImageInferenceResult:
    """Combined food detector and classifier outcome for preview persistence.

    Attributes:
        detections: Review-only YOLO detector candidates.
        classification: Review-only DINO classifier candidate.
        detector_model: Sanitized detector model label when configured.
        classifier_model: Sanitized classifier model label when configured.
        detector_used: Whether detector inference ran.
        classifier_used: Whether classifier inference ran.
        warning_codes: Stable warning codes for the preview.
    """

    detections: tuple[FoodDetection, ...]
    classification: FoodClassification | None
    detector_model: str | None
    classifier_model: str | None
    detector_used: bool
    classifier_used: bool
    warning_codes: tuple[str, ...]


class FoodDetector(Protocol):
    """Protocol for request-local food image detectors."""

    def detect_foods(self, image_bytes: bytes) -> list[FoodDetection]:
        """Detect food candidates.

        Args:
            image_bytes: Request-local normalized image bytes.

        Returns:
            Review-only food detections.
        """
        ...


class FoodImageClassifier(Protocol):
    """Protocol for request-local food image classifiers."""

    def classify_food(self, image_bytes: bytes) -> FoodClassification | None:
        """Classify one food image candidate.

        Args:
            image_bytes: Request-local normalized image bytes.

        Returns:
            Review-only food classification or None if no food is detected.
        """
        ...


class MealImageValidationError(ValueError):
    """Raised when an uploaded food image fails validation."""

    def __init__(self, *, code: str, message: str, status_code: int) -> None:
        """Initialize a safe food image validation error.

        Args:
            code: Stable API error code.
            message: Safe user-facing message.
            status_code: HTTP status code for the route.
        """
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class MealImageAnalysisConflictError(ValueError):
    """Raised when an idempotency key is reused for different image bytes."""


class MealConfirmationError(ValueError):
    """Base error for user meal confirmation failures."""


class MealConfirmationValidationError(MealConfirmationError):
    """Raised when a user-confirmed meal payload is inconsistent."""


class MealPreviewNotFoundError(MealConfirmationError):
    """Raised when a meal preview row is absent or inaccessible."""


class MealPreviewStateError(MealConfirmationError):
    """Raised when a meal preview cannot be confirmed in its current state."""


async def read_and_validate_meal_image(image: UploadFile, settings: Settings) -> ValidatedMealImage:
    """Read, bound, hash, and validate a food image upload.

    Args:
        image: Uploaded food image.
        settings: Runtime settings containing shared image upload limits.

    Returns:
        Validated food image metadata.

    Raises:
        MealImageValidationError: If the upload is empty, too large, unsupported,
            spoofed, or not a valid image.
    """
    data = await _read_limited_upload(image, settings.supplement_image_max_bytes)
    content_type = image.content_type
    detected_mime = detect_image_mime(data[:16])

    if not data:
        raise MealImageValidationError(
            code="invalid_image",
            message="Uploaded food image is empty.",
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        )
    if content_type not in ALLOWED_IMAGE_MIME_TYPES or detected_mime is None:
        raise MealImageValidationError(
            code="unsupported_media_type",
            message="Only JPEG, PNG, and WebP food images are accepted.",
            status_code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
        )
    if content_type != detected_mime:
        raise MealImageValidationError(
            code="unsupported_media_type",
            message="Uploaded food image content does not match its declared media type.",
            status_code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
        )

    width, height = _validate_decodable_image(data, settings.supplement_image_max_pixels)

    try:
        sanitized = strip_image_metadata(data, detected_mime)
    except ImageSafetyError as exc:
        raise MealImageValidationError(
            code="invalid_image",
            message="Uploaded food image cannot be normalized.",
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        ) from exc

    return ValidatedMealImage(
        sha256=hashlib.sha256(sanitized).hexdigest(),
        mime_type=detected_mime,
        size_bytes=len(sanitized),
        width=width,
        height=height,
        normalized_bytes=sanitized,
    )


async def create_meal_image_analysis_preview(
    *,
    session: AsyncSession,
    user: AuthenticatedUser,
    image_metadata: ValidatedMealImage,
    meal_type: MealType,
    eaten_at: datetime | None,
    client_request_id: str | None,
    settings: Settings,
    food_detector: FoodDetector | None = None,
    food_classifier: FoodImageClassifier | None = None,
) -> MealImageAnalysisStoreResult:
    """Persist a review-required food image preview for the current owner.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        image_metadata: Validated image metadata.
        meal_type: User-selected meal type.
        eaten_at: User-selected meal timestamp.
        client_request_id: Optional client idempotency key.
        settings: Runtime settings containing the privacy hash secret.
        food_detector: Optional injected local detector for tests.
        food_classifier: Optional injected local classifier for tests.

    Returns:
        Stored meal and food image preview rows.

    Raises:
        MealImageAnalysisConflictError: If the idempotency key exists with a
            different image hash.
        ValueError: If owner identity cannot be persisted safely.
    """
    owner_subject = build_owner_subject(user)
    normalized_client_request_id = derive_idempotency_key(
        client_request_id,
        owner_subject,
        settings.privacy_hash_secret,
    )
    # Vision inference (YOLO gate + DINOv3 + optional CLIP filter) is synchronous and
    # CPU-bound. Run it in a worker thread so one meal upload does not block the event
    # loop (and every other request in this worker) for the full inference duration.
    inference = await anyio.to_thread.run_sync(
        functools.partial(
            _run_food_image_inference_if_enabled,
            image_metadata=image_metadata,
            settings=settings,
            food_detector=food_detector,
            food_classifier=food_classifier,
        )
    )
    detected_items_snapshot = _food_candidates_to_snapshot(
        inference.detections,
        inference.classification,
    )
    nutrition_estimate_snapshot = await _nutrition_estimate_snapshot(
        session,
        inference.detections,
        classification=inference.classification,
        detector_used=inference.detector_used,
        classifier_used=inference.classifier_used,
    )
    analysis_run: FoodImageAnalysisRun | None = None
    meal_record: MealRecord | None = None
    reused_existing = False

    async with persist_scope(session):
        if normalized_client_request_id is not None:
            analysis_run = await session.scalar(
                select(FoodImageAnalysisRun).where(
                    FoodImageAnalysisRun.owner_subject == owner_subject,
                    FoodImageAnalysisRun.client_request_id == normalized_client_request_id,
                )
            )
            if analysis_run is not None:
                if analysis_run.image_sha256 != image_metadata.sha256:
                    raise MealImageAnalysisConflictError(
                        "client_request_id has already been used for a different image."
                    )
                reused_existing = True
                if analysis_run.meal_id is not None:
                    meal_record = await session.scalar(
                        select(MealRecord).where(
                            MealRecord.id == analysis_run.meal_id,
                            MealRecord.owner_subject == owner_subject,
                        )
                    )

        if analysis_run is not None and meal_record is None:
            raise MealImageAnalysisConflictError("stored meal preview is incomplete.")

        if analysis_run is None:
            meal_id = uuid4()
            meal_record = MealRecord(
                id=meal_id,
                owner_subject=owner_subject,
                client_request_id=normalized_client_request_id,
                eaten_at=_normalize_eaten_at(eaten_at),
                meal_type=meal_type.value,
                source="camera",
                status=MealAnalysisStatus.REQUIRES_CONFIRMATION.value,
                nutrition_summary=nutrition_estimate_snapshot,
                confidence=None,
                confirmed_at=None,
                deleted_at=None,
            )
            session.add(meal_record)
            await session.flush()
            analysis_run = FoodImageAnalysisRun(
                id=uuid4(),
                owner_subject=owner_subject,
                client_request_id=normalized_client_request_id,
                media_object_id=None,
                meal_id=meal_id,
                image_sha256=image_metadata.sha256,
                image_mime_type=image_metadata.mime_type,
                image_size_bytes=image_metadata.size_bytes,
                detector_model=inference.detector_model,
                classifier_model=inference.classifier_model,
                status=MealAnalysisStatus.REQUIRES_CONFIRMATION.value,
                detected_items_snapshot=detected_items_snapshot,
                nutrition_estimate_snapshot=nutrition_estimate_snapshot,
                warning_codes=list(inference.warning_codes),
            )
            session.add(analysis_run)
            reused_existing = False

    if not reused_existing:
        await session.refresh(meal_record)
        await session.refresh(analysis_run)
    return MealImageAnalysisStoreResult(
        meal_record=meal_record,
        analysis_run=analysis_run,
        image_metadata=image_metadata,
        reused_existing=reused_existing,
    )


def meal_image_analysis_to_preview(
    result: MealImageAnalysisStoreResult,
) -> MealImageAnalysisPreview:
    """Convert stored food image rows to a safe API preview response.

    Args:
        result: Persisted food image preview result.

    Returns:
        Meal image analysis preview response.
    """
    analysis_run = result.analysis_run
    meal_record = result.meal_record
    return MealImageAnalysisPreview(
        analysis_id=analysis_run.id,
        meal_id=meal_record.id,
        status=MealAnalysisStatus(analysis_run.status),
        meal_type=MealType(meal_record.meal_type),
        eaten_at=meal_record.eaten_at,
        food_candidates=_snapshot_to_food_candidates(analysis_run.detected_items_snapshot),
        nutrition_estimate_summary=_dict_or_empty(analysis_run.nutrition_estimate_snapshot),
        warning_codes=list(_string_items(analysis_run.warning_codes)),
        pipeline_metadata=FoodImagePipelineMetadata(
            intake_completed=True,
            detector_model=analysis_run.detector_model,
            classifier_model=analysis_run.classifier_model,
            detector_used=bool(analysis_run.detector_model)
            and not _contains_warning(analysis_run.warning_codes, "food_detector_unavailable"),
            classifier_used=bool(analysis_run.classifier_model)
            and not _contains_warning(analysis_run.warning_codes, "food_classifier_unavailable"),
            raw_image_stored=False,
            raw_provider_payload_stored=False,
            requires_manual_entry=not bool(_snapshot_items(analysis_run.detected_items_snapshot)),
        ),
        algorithm_version=FOOD_IMAGE_ANALYSIS_ALGORITHM_VERSION,
        created_at=analysis_run.created_at,
    )


async def confirm_meal_record_from_preview(
    *,
    session: AsyncSession,
    user: AuthenticatedUser,
    meal_id: UUID,
    request: MealConfirmationRequest,
) -> MealConfirmationStoreResult:
    """Persist user-confirmed food rows for a meal image preview.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        meal_id: Meal preview identifier from `/meals/analyze-image`.
        request: User-confirmed meal rows and optional preview trace id.

    Returns:
        Confirmed meal and food item rows.

    Raises:
        MealPreviewNotFoundError: If the meal or analysis preview is absent.
        MealPreviewStateError: If the preview has already left review state.
        MealConfirmationValidationError: If the analysis id does not match the meal.
    """
    owner_subject = build_owner_subject(user)
    meal_record = await session.scalar(
        select(MealRecord).where(
            MealRecord.id == meal_id,
            MealRecord.owner_subject == owner_subject,
            MealRecord.deleted_at.is_(None),
        )
    )
    if meal_record is None:
        raise MealPreviewNotFoundError("Meal preview was not found.")
    if meal_record.status != MealAnalysisStatus.REQUIRES_CONFIRMATION.value:
        raise MealPreviewStateError("Meal preview cannot be confirmed in its current state.")

    analysis_run: FoodImageAnalysisRun | None = None
    if request.analysis_id is not None:
        analysis_run = await session.scalar(
            select(FoodImageAnalysisRun).where(
                FoodImageAnalysisRun.id == request.analysis_id,
                FoodImageAnalysisRun.owner_subject == owner_subject,
            )
        )
        if analysis_run is None:
            raise MealPreviewNotFoundError("Food image analysis preview was not found.")
        if analysis_run.meal_id != meal_record.id:
            raise MealConfirmationValidationError(
                "Food image analysis preview does not belong to this meal."
            )
        if analysis_run.status != MealAnalysisStatus.REQUIRES_CONFIRMATION.value:
            raise MealPreviewStateError(
                "Food image analysis preview cannot be confirmed in its current state."
            )

    catalog_item_refs = await _validate_food_catalog_item_inputs(session, request.food_items)
    now = datetime.now(UTC)
    food_items = [
        _meal_food_item_from_input(meal_record.id, item, sort_order=index)
        for index, item in enumerate(request.food_items)
    ]
    async with persist_scope(session):
        meal_record.meal_type = (request.meal_type or MealType(meal_record.meal_type)).value
        meal_record.eaten_at = (
            _normalize_eaten_at(request.eaten_at) if request.eaten_at else meal_record.eaten_at
        )
        meal_record.status = MealAnalysisStatus.CONFIRMED.value
        meal_record.nutrition_summary = _confirmed_nutrition_summary(request.food_items)
        meal_record.confidence = _mean_confidence(request.food_items)
        meal_record.confirmed_at = now
        if analysis_run is not None:
            analysis_run.status = MealAnalysisStatus.CONFIRMED.value

        for item in food_items:
            session.add(item)

    await session.refresh(meal_record)
    return MealConfirmationStoreResult(
        meal_record=meal_record,
        food_items=food_items,
        analysis_run=analysis_run,
        catalog_item_refs=catalog_item_refs,
    )


async def list_user_meal_records(
    *,
    session: AsyncSession,
    user: AuthenticatedUser,
    limit: int,
    offset: int,
    cuisine_code: str | None = None,
    course_code: str | None = None,
    food_catalog_item_id: UUID | None = None,
    from_eaten_at: datetime | None = None,
    to_eaten_at: datetime | None = None,
) -> MealRecordListResponse:
    """List confirmed meal records visible to the current owner.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        limit: Maximum row count.
        offset: Row offset.
        cuisine_code: Optional cuisine taxonomy filter.
        course_code: Optional course taxonomy filter.
        food_catalog_item_id: Optional exact food catalog item filter.
        from_eaten_at: Optional inclusive lower meal timestamp.
        to_eaten_at: Optional inclusive upper meal timestamp.

    Returns:
        Paginated current-user meal records.

    Raises:
        TaxonomyFilterNotFoundError: If a supplied taxonomy filter has no active match.
        ValueError: If the timestamp range is invalid.
    """
    normalized_from = _normalize_optional_datetime(from_eaten_at)
    normalized_to = _normalize_optional_datetime(to_eaten_at)
    if (
        normalized_from is not None
        and normalized_to is not None
        and normalized_from > normalized_to
    ):
        raise ValueError("from_eaten_at must be before or equal to to_eaten_at.")

    await validate_food_catalog_filters(
        session,
        cuisine_code=cuisine_code,
        course_code=course_code,
        food_catalog_item_id=food_catalog_item_id,
    )
    meal_records = await _list_owned_confirmed_meals(
        session=session,
        user=user,
        limit=limit,
        offset=offset,
        cuisine_code=cuisine_code,
        course_code=course_code,
        food_catalog_item_id=food_catalog_item_id,
        from_eaten_at=normalized_from,
        to_eaten_at=normalized_to,
    )
    food_items_by_meal = await _load_food_items_for_meals(
        session,
        [meal_record.id for meal_record in meal_records],
    )
    catalog_refs = await _load_catalog_refs_for_food_items(
        session,
        [item for items in food_items_by_meal.values() for item in items],
    )
    return MealRecordListResponse(
        results=[
            meal_record_to_response(
                meal_record,
                food_items_by_meal.get(meal_record.id, []),
                catalog_item_refs=catalog_refs,
            )
            for meal_record in meal_records
        ],
        limit=limit,
        offset=offset,
    )


async def get_user_meal_record(
    *,
    session: AsyncSession,
    user: AuthenticatedUser,
    meal_id: UUID,
) -> MealRecordResponse:
    """Load one confirmed current-user meal record.

    Args:
        session: Request-scoped database session.
        user: Authenticated owner.
        meal_id: Meal record identifier.

    Returns:
        Confirmed meal record response without owner or raw media data.

    Raises:
        MealPreviewNotFoundError: If the meal is absent, soft-deleted, or not confirmed.
    """
    result = await session.scalars(
        select(MealRecord).where(
            MealRecord.id == meal_id,
            MealRecord.owner_subject == build_owner_subject(user),
            MealRecord.deleted_at.is_(None),
            MealRecord.status == MealAnalysisStatus.CONFIRMED.value,
        )
    )
    meal_record = result.one_or_none()
    if meal_record is None:
        raise MealPreviewNotFoundError("Confirmed meal record was not found.")

    food_items_by_meal = await _load_food_items_for_meals(session, [meal_record.id])
    food_items = food_items_by_meal.get(meal_record.id, [])
    catalog_refs = await _load_catalog_refs_for_food_items(session, food_items)
    return meal_record_to_response(
        meal_record,
        food_items,
        catalog_item_refs=catalog_refs,
    )


async def update_user_meal_record(
    *,
    session: AsyncSession,
    user: AuthenticatedUser,
    meal_id: UUID,
    request: MealRecordUpdateRequest,
) -> MealRecordResponse:
    """Edit one confirmed current-user meal record.

    Args:
        session: Request-scoped database session.
        user: Authenticated owner.
        meal_id: Confirmed meal record identifier.
        request: Replacement food rows and optional meal metadata edits.

    Returns:
        Updated current-user meal record response.

    Raises:
        MealPreviewNotFoundError: If the meal is absent, soft-deleted, or not confirmed.
    """
    meal_record = await session.scalar(
        select(MealRecord).where(
            MealRecord.id == meal_id,
            MealRecord.owner_subject == build_owner_subject(user),
            MealRecord.deleted_at.is_(None),
            MealRecord.status == MealAnalysisStatus.CONFIRMED.value,
        )
    )
    if meal_record is None:
        raise MealPreviewNotFoundError("Confirmed meal record was not found.")

    replacement_items: list[MealFoodItem] | None = None
    catalog_item_refs: dict[UUID, FoodCatalogItemReference] | None = None
    if request.food_items is not None:
        catalog_item_refs = await _validate_food_catalog_item_inputs(
            session,
            request.food_items,
        )
        replacement_items = [
            _meal_food_item_from_input(meal_record.id, item, sort_order=index)
            for index, item in enumerate(request.food_items)
        ]

    async with persist_scope(session):
        if request.meal_type is not None:
            meal_record.meal_type = request.meal_type.value
        if request.eaten_at is not None:
            meal_record.eaten_at = _normalize_eaten_at(request.eaten_at)
        if replacement_items is not None and request.food_items is not None:
            await session.execute(
                delete(MealFoodItem).where(MealFoodItem.meal_id == meal_record.id)
            )
            meal_record.nutrition_summary = _confirmed_nutrition_summary(
                request.food_items,
            )
            meal_record.confidence = _mean_confidence(request.food_items)
            for item in replacement_items:
                session.add(item)

    await session.refresh(meal_record)
    if replacement_items is None:
        food_items_by_meal = await _load_food_items_for_meals(session, [meal_record.id])
        food_items = food_items_by_meal.get(meal_record.id, [])
        catalog_item_refs = await _load_catalog_refs_for_food_items(session, food_items)
    else:
        food_items = replacement_items

    return meal_record_to_response(
        meal_record,
        food_items,
        catalog_item_refs=catalog_item_refs,
    )


async def delete_user_meal_record(
    *,
    session: AsyncSession,
    user: AuthenticatedUser,
    meal_id: UUID,
) -> None:
    """Soft-delete one confirmed current-user meal record.

    Args:
        session: Request-scoped database session.
        user: Authenticated owner.
        meal_id: Confirmed meal record identifier.

    Raises:
        MealPreviewNotFoundError: If the meal is absent, already deleted, or unconfirmed.
    """
    meal_record = await session.scalar(
        select(MealRecord).where(
            MealRecord.id == meal_id,
            MealRecord.owner_subject == build_owner_subject(user),
            MealRecord.deleted_at.is_(None),
            MealRecord.status == MealAnalysisStatus.CONFIRMED.value,
        )
    )
    if meal_record is None:
        raise MealPreviewNotFoundError("Confirmed meal record was not found.")

    async with persist_scope(session):
        meal_record.status = "deleted"
        meal_record.deleted_at = datetime.now(UTC)


def meal_confirmation_to_response(
    result: MealConfirmationStoreResult,
) -> MealRecordResponse:
    """Convert confirmed meal rows into the public API response.

    Args:
        result: Persisted meal confirmation result.

    Returns:
        Current-user meal record response without owner identifiers.
    """
    return meal_record_to_response(
        result.meal_record,
        result.food_items,
        catalog_item_refs=result.catalog_item_refs,
    )


def meal_record_to_response(
    meal_record: MealRecord,
    food_items: list[MealFoodItem],
    *,
    catalog_item_refs: dict[UUID, FoodCatalogItemReference] | None = None,
) -> MealRecordResponse:
    """Convert confirmed meal rows into the public API response.

    Args:
        meal_record: Persisted confirmed meal row.
        food_items: Persisted food item rows for the meal.
        catalog_item_refs: Catalog references keyed by food catalog item id.

    Returns:
        Current-user meal record response without owner identifiers.

    Raises:
        MealConfirmationValidationError: If the meal record is not confirmed.
    """
    if meal_record.confirmed_at is None:
        raise MealConfirmationValidationError("Meal record is not confirmed.")
    return MealRecordResponse(
        id=meal_record.id,
        status=MealAnalysisStatus(meal_record.status),
        meal_type=MealType(meal_record.meal_type),
        eaten_at=meal_record.eaten_at,
        food_items=[
            _meal_food_item_to_response(item, catalog_item_refs=catalog_item_refs or {})
            for item in food_items
        ],
        nutrition_summary=_dict_or_empty(meal_record.nutrition_summary),
        confirmed_at=meal_record.confirmed_at,
        created_at=meal_record.created_at,
    )


def _detect_food_candidates_if_enabled(
    *,
    image_metadata: ValidatedMealImage,
    settings: Settings,
    food_detector: FoodDetector | None,
) -> FoodDetectionResult:
    """Run optional food YOLO without storing image bytes or provider payloads.

    Args:
        image_metadata: Validated in-memory image metadata and bytes.
        settings: Runtime settings.
        food_detector: Optional injected detector.

    Returns:
        Sanitized detector outcome for persistence.
    """
    if not settings.enable_food_yolo_detector:
        return FoodDetectionResult(
            detections=(),
            detector_model=None,
            detector_used=False,
            warning_codes=FOOD_IMAGE_ANALYSIS_WARNING_CODES,
        )

    detector_model = food_model_label(
        settings.meal_yolo_model_path,
        settings.meal_yolo_model_label,
    )
    if detector_model is None:
        return FoodDetectionResult(
            detections=(),
            detector_model=None,
            detector_used=False,
            warning_codes=FOOD_IMAGE_DETECTOR_UNAVAILABLE_WARNING_CODES,
        )

    detector = food_detector or FoodYoloDetector(
        model_path=settings.meal_yolo_model_path or "",
        model_label=detector_model,
        min_confidence=settings.meal_yolo_min_confidence,
        max_detections=settings.meal_yolo_max_detections,
    )
    try:
        detections = tuple(detector.detect_foods(image_metadata.normalized_bytes))
    except (OSError, ValueError, VisionError):
        return FoodDetectionResult(
            detections=(),
            detector_model=detector_model,
            detector_used=False,
            warning_codes=FOOD_IMAGE_DETECTOR_UNAVAILABLE_WARNING_CODES,
        )
    if not detections:
        return FoodDetectionResult(
            detections=(),
            detector_model=detector_model,
            detector_used=True,
            warning_codes=FOOD_IMAGE_DETECTOR_EMPTY_WARNING_CODES,
        )
    return FoodDetectionResult(
        detections=detections,
        detector_model=detector_model,
        detector_used=True,
        warning_codes=FOOD_IMAGE_DETECTION_REVIEW_WARNING_CODES,
    )


def _classify_food_candidate_if_enabled(
    *,
    image_metadata: ValidatedMealImage,
    settings: Settings,
    food_classifier: FoodImageClassifier | None,
) -> FoodClassificationResult:
    """Run optional food DINO classifier without storing image bytes or payloads.

    Args:
        image_metadata: Validated in-memory image metadata and bytes.
        settings: Runtime settings.
        food_classifier: Optional injected classifier.

    Returns:
        Sanitized classifier outcome for persistence.
    """
    if not settings.enable_food_dino_classifier:
        return FoodClassificationResult(
            classification=None,
            classifier_model=None,
            classifier_used=False,
            warning_codes=(),
        )

    classifier_model = food_classifier_model_label(
        settings.meal_food_classifier_model_label,
        settings.meal_food_classifier_probe_path,
    )
    if classifier_model is None:
        return FoodClassificationResult(
            classification=None,
            classifier_model=None,
            classifier_used=False,
            warning_codes=FOOD_IMAGE_CLASSIFIER_UNAVAILABLE_WARNING_CODES,
        )

    classifier = food_classifier or get_shared_food_dino_classifier(
        module_dir=settings.meal_food_classifier_module_dir,
        exp16b_model_path=settings.meal_food_classifier_exp16b_model_path or "",
        probe_path=settings.meal_food_classifier_probe_path or "",
        nutrition_csv_path=settings.meal_food_classifier_nutrition_csv_path or "",
        model_label=classifier_model,
        detector_confidence=settings.meal_food_classifier_gate_confidence,
        max_px=settings.meal_food_classifier_max_px,
        enable_food_filter=settings.enable_food_clip_filter,
        food_filter_threshold=settings.food_clip_filter_threshold,
        food_filter_model_id=settings.food_clip_filter_model_id,
    )
    try:
        classification = classifier.classify_food(image_metadata.normalized_bytes)
    except (OSError, ValueError, VisionError):
        return FoodClassificationResult(
            classification=None,
            classifier_model=classifier_model,
            classifier_used=False,
            warning_codes=FOOD_IMAGE_CLASSIFIER_UNAVAILABLE_WARNING_CODES,
        )
    if classification is None:
        return FoodClassificationResult(
            classification=None,
            classifier_model=classifier_model,
            classifier_used=True,
            warning_codes=FOOD_IMAGE_CLASSIFIER_EMPTY_WARNING_CODES,
        )
    return FoodClassificationResult(
        classification=classification,
        classifier_model=classifier_model,
        classifier_used=True,
        warning_codes=FOOD_IMAGE_CLASSIFICATION_REVIEW_WARNING_CODES,
    )


def _run_food_image_inference_if_enabled(
    *,
    image_metadata: ValidatedMealImage,
    settings: Settings,
    food_detector: FoodDetector | None,
    food_classifier: FoodImageClassifier | None,
) -> FoodImageInferenceResult:
    """Run enabled food image inference providers and merge safe preview metadata.

    Args:
        image_metadata: Validated in-memory image metadata and bytes.
        settings: Runtime settings.
        food_detector: Optional injected detector.
        food_classifier: Optional injected classifier.

    Returns:
        Combined detector/classifier inference result.
    """
    detection = _detect_food_candidates_if_enabled(
        image_metadata=image_metadata,
        settings=settings,
        food_detector=food_detector,
    )
    classification = _classify_food_candidate_if_enabled(
        image_metadata=image_metadata,
        settings=settings,
        food_classifier=food_classifier,
    )
    has_candidates = bool(detection.detections) or classification.classification is not None
    warning_codes = _merged_food_warning_codes(
        detector_enabled=settings.enable_food_yolo_detector,
        classifier_enabled=settings.enable_food_dino_classifier,
        detection_warning_codes=detection.warning_codes,
        classification_warning_codes=classification.warning_codes,
        has_candidates=has_candidates,
    )
    return FoodImageInferenceResult(
        detections=detection.detections,
        classification=classification.classification,
        detector_model=detection.detector_model,
        classifier_model=classification.classifier_model,
        detector_used=detection.detector_used,
        classifier_used=classification.classifier_used,
        warning_codes=warning_codes,
    )


def _food_candidates_to_snapshot(
    detections: tuple[FoodDetection, ...],
    classification: FoodClassification | None,
) -> dict[str, object]:
    """Convert food inference outputs into sanitized JSON snapshot data.

    Args:
        detections: Detector candidates.
        classification: Classifier candidate.

    Returns:
        JSON object without image bytes or provider payloads.
    """
    items: list[dict[str, object]] = []
    if classification is not None:
        item: dict[str, object] = {
            "display_name": classification.display_name,
            "class_en": classification.name_en,
            "confidence": classification.confidence,
            "source": "vision",
            "model": classification.model,
            "candidate_type": "classifier",
        }
        if classification.bbox is not None:
            item["bbox"] = _bbox_snapshot(classification.bbox)
        nutrition = _classification_serving_nutrition(classification.nutrition)
        if nutrition:
            item["nutrition"] = nutrition
        items.append(item)
    items.extend(
        {
            "display_name": detection.label,
            "confidence": detection.confidence,
            "source": "vision",
            "bbox": _bbox_snapshot(detection.bbox),
            "model": detection.model,
            "candidate_type": "detector",
        }
        for detection in detections
    )
    return {"items": items}


async def _nutrition_estimate_snapshot(
    session: AsyncSession,
    detections: tuple[FoodDetection, ...],
    *,
    classification: FoodClassification | None,
    detector_used: bool,
    classifier_used: bool,
) -> dict[str, object]:
    """Build a bounded advisory pre-confirmation nutrition summary.

    For each detection whose label matches an active ``food_nutrition`` class,
    this attaches a class-average per-serving estimate and contributes to a
    summed ``totals`` block. The estimate is advisory only and never overrides
    user-confirmed values; unmatched detections keep ``source`` "vision".

    Args:
        session: Request-scoped async database session for catalog lookups.
        detections: Detector candidates.
        classification: Classifier candidate.
        detector_used: Whether detector inference ran.
        classifier_used: Whether classifier inference ran.

    Returns:
        Safe nutrition summary for user review with sanitized, bounded values.
    """
    has_candidates = bool(detections) or classification is not None
    status = "detected_review_required" if has_candidates else "analysis_unavailable"
    if not has_candidates:
        return {
            "status": status,
            "items": [],
            "totals": {},
            "detector_used": detector_used,
            "classifier_used": classifier_used,
        }

    nutrition_by_class = await load_food_nutrition_by_class_ens(
        session,
        [detection.label for detection in detections],
    )
    items: list[dict[str, object]] = []
    totals: dict[str, float] = {}
    matched = False
    if classification is not None:
        item = {
            "display_name": classification.display_name,
            "class_en": classification.name_en,
            "confidence": classification.confidence,
            "source": "vision",
            "candidate_type": "classifier",
        }
        serving = _classification_serving_nutrition(classification.nutrition)
        if serving:
            matched = True
            item["nutrition"] = serving
            for key, value in serving.items():
                totals[key] = round(totals.get(key, 0.0) + value, 2)
        items.append(item)
    for detection in detections:
        item: dict[str, object] = {
            "display_name": detection.label,
            "confidence": detection.confidence,
            "source": "vision",
            "candidate_type": "detector",
        }
        row = nutrition_by_class.get(detection.label)
        if row is not None:
            serving = compute_serving_nutrition(
                food_nutrition_per_100g(row),
                serving_g=row.serving_g,
            )
            if serving:
                matched = True
                item["nutrition"] = serving
                for key, value in serving.items():
                    totals[key] = round(totals.get(key, 0.0) + value, 2)
        items.append(item)

    snapshot: dict[str, object] = {
        "status": status,
        "items": items,
        "totals": totals,
        "detector_used": detector_used,
        "classifier_used": classifier_used,
    }
    if matched:
        snapshot["basis"] = "class_average_per_serving"
        snapshot["precision_note"] = "demo_class_average_not_medical_or_prescriptive"
    return snapshot


def _snapshot_to_food_candidates(value: Any) -> list[MealFoodCandidate]:
    """Convert stored snapshot JSON into API food candidates.

    Args:
        value: Stored JSON snapshot.

    Returns:
        Review-only food candidates.
    """
    candidates: list[MealFoodCandidate] = []
    for item in _snapshot_items(value):
        display_name = item.get("display_name")
        confidence = item.get("confidence")
        if not isinstance(display_name, str):
            continue
        if not isinstance(confidence, int | float):
            continue
        nutrition = item.get("nutrition")
        nutrition_mapping = nutrition if isinstance(nutrition, dict) else {}
        candidates.append(
            MealFoodCandidate(
                display_name=display_name,
                portion_amount=_float_or_none(nutrition_mapping.get("serving_g")),
                portion_unit="g" if _float_or_none(nutrition_mapping.get("serving_g")) else None,
                kcal=_float_or_none(nutrition_mapping.get("kcal")),
                carb_g=_float_or_none(nutrition_mapping.get("carb_g")),
                protein_g=_float_or_none(nutrition_mapping.get("protein_g")),
                fat_g=_float_or_none(nutrition_mapping.get("fat_g")),
                sodium_mg=_float_or_none(nutrition_mapping.get("sodium_mg")),
                confidence=float(confidence),
                source="vision",
            )
        )
    return candidates


def _snapshot_items(value: Any) -> list[dict[str, object]]:
    """Return dictionary items from snapshot JSON.

    Args:
        value: Stored snapshot JSON.

    Returns:
        Snapshot item dictionaries.
    """
    if not isinstance(value, dict):
        return []
    items = value.get("items")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _contains_warning(value: Any, warning_code: str) -> bool:
    """Return whether warning JSON contains a code.

    Args:
        value: Stored warning JSON.
        warning_code: Warning to find.

    Returns:
        True when present.
    """
    return isinstance(value, list) and warning_code in value


def _merged_food_warning_codes(
    *,
    detector_enabled: bool,
    classifier_enabled: bool,
    detection_warning_codes: tuple[str, ...],
    classification_warning_codes: tuple[str, ...],
    has_candidates: bool,
) -> tuple[str, ...]:
    """Merge detector and classifier warning codes without duplicate UI prompts.

    Args:
        detector_enabled: Whether the detector provider was configured.
        classifier_enabled: Whether the classifier provider was configured.
        detection_warning_codes: Detector warning codes.
        classification_warning_codes: Classifier warning codes.
        has_candidates: Whether any review candidate exists.

    Returns:
        Stable, de-duplicated warning codes.
    """
    if not detector_enabled and not classifier_enabled:
        return FOOD_IMAGE_ANALYSIS_WARNING_CODES

    warning_codes: list[str] = []
    if detector_enabled:
        warning_codes.extend(detection_warning_codes)
    if classifier_enabled:
        warning_codes.extend(classification_warning_codes)

    if has_candidates:
        warning_codes = [
            code
            for code in warning_codes
            if code
            not in {
                "food_analysis_unavailable",
                "food_detector_empty",
                "food_classifier_empty",
                "manual_entry_required",
            }
        ]

    if not has_candidates and "manual_entry_required" not in warning_codes:
        warning_codes.append("manual_entry_required")
    return tuple(dict.fromkeys(warning_codes))


def _bbox_snapshot(bbox: Any) -> dict[str, object]:
    """Convert a bounding box into safe JSON metadata.

    Args:
        bbox: Bounding box-like object.

    Returns:
        JSON-serializable box snapshot.
    """
    return {
        "x": bbox.x,
        "y": bbox.y,
        "width": bbox.width,
        "height": bbox.height,
    }


def _classification_serving_nutrition(
    nutrition: Mapping[str, object] | None,
) -> dict[str, float]:
    """Convert a classifier CSV row into one-serving nutrition values.

    Args:
        nutrition: Raw classifier nutrition row keyed by CSV column name.

    Returns:
        Per-serving nutrition estimate, including ``serving_g`` when available.
    """
    if nutrition is None:
        return {}
    serving_g = _float_or_none(nutrition.get("serving_g"))
    scaled = compute_serving_nutrition(
        {
            "kcal": _float_or_none(nutrition.get("kcal_100g")),
            "carb_g": _float_or_none(nutrition.get("carb_g")),
            "sugar_g": _float_or_none(nutrition.get("sugar_g")),
            "fat_g": _float_or_none(nutrition.get("fat_g")),
            "protein_g": _float_or_none(nutrition.get("protein_g")),
            "sodium_mg": _float_or_none(nutrition.get("sodium_mg")),
            "cholesterol_mg": _float_or_none(nutrition.get("chol_mg")),
            "saturated_fat_g": _float_or_none(nutrition.get("sat_fat_g")),
            "trans_fat_g": _float_or_none(nutrition.get("trans_fat_g")),
        },
        serving_g=serving_g,
    )
    if serving_g is not None and scaled:
        scaled["serving_g"] = serving_g
    return scaled


def _float_or_none(value: object) -> float | None:
    """Safely coerce a numeric value to float.

    Args:
        value: Candidate numeric value.

    Returns:
        Float value, or None when the input is absent/invalid.
    """
    parsed: float | None = None
    if isinstance(value, Decimal | int | float):
        parsed = float(value)
    elif isinstance(value, str):
        stripped = value.strip()
        if stripped:
            try:
                parsed = float(stripped)
            except ValueError:
                parsed = None
    return parsed


async def _read_limited_upload(image: UploadFile, max_bytes: int) -> bytes:
    """Read an uploaded file while enforcing a byte limit.

    Args:
        image: Uploaded file.
        max_bytes: Maximum accepted byte count.

    Returns:
        Uploaded bytes.

    Raises:
        MealImageValidationError: If the upload exceeds the size limit.
    """
    chunks: list[bytes] = []
    total_size = 0
    while True:
        chunk = await image.read(READ_CHUNK_SIZE_BYTES)
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > max_bytes:
            raise MealImageValidationError(
                code="payload_too_large",
                message="Uploaded food image exceeds the configured size limit.",
                status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _validate_decodable_image(data: bytes, max_pixels: int) -> tuple[int, int]:
    """Verify image structure and pixel bounds without persisting image bytes.

    Args:
        data: Uploaded image bytes.
        max_pixels: Maximum accepted pixel count.

    Returns:
        Image width and height.

    Raises:
        MealImageValidationError: If the image is malformed or too large.
    """
    try:
        with Image.open(BytesIO(data)) as image:
            width, height = image.size
            if width <= 0 or height <= 0:
                raise MealImageValidationError(
                    code="invalid_image",
                    message="Uploaded food image has invalid dimensions.",
                    status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                )
            if width * height > max_pixels:
                raise MealImageValidationError(
                    code="payload_too_large",
                    message="Uploaded food image exceeds the configured pixel limit.",
                    status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                )
            image.verify()
    except MealImageValidationError:
        raise
    except Image.DecompressionBombError as exc:
        raise MealImageValidationError(
            code="payload_too_large",
            message="Uploaded food image exceeds the configured pixel limit.",
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        ) from exc
    except (OSError, SyntaxError, UnidentifiedImageError) as exc:
        raise MealImageValidationError(
            code="invalid_image",
            message="Uploaded food image cannot be decoded.",
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        ) from exc

    try:
        with safe_load_with_bomb_guard(data) as decoded:
            width, height = decoded.size
            return int(width), int(height)
    except ImageSafetyError as exc:
        raise MealImageValidationError(
            code="payload_too_large",
            message="Uploaded food image is too large to decode safely.",
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        ) from exc


def _normalize_eaten_at(value: datetime | None) -> datetime:
    """Return a timezone-aware meal timestamp.

    Args:
        value: User-selected timestamp or None.

    Returns:
        UTC-aware timestamp.
    """
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _normalize_optional_datetime(value: datetime | None) -> datetime | None:
    """Normalize an optional timestamp into UTC.

    Args:
        value: User-selected timestamp or None.

    Returns:
        UTC-aware timestamp or None.
    """
    if value is None:
        return None
    return _normalize_eaten_at(value)


async def _validate_food_catalog_item_inputs(
    session: AsyncSession,
    food_items: list[MealFoodItemInput],
) -> dict[UUID, FoodCatalogItemReference]:
    """Validate active food catalog item ids supplied by confirmation input.

    Args:
        session: Request-scoped async database session.
        food_items: User-confirmed food rows.

    Returns:
        Active catalog references keyed by catalog item id.

    Raises:
        MealConfirmationValidationError: If any supplied catalog item is missing or inactive.
    """
    catalog_ids = [
        item.food_catalog_item_id for item in food_items if item.food_catalog_item_id is not None
    ]
    if not catalog_ids:
        return {}
    refs = await load_food_catalog_item_references(session, catalog_ids)
    missing = [catalog_id for catalog_id in catalog_ids if catalog_id not in refs]
    if missing:
        raise MealConfirmationValidationError("Food catalog item was not found.")
    return refs


async def _list_owned_confirmed_meals(
    *,
    session: AsyncSession,
    user: AuthenticatedUser,
    limit: int,
    offset: int,
    cuisine_code: str | None,
    course_code: str | None,
    food_catalog_item_id: UUID | None,
    from_eaten_at: datetime | None,
    to_eaten_at: datetime | None,
) -> list[MealRecord]:
    """Load confirmed meal records for a current user with optional taxonomy filters."""
    stmt = select(MealRecord).where(
        MealRecord.owner_subject == build_owner_subject(user),
        MealRecord.deleted_at.is_(None),
        MealRecord.status == MealAnalysisStatus.CONFIRMED.value,
    )
    if from_eaten_at is not None:
        stmt = stmt.where(MealRecord.eaten_at >= from_eaten_at)
    if to_eaten_at is not None:
        stmt = stmt.where(MealRecord.eaten_at <= to_eaten_at)

    normalized_cuisine = _normalized_filter(cuisine_code)
    normalized_course = _normalized_filter(course_code)
    if (
        normalized_cuisine is not None
        or normalized_course is not None
        or food_catalog_item_id is not None
    ):
        stmt = (
            stmt.join(MealFoodItem, MealFoodItem.meal_id == MealRecord.id)
            .join(FoodCatalogItem, MealFoodItem.food_catalog_item_id == FoodCatalogItem.id)
            .join(FoodCuisine, FoodCatalogItem.cuisine_id == FoodCuisine.id)
            .join(FoodCourse, FoodCatalogItem.course_id == FoodCourse.id)
            .where(
                FoodCatalogItem.is_active.is_(True),
                FoodCuisine.is_active.is_(True),
                FoodCourse.is_active.is_(True),
            )
            .distinct()
        )
        if normalized_cuisine is not None:
            stmt = stmt.where(FoodCuisine.cuisine_code == normalized_cuisine)
        if normalized_course is not None:
            stmt = stmt.where(FoodCourse.course_code == normalized_course)
        if food_catalog_item_id is not None:
            stmt = stmt.where(FoodCatalogItem.id == food_catalog_item_id)

    result = await session.scalars(
        stmt.order_by(desc(MealRecord.eaten_at), desc(MealRecord.created_at))
        .limit(limit)
        .offset(offset)
    )
    return list(result.all())


async def _load_food_items_for_meals(
    session: AsyncSession,
    meal_ids: list[UUID],
) -> dict[UUID, list[MealFoodItem]]:
    """Load food item rows grouped by meal id."""
    ids = list(dict.fromkeys(meal_ids))
    if not ids:
        return {}
    result = await session.scalars(
        select(MealFoodItem)
        .where(MealFoodItem.meal_id.in_(ids))
        .order_by(MealFoodItem.meal_id.asc(), MealFoodItem.sort_order.asc())
    )
    grouped: dict[UUID, list[MealFoodItem]] = {}
    for item in result.all():
        grouped.setdefault(item.meal_id, []).append(item)
    return grouped


async def _load_catalog_refs_for_food_items(
    session: AsyncSession,
    food_items: list[MealFoodItem],
) -> dict[UUID, FoodCatalogItemReference]:
    """Load catalog references for confirmed food item rows."""
    return await load_food_catalog_item_references(
        session,
        [item.food_catalog_item_id for item in food_items if item.food_catalog_item_id is not None],
    )


def _normalized_filter(value: str | None) -> str | None:
    """Trim optional taxonomy filter text and normalize blanks to None."""
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _meal_food_item_from_input(
    meal_id: UUID,
    item: MealFoodItemInput,
    *,
    sort_order: int,
) -> MealFoodItem:
    """Build a persisted food item from user-confirmed input.

    Args:
        meal_id: Parent meal id.
        item: User-confirmed food item.
        sort_order: Stable display order.

    Returns:
        Unsaved meal food item row.
    """
    return MealFoodItem(
        id=uuid4(),
        meal_id=meal_id,
        food_name_text=item.display_name,
        food_catalog_item_id=item.food_catalog_item_id,
        canonical_food_id=None,
        portion_amount=_decimal_or_none(item.portion_amount),
        portion_unit=item.portion_unit,
        kcal=_decimal_or_none(item.kcal),
        carb_g=_decimal_or_none(item.carb_g),
        protein_g=_decimal_or_none(item.protein_g),
        fat_g=_decimal_or_none(item.fat_g),
        sodium_mg=_decimal_or_none(item.sodium_mg),
        source=item.source,
        confidence=_decimal_or_none(item.confidence),
        sort_order=sort_order,
    )


def _meal_food_item_to_response(
    item: MealFoodItem,
    *,
    catalog_item_refs: dict[UUID, FoodCatalogItemReference],
) -> MealFoodItemResponse:
    """Convert one persisted food item row to API response data.

    Args:
        item: Persisted meal food item row.
        catalog_item_refs: Catalog references keyed by food catalog item id.

    Returns:
        Public meal food item response.
    """
    catalog_item_id = item.food_catalog_item_id
    return MealFoodItemResponse(
        id=item.id,
        display_name=item.food_name_text,
        portion_amount=_float_or_none(item.portion_amount),
        portion_unit=item.portion_unit,
        kcal=_float_or_none(item.kcal),
        carb_g=_float_or_none(item.carb_g),
        protein_g=_float_or_none(item.protein_g),
        fat_g=_float_or_none(item.fat_g),
        sodium_mg=_float_or_none(item.sodium_mg),
        food_catalog_item_id=catalog_item_id,
        catalog_item=(
            catalog_item_refs.get(catalog_item_id) if catalog_item_id is not None else None
        ),
        confidence=_float_or_none(item.confidence),
        source=item.source,
    )


def _confirmed_nutrition_summary(
    items: list[MealFoodItemInput],
) -> dict[str, object]:
    """Build a bounded nutrition summary from confirmed meal inputs.

    Args:
        items: User-confirmed food rows.

    Returns:
        JSON summary with numeric totals only.
    """
    totals: dict[str, float] = {}
    for field_name in ("kcal", "carb_g", "protein_g", "fat_g", "sodium_mg"):
        values = [getattr(item, field_name) for item in items]
        numeric_values = [value for value in values if isinstance(value, int | float)]
        if numeric_values:
            totals[field_name] = round(float(sum(numeric_values)), 2)
    return {
        "status": "user_confirmed",
        "items_count": len(items),
        "totals": totals,
    }


def _mean_confidence(items: list[MealFoodItemInput]) -> Decimal | None:
    """Return mean confidence across confirmed items when present.

    Args:
        items: User-confirmed food rows.

    Returns:
        Decimal mean confidence, or None when no item has confidence.
    """
    confidence_values = [
        item.confidence for item in items if isinstance(item.confidence, int | float)
    ]
    if not confidence_values:
        return None
    return Decimal(str(round(sum(confidence_values) / len(confidence_values), 4)))


def _decimal_or_none(value: float | None) -> Decimal | None:
    """Convert a JSON numeric value to Decimal for persistence.

    Args:
        value: Optional numeric value.

    Returns:
        Decimal value or None.
    """
    return Decimal(str(value)) if value is not None else None


def _float_or_none(value: object) -> float | None:  # noqa: PLR0911
    """Convert optional numeric-like values to float for API responses.

    Args:
        value: Optional numeric value or provider/catalog text value.

    Returns:
        Float value or None when the input is absent, blank, or non-numeric.
    """
    if value is None:
        return None
    if isinstance(value, Decimal | int | float):
        return float(value)
    if isinstance(value, str):
        normalized = value.strip().replace(",", "")
        if not normalized:
            return None
        try:
            return float(normalized)
        except ValueError:
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dict_or_empty(value: Any) -> dict[str, object]:
    """Return a dictionary value or an empty dictionary.

    Args:
        value: Candidate JSON value.

    Returns:
        Dictionary value when present.
    """
    return value if isinstance(value, dict) else {}


def _string_items(value: Any) -> tuple[str, ...]:
    """Return bounded string items from a JSON value.

    Args:
        value: Candidate JSON array.

    Returns:
        Tuple of string values.
    """
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))
