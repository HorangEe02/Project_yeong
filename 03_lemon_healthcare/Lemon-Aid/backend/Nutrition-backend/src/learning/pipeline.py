"""Service helpers for the consent-gated learning/vector pipeline."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings
from src.learning.consent_gate import IMAGE_LEARNING_REQUIRED_CONSENTS, evaluate_image_learning_gate
from src.learning.object_storage import (
    LearningImageObjectInput,
    LearningImageObjectStore,
    LearningObjectStorageError,
)
from src.learning.retention import image_retention_deadline
from src.models.db.learning import ImageEmbeddingJob, ImageEmbeddingRecord, LearningImageObject
from src.models.db.privacy import ConsentRecord
from src.models.db.supplement import SupplementAnalysisRun, UserSupplement, UserSupplementIngredient
from src.models.schemas.privacy import ConsentType
from src.privacy.consent_policies import get_active_policy
from src.security.auth import AuthenticatedUser
from src.security.privacy import hash_actor_subject
from src.security.subjects import build_owner_subject
from src.services.supplement_intake import ValidatedSupplementImage

LEARNING_IMAGE_STATUS_AWAITING_CONFIRMATION = "awaiting_confirmation"
LEARNING_IMAGE_STATUS_PENDING_AUTO_FILTER = "pending_auto_filter"
LEARNING_IMAGE_STATUS_PENDING_MANUAL_REVIEW = "pending_manual_review"
LEARNING_IMAGE_STATUS_REJECTED_BY_AUTO_FILTER = "rejected_by_auto_filter"
LEARNING_IMAGE_STATUS_APPROVED_FOR_EMBEDDING = "approved_for_embedding"
LEARNING_IMAGE_STATUS_REJECTED_BY_REVIEW = "rejected_by_review"
LEARNING_IMAGE_STATUS_READY = "ready"
LEARNING_IMAGE_STATUS_DELETED = "deleted"
LEARNING_IMAGE_STATUS_FAILED = "failed"
IMAGE_EMBEDDING_JOB_STATUS_PENDING = "pending"
FORBIDDEN_LEARNING_METADATA_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "authorization",
        "credential",
        "credentials",
        "image_base64",
        "image_bytes",
        "ocr_text",
        "provider_payload",
        "raw_image",
        "raw_image_bytes",
        "raw_llm_response",
        "raw_ocr_text",
        "raw_provider_payload",
        "request_headers",
        "secret",
        "service_key",
    }
)
NORMALIZED_FORBIDDEN_LEARNING_METADATA_KEYS = frozenset(
    "".join(character for character in key.casefold() if character.isalnum())
    for key in FORBIDDEN_LEARNING_METADATA_KEYS
)
PII_LIKE_TEXT_PATTERN = re.compile(
    r"(?P<email>[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})|" r"(?P<phone>\+?\d[\d\s().-]{7,}\d)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class LearningMetadataAutoFilterDecision:
    """Decision returned by the learning metadata auto-filter.

    Attributes:
        allowed: Whether the metadata may continue to review or embedding.
        reason: Stable reason string safe for logs and tests.
    """

    allowed: bool
    reason: str


async def collect_active_learning_consents(
    session: AsyncSession,
    user: AuthenticatedUser,
) -> tuple[ConsentType, ...]:
    """Collect active image-learning consent grants for a user.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.

    Returns:
        Active consent types among the learning gate requirements.
    """
    owner_subject = build_owner_subject(user)
    granted: list[ConsentType] = []
    for consent_type in IMAGE_LEARNING_REQUIRED_CONSENTS:
        policy = get_active_policy(consent_type)
        record = await session.scalar(
            select(ConsentRecord)
            .where(
                ConsentRecord.owner_subject == owner_subject,
                ConsentRecord.consent_type == consent_type.value,
            )
            .order_by(desc(ConsentRecord.occurred_at), desc(ConsentRecord.created_at))
            .limit(1)
        )
        if record and record.granted and record.policy_version == policy.version:
            granted.append(consent_type)
    return tuple(granted)


async def maybe_store_learning_image_object(
    *,
    session: AsyncSession,
    user: AuthenticatedUser,
    analysis: SupplementAnalysisRun,
    image_bytes: bytes | None,
    image_metadata: ValidatedSupplementImage,
    settings: Settings,
    object_store: LearningImageObjectStore,
    granted_consents: tuple[ConsentType, ...],
) -> LearningImageObject | None:
    """Store a raw image object only when the learning gate passes.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        analysis: Supplement analysis row that produced the image.
        image_bytes: Validated image bytes. Required only when the gate passes.
        image_metadata: Validated image metadata.
        settings: Runtime settings.
        object_store: Learning image object store.
        granted_consents: Active user consents.

    Returns:
        Persisted learning image object, or None when the gate is closed.
    """
    decision = evaluate_image_learning_gate(settings, granted_consents)
    if not decision.allowed or image_bytes is None:
        return None
    retained_until = image_retention_deadline(settings)
    if retained_until is None:
        return None
    owner_subject_hash = hash_actor_subject(user, settings)
    existing = await session.scalar(
        select(LearningImageObject).where(
            LearningImageObject.owner_subject_hash == owner_subject_hash,
            LearningImageObject.analysis_id == analysis.id,
            LearningImageObject.image_sha256 == image_metadata.sha256,
        )
    )
    if existing is not None:
        return existing

    try:
        stored = await object_store.put_image(
            LearningImageObjectInput(
                image_bytes=image_bytes,
                image_sha256=image_metadata.sha256,
                mime_type=image_metadata.mime_type,
                owner_subject_hash=owner_subject_hash,
                retained_until=retained_until,
                metadata={
                    "image_sha256": image_metadata.sha256,
                    "analysis_id": str(analysis.id),
                    "owner_subject_hash_prefix": owner_subject_hash[:16],
                },
            )
        )
    except LearningObjectStorageError:
        return None

    record = LearningImageObject(
        owner_subject_hash=owner_subject_hash,
        analysis_id=analysis.id,
        image_sha256=image_metadata.sha256,
        object_uri=stored.object_uri,
        object_storage_provider=stored.provider,
        object_version_id=stored.version_id,
        image_mime_type=image_metadata.mime_type,
        image_size_bytes=image_metadata.size_bytes,
        retained_until=retained_until,
        status=LEARNING_IMAGE_STATUS_AWAITING_CONFIRMATION,
        consent_snapshot=_consent_snapshot(granted_consents),
    )
    session.add(record)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        await object_store.delete_image(stored.object_uri, stored.version_id)
        raise
    await session.refresh(record)
    return record


async def enqueue_learning_embedding_job_for_confirmation(
    *,
    session: AsyncSession,
    user: AuthenticatedUser,
    analysis_id: UUID | None,
    metadata_snapshot: dict[str, Any],
    settings: Settings,
    granted_consents: tuple[ConsentType, ...],
) -> ImageEmbeddingJob | None:
    """Create an embedding job after a supplement preview is confirmed.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        analysis_id: Source supplement analysis id.
        metadata_snapshot: User-confirmed structured metadata. This is only written to
            an embedding job after the manual-review gate is open.
        settings: Runtime settings.
        granted_consents: Active user consents at confirmation time.

    Returns:
        Persisted embedding job, or None when no retained image object is eligible
        or manual review is still required.
    """
    if analysis_id is None:
        return None
    decision = evaluate_image_learning_gate(settings, granted_consents)
    if not decision.allowed:
        return None
    owner_subject_hash = hash_actor_subject(user, settings)
    image_object = await session.scalar(
        select(LearningImageObject).where(
            LearningImageObject.owner_subject_hash == owner_subject_hash,
            LearningImageObject.analysis_id == analysis_id,
            LearningImageObject.status.in_(
                [LEARNING_IMAGE_STATUS_AWAITING_CONFIRMATION, LEARNING_IMAGE_STATUS_READY]
            ),
            LearningImageObject.deleted_at.is_(None),
        )
    )
    if image_object is None:
        return None

    existing = await session.scalar(
        select(ImageEmbeddingJob).where(
            ImageEmbeddingJob.image_object_id == image_object.id,
            ImageEmbeddingJob.embedding_model == settings.embedding_model,
        )
    )
    if existing is not None:
        return existing

    return await _stage_embedding_job_after_learning_filters(
        session=session,
        image_object=image_object,
        analysis_id=analysis_id,
        owner_subject_hash=owner_subject_hash,
        metadata_snapshot=metadata_snapshot,
        settings=settings,
    )


async def _stage_embedding_job_after_learning_filters(
    *,
    session: AsyncSession,
    image_object: LearningImageObject,
    analysis_id: UUID,
    owner_subject_hash: str,
    metadata_snapshot: dict[str, Any],
    settings: Settings,
) -> ImageEmbeddingJob | None:
    """Apply auto-filter/review gates and optionally enqueue an embedding job.

    Args:
        session: Request-scoped async database session.
        image_object: Retained image object selected for learning.
        analysis_id: Source supplement analysis id.
        owner_subject_hash: HMAC of the owner subject.
        metadata_snapshot: User-confirmed structured metadata.
        settings: Runtime settings.

    Returns:
        Persisted embedding job, or None when review/filter gates stop the item.
    """
    storage_decision = evaluate_learning_metadata_storage_filter(metadata_snapshot)
    if not storage_decision.allowed:
        image_object.status = LEARNING_IMAGE_STATUS_REJECTED_BY_AUTO_FILTER
        await session.commit()
        return None

    if settings.enable_learning_auto_filter:
        image_object.status = LEARNING_IMAGE_STATUS_PENDING_AUTO_FILTER
        filter_decision = evaluate_learning_metadata_auto_filter(metadata_snapshot)
        if not filter_decision.allowed:
            image_object.status = LEARNING_IMAGE_STATUS_REJECTED_BY_AUTO_FILTER
            await session.commit()
            return None

    if settings.require_learning_manual_review:
        image_object.status = LEARNING_IMAGE_STATUS_PENDING_MANUAL_REVIEW
        image_object.review_metadata_snapshot = metadata_snapshot
        await session.commit()
        return None

    return await _create_pending_embedding_job(
        session=session,
        image_object=image_object,
        analysis_id=analysis_id,
        owner_subject_hash=owner_subject_hash,
        metadata_snapshot=metadata_snapshot,
        settings=settings,
    )


async def approve_learning_image_object_after_manual_review(
    *,
    session: AsyncSession,
    image_object_id: UUID,
    settings: Settings,
) -> ImageEmbeddingJob | None:
    """Approve a manually reviewed learning image object for embedding.

    Args:
        session: Request-scoped async database session.
        image_object_id: Retained image object selected by the reviewer.
        settings: Runtime settings.

    Returns:
        Persisted embedding job, or None when the item is missing, already
        ineligible, or its stored review metadata no longer passes safety checks.
    """
    if not settings.enable_image_learning_pipeline or not settings.enable_pgvector_storage:
        return None

    image_object = await session.scalar(
        select(LearningImageObject).where(
            LearningImageObject.id == image_object_id,
            LearningImageObject.status == LEARNING_IMAGE_STATUS_PENDING_MANUAL_REVIEW,
            LearningImageObject.deleted_at.is_(None),
        )
    )
    if image_object is None:
        return None

    existing = await session.scalar(
        select(ImageEmbeddingJob).where(
            ImageEmbeddingJob.image_object_id == image_object.id,
            ImageEmbeddingJob.embedding_model == settings.embedding_model,
        )
    )
    if existing is not None:
        return existing

    metadata_snapshot = image_object.review_metadata_snapshot
    filter_decision = evaluate_learning_metadata_auto_filter(metadata_snapshot)
    if not filter_decision.allowed:
        image_object.status = LEARNING_IMAGE_STATUS_REJECTED_BY_AUTO_FILTER
        await session.commit()
        return None

    image_object.status = LEARNING_IMAGE_STATUS_APPROVED_FOR_EMBEDDING
    return await _create_pending_embedding_job(
        session=session,
        image_object=image_object,
        analysis_id=image_object.analysis_id,
        owner_subject_hash=image_object.owner_subject_hash,
        metadata_snapshot=metadata_snapshot,
        settings=settings,
    )


async def reject_learning_image_object_after_manual_review(
    *,
    session: AsyncSession,
    image_object_id: UUID,
) -> bool:
    """Reject a manually reviewed learning image object.

    Args:
        session: Request-scoped async database session.
        image_object_id: Retained image object selected by the reviewer.

    Returns:
        True when a pending review object was marked rejected.
    """
    image_object = await session.scalar(
        select(LearningImageObject).where(
            LearningImageObject.id == image_object_id,
            LearningImageObject.status == LEARNING_IMAGE_STATUS_PENDING_MANUAL_REVIEW,
            LearningImageObject.deleted_at.is_(None),
        )
    )
    if image_object is None:
        return False
    image_object.status = LEARNING_IMAGE_STATUS_REJECTED_BY_REVIEW
    await session.commit()
    return True


async def _create_pending_embedding_job(
    *,
    session: AsyncSession,
    image_object: LearningImageObject,
    analysis_id: UUID,
    owner_subject_hash: str,
    metadata_snapshot: dict[str, Any],
    settings: Settings,
) -> ImageEmbeddingJob:
    """Create a pending embedding job after automated or manual review gates.

    Args:
        session: Request-scoped async database session.
        image_object: Retained image object that passed review.
        analysis_id: Source supplement analysis id.
        owner_subject_hash: HMAC of the owner subject.
        metadata_snapshot: User-confirmed structured metadata.
        settings: Runtime settings.

    Returns:
        Persisted embedding job.
    """
    now = datetime.now(UTC)
    image_object.status = LEARNING_IMAGE_STATUS_READY
    job = ImageEmbeddingJob(
        image_object_id=image_object.id,
        analysis_id=analysis_id,
        owner_subject_hash=owner_subject_hash,
        embedding_model=settings.embedding_model,
        status=IMAGE_EMBEDDING_JOB_STATUS_PENDING,
        attempt_count=0,
        next_run_at=now,
        metadata_snapshot=metadata_snapshot,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


def evaluate_learning_metadata_storage_filter(
    metadata_snapshot: dict[str, Any],
) -> LearningMetadataAutoFilterDecision:
    """Screen metadata before storing it for manual learning review.

    Args:
        metadata_snapshot: User-confirmed structured supplement metadata.

    Returns:
        Storage-safety decision. This does not enforce ingredient signal so a
        human can review low-signal structured records, but it still blocks raw
        payload keys and PII-like strings.
    """
    if _contains_forbidden_metadata_key(metadata_snapshot):
        return LearningMetadataAutoFilterDecision(
            allowed=False,
            reason="forbidden_metadata_key",
        )
    if _contains_pii_like_text(metadata_snapshot):
        return LearningMetadataAutoFilterDecision(
            allowed=False,
            reason="pii_like_text",
        )
    return LearningMetadataAutoFilterDecision(allowed=True, reason="passed")


def evaluate_learning_metadata_auto_filter(
    metadata_snapshot: dict[str, Any],
) -> LearningMetadataAutoFilterDecision:
    """Screen confirmed metadata before learning review or embedding.

    The filter is intentionally deterministic and conservative: it rejects
    obvious raw payload keys, PII-like strings, and records without ingredient
    signal. It does not replace operator review.

    Args:
        metadata_snapshot: User-confirmed structured supplement metadata.

    Returns:
        Auto-filter decision safe to log without raw OCR text.
    """
    storage_decision = evaluate_learning_metadata_storage_filter(metadata_snapshot)
    if not storage_decision.allowed:
        return storage_decision
    ingredients = metadata_snapshot.get("ingredients")
    if not isinstance(ingredients, list) or not ingredients:
        return LearningMetadataAutoFilterDecision(
            allowed=False,
            reason="missing_ingredient_signal",
        )
    if not any(_has_ingredient_signal(item) for item in ingredients):
        return LearningMetadataAutoFilterDecision(
            allowed=False,
            reason="missing_ingredient_signal",
        )
    return LearningMetadataAutoFilterDecision(allowed=True, reason="passed")


def build_confirmed_supplement_learning_metadata(
    supplement: UserSupplement,
    ingredients: list[UserSupplementIngredient],
) -> dict[str, Any]:
    """Build sanitized metadata from a user-confirmed supplement.

    Args:
        supplement: Persisted user supplement row.
        ingredients: Persisted user supplement ingredient rows.

    Returns:
        Metadata safe for vector storage. Raw OCR text is intentionally absent.
    """
    return {
        "display_name": supplement.display_name,
        "manufacturer": supplement.manufacturer,
        "ingredient_count": len(ingredients),
        "ingredients": [
            {
                "display_name": ingredient.display_name,
                "nutrient_code": ingredient.nutrient_code,
                "amount": _decimal_to_string(ingredient.amount),
                "unit": ingredient.unit,
                "source": ingredient.source,
            }
            for ingredient in sorted(ingredients, key=lambda item: item.sort_order)
        ],
        "source_analysis_run_id": (
            str(supplement.source_analysis_run_id)
            if supplement.source_analysis_run_id is not None
            else None
        ),
        "matched_product_id": (
            str(supplement.matched_product_id)
            if supplement.matched_product_id is not None
            else None
        ),
        "user_confirmed_at": supplement.user_confirmed_at.isoformat(),
    }


async def delete_learning_artifacts_for_owner(
    *,
    session: AsyncSession,
    owner_subject_hash: str,
    object_store: LearningImageObjectStore,
) -> dict[str, int]:
    """Delete learning DB rows and retained objects for one owner.

    Args:
        session: Active database session.
        owner_subject_hash: HMAC of the owner subject.
        object_store: Object store used to delete retained images.

    Returns:
        Deleted row/object counts.
    """
    image_objects = list(
        (
            await session.scalars(
                select(LearningImageObject).where(
                    LearningImageObject.owner_subject_hash == owner_subject_hash
                )
            )
        ).all()
    )
    jobs = list(
        (
            await session.scalars(
                select(ImageEmbeddingJob).where(
                    ImageEmbeddingJob.owner_subject_hash == owner_subject_hash
                )
            )
        ).all()
    )
    records = list(
        (
            await session.scalars(
                select(ImageEmbeddingRecord).where(
                    ImageEmbeddingRecord.owner_subject_hash == owner_subject_hash
                )
            )
        ).all()
    )

    deleted_rows = 0
    deleted_objects = 0
    object_delete_failures = 0
    retained_for_retry = 0
    for job in jobs:
        await session.delete(job)
    for record in records:
        await session.delete(record)
    for image_object in image_objects:
        if image_object.deleted_at is None:
            try:
                await object_store.delete_image(
                    image_object.object_uri,
                    image_object.object_version_id,
                )
                deleted_objects += 1
            except LearningObjectStorageError:
                object_delete_failures += 1
                retained_for_retry += 1
                image_object.status = LEARNING_IMAGE_STATUS_FAILED
                continue
        await session.delete(image_object)
        deleted_rows += 1

    return {
        "learning_image_objects": deleted_rows,
        "image_embedding_jobs": len(jobs),
        "image_embedding_records": len(records),
        "learning_image_object_blobs": deleted_objects,
        "learning_image_object_delete_failures": object_delete_failures,
        "learning_image_objects_retained_for_retry": retained_for_retry,
    }


async def delete_expired_learning_image_objects(
    *,
    session: AsyncSession,
    object_store: LearningImageObjectStore,
    now: datetime | None = None,
    limit: int = 100,
) -> int:
    """Delete retained image objects past their retention deadline.

    Args:
        session: Worker-scoped async database session.
        object_store: Object storage adapter.
        now: Optional current time override.
        limit: Maximum number of objects to process.

    Returns:
        Number of objects marked deleted.
    """
    cutoff = now or datetime.now(UTC)
    image_objects = list(
        (
            await session.scalars(
                select(LearningImageObject)
                .where(
                    LearningImageObject.retained_until <= cutoff,
                    LearningImageObject.deleted_at.is_(None),
                    LearningImageObject.status != LEARNING_IMAGE_STATUS_DELETED,
                )
                .limit(limit)
            )
        ).all()
    )
    deleted = 0
    for image_object in image_objects:
        await object_store.delete_image(image_object.object_uri, image_object.object_version_id)
        image_object.status = LEARNING_IMAGE_STATUS_DELETED
        image_object.deleted_at = cutoff
        deleted += 1
    await session.commit()
    return deleted


async def retry_failed_learning_image_object_deletions(
    *,
    session: AsyncSession,
    object_store: LearningImageObjectStore,
    now: datetime | None = None,
    limit: int = 100,
) -> dict[str, int]:
    """Retry deletion for learning image objects retained after delete failures.

    Args:
        session: Worker-scoped async database session.
        object_store: Object storage adapter.
        now: Optional current time override.
        limit: Maximum failed objects to process.

    Returns:
        Sanitized retry counts.
    """
    cutoff = now or datetime.now(UTC)
    image_objects = list(
        (
            await session.scalars(
                select(LearningImageObject)
                .where(
                    LearningImageObject.status == LEARNING_IMAGE_STATUS_FAILED,
                    LearningImageObject.deleted_at.is_(None),
                )
                .limit(limit)
            )
        ).all()
    )
    deleted = 0
    failures = 0
    for image_object in image_objects:
        try:
            await object_store.delete_image(image_object.object_uri, image_object.object_version_id)
        except LearningObjectStorageError:
            failures += 1
            continue
        image_object.status = LEARNING_IMAGE_STATUS_DELETED
        image_object.deleted_at = cutoff
        await session.delete(image_object)
        deleted += 1
    await session.commit()
    return {
        "scanned": len(image_objects),
        "deleted": deleted,
        "failures": failures,
    }


def _consent_snapshot(consents: tuple[ConsentType, ...]) -> dict[str, Any]:
    """Build a policy-version snapshot for granted consent types.

    Args:
        consents: Granted consent types.

    Returns:
        Consent snapshot safe for learning metadata.
    """
    return {
        "consents": [
            {
                "type": consent.value,
                "policy_version": get_active_policy(consent).version,
            }
            for consent in consents
        ]
    }


def _decimal_to_string(value: Decimal | None) -> str | None:
    """Serialize Decimal without losing precision in JSON metadata.

    Args:
        value: Optional decimal value.

    Returns:
        String decimal representation or None.
    """
    if value is None:
        return None
    return str(value)


def _contains_forbidden_metadata_key(value: Any) -> bool:
    """Check nested metadata for raw payload, credential, or secret keys.

    Args:
        value: Candidate nested metadata value.

    Returns:
        True when a forbidden key is present.
    """
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized_key = _normalize_metadata_key(str(key))
            if normalized_key in NORMALIZED_FORBIDDEN_LEARNING_METADATA_KEYS:
                return True
            if _contains_forbidden_metadata_key(nested):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_metadata_key(item) for item in value)
    return False


def _normalize_metadata_key(key: str) -> str:
    """Normalize metadata keys before forbidden-key comparison.

    Args:
        key: Candidate metadata key.

    Returns:
        Lowercase alphanumeric key for snake/camel/kebab-case equivalence.
    """
    return "".join(character for character in key.casefold() if character.isalnum())


def _contains_pii_like_text(value: Any) -> bool:
    """Check nested metadata strings for email or phone-number-like text.

    Args:
        value: Candidate nested metadata value.

    Returns:
        True when a PII-like string is present.
    """
    if isinstance(value, str):
        return bool(PII_LIKE_TEXT_PATTERN.search(value))
    if isinstance(value, dict):
        return any(_contains_pii_like_text(nested) for nested in value.values())
    if isinstance(value, list):
        return any(_contains_pii_like_text(item) for item in value)
    return False


def _has_ingredient_signal(value: Any) -> bool:
    """Return whether an ingredient item has a stable name or nutrient code.

    Args:
        value: Ingredient metadata candidate.

    Returns:
        True when the item has a non-empty display name or nutrient code.
    """
    if not isinstance(value, dict):
        return False
    display_name = value.get("display_name")
    nutrient_code = value.get("nutrient_code")
    return bool(
        (isinstance(display_name, str) and display_name.strip())
        or (isinstance(nutrient_code, str) and nutrient_code.strip())
    )
