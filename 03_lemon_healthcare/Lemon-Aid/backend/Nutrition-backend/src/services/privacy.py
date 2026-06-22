"""Privacy, consent, deletion, and audit services."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import Request
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings
from src.db.session import get_audit_sessionmaker
from src.db.tx import persist_scope, request_manages_transaction
from src.learning.consent_gate import IMAGE_LEARNING_REQUIRED_CONSENTS
from src.learning.factory import build_learning_object_store
from src.learning.pipeline import delete_learning_artifacts_for_owner
from src.media.factory import build_media_object_store
from src.media.object_storage import MediaObjectReference, MediaObjectStorageError, MediaObjectStore
from src.models.db.analysis_result import AnalysisResult
from src.models.db.health import (
    BodyProfileSnapshot,
    HealthDailySummary,
    HealthMetricSample,
    HealthSyncBatch,
)
from src.models.db.meal import FoodImageAnalysisRun, MealFoodItem, MealRecord
from src.models.db.media import MediaObject, MediaProcessingRun, SupplementImageEvidence
from src.models.db.medical import (
    MedicalRecordCollection,
    PatientCondition,
    PatientMedication,
    PatientStatusSnapshot,
)
from src.models.db.privacy import AuditLog, ConsentRecord, DeletionRequest
from src.models.db.regulated import RegulatedDocument
from src.models.db.retraining import AnnotationTask, LearningDatasetItem
from src.models.db.supplement import (
    SupplementAnalysisRun,
    UserSupplement,
    UserSupplementIngredient,
)
from src.models.schemas.privacy import (
    ConsentActionResponse,
    ConsentStateResponse,
    ConsentStatus,
    ConsentType,
    DeletionRequestResponse,
    DeletionRequestStatus,
    DeletionRequestType,
)
from src.privacy.consent_policies import ACTIVE_CONSENT_POLICIES, get_active_policy
from src.security.auth import AuthenticatedUser
from src.security.privacy import (
    hash_actor_subject,
    request_id_from_headers,
    request_privacy_hashes,
)
from src.security.subjects import build_owner_subject

SENSITIVE_HEALTH_CONSENT = ConsentType.SENSITIVE_HEALTH_ANALYSIS
AuditOutcome = Literal["success", "failed", "not_found", "blocked"]
LEARNING_REVOCATION_CONSENTS = frozenset(IMAGE_LEARNING_REQUIRED_CONSENTS)
FORBIDDEN_AUDIT_METADATA_KEYS = {
    "authorization",
    "access_token",
    "diagnosis",
    "diagnosis_text",
    "image_base64",
    "image_bytes",
    "jwt",
    "object_ref",
    "object_uri",
    "ocr_text",
    "owner_subject",
    "public_url",
    "provider_payload",
    "provider_raw_payload",
    "raw_image",
    "raw_image_bytes",
    "raw_ocr_text",
    "raw_payload",
    "raw_provider_payload",
    "request_headers",
    "input_snapshot",
    "result_snapshot",
    "secret",
    "signed_url",
    "treatment_instruction",
    "treatment_instructions",
    "token",
}


class ConsentRequiredError(ValueError):
    """Raised when a protected operation is missing required user consent."""


def _utc_now() -> datetime:
    """Return the current UTC timestamp.

    Returns:
        Timezone-aware current datetime.
    """
    return datetime.now(UTC)


def _sanitize_event_metadata(event_metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Remove sensitive keys from audit metadata recursively.

    Args:
        event_metadata: Candidate audit metadata.

    Returns:
        Metadata dictionary with blocked keys removed.
    """
    if event_metadata is None:
        return {}
    sanitized = _sanitize_event_value(event_metadata)
    if not isinstance(sanitized, dict):
        return {}
    return sanitized


def _sanitize_event_value(value: Any) -> Any:
    """Remove sensitive keys from nested audit metadata values.

    Args:
        value: Candidate metadata value.

    Returns:
        Sanitized metadata value.
    """
    if isinstance(value, dict):
        return {
            key: _sanitize_event_value(nested_value)
            for key, nested_value in value.items()
            if isinstance(key, str) and key.lower() not in FORBIDDEN_AUDIT_METADATA_KEYS
        }
    if isinstance(value, list):
        return [_sanitize_event_value(item) for item in value]
    return value


def _audit_record_hash(
    *,
    actor_subject_hash: str,
    action: str,
    resource_type: str,
    resource_id: str | None,
    outcome: AuditOutcome,
    request_id: str | None,
    event_metadata: dict[str, Any],
    settings: Settings,
) -> str:
    """Build an HMAC over the normalized audit event payload.

    Args:
        actor_subject_hash: Hashed actor subject.
        action: Event action name.
        resource_type: Resource category.
        resource_id: Optional resource identifier.
        outcome: Event outcome.
        request_id: Optional request correlation identifier.
        event_metadata: Sanitized metadata.
        settings: Application settings containing the privacy hash secret.

    Returns:
        Hex-encoded SHA-256 HMAC for the audit payload.
    """
    payload = {
        "actor_subject_hash": actor_subject_hash,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "outcome": outcome,
        "request_id": request_id,
        "event_metadata": event_metadata,
    }
    serialized_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hmac.new(
        settings.privacy_hash_secret.get_secret_value().encode("utf-8"),
        serialized_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _build_audit_log(
    *,
    user: AuthenticatedUser,
    action: str,
    resource_type: str,
    resource_id: str | None,
    outcome: AuditOutcome,
    request: Request,
    settings: Settings,
    event_metadata: dict[str, Any] | None = None,
) -> AuditLog:
    """Build a sanitized audit log ORM object.

    Args:
        user: Authenticated actor.
        action: Event action name.
        resource_type: Resource category.
        resource_id: Optional resource identifier.
        outcome: Event outcome.
        request: Current FastAPI request.
        settings: Application settings containing the privacy hash secret.
        event_metadata: Optional sanitized metadata.

    Returns:
        Unsaved audit log ORM object.

    Raises:
        ValueError: If the authenticated subject is invalid.
    """
    actor_subject_hash = hash_actor_subject(user, settings)
    ip_hash, user_agent_hash = request_privacy_hashes(request, settings)
    request_id = request_id_from_headers(request)
    sanitized_metadata = _sanitize_event_metadata(event_metadata)
    record_hash = _audit_record_hash(
        actor_subject_hash=actor_subject_hash,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        request_id=request_id,
        event_metadata=sanitized_metadata,
        settings=settings,
    )
    return AuditLog(
        actor_subject_hash=actor_subject_hash,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        request_id=request_id,
        ip_hash=ip_hash,
        user_agent_hash=user_agent_hash,
        event_metadata=sanitized_metadata,
        record_hash=record_hash,
    )


def consent_record_to_action_response(record: ConsentRecord) -> ConsentActionResponse:
    """Convert a consent event row to an API response.

    Args:
        record: Persisted consent record.

    Returns:
        Consent action response.
    """
    return ConsentActionResponse(
        consent_type=ConsentType(record.consent_type),
        policy_version=record.policy_version,
        granted=record.granted,
        occurred_at=record.occurred_at,
    )


def deletion_request_to_response(record: DeletionRequest) -> DeletionRequestResponse:
    """Convert a deletion request row to an API response.

    Args:
        record: Persisted deletion request.

    Returns:
        Deletion request response.
    """
    return DeletionRequestResponse.model_validate(record)


async def _latest_consent_record(
    session: AsyncSession,
    user: AuthenticatedUser,
    consent_type: ConsentType,
) -> ConsentRecord | None:
    """Return the latest consent event for one user and bucket.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        consent_type: Consent bucket.

    Returns:
        Latest consent record or None.

    Raises:
        ValueError: If owner identity cannot be persisted safely.
    """
    statement = (
        select(ConsentRecord)
        .where(
            ConsentRecord.owner_subject == build_owner_subject(user),
            ConsentRecord.consent_type == consent_type.value,
        )
        .order_by(desc(ConsentRecord.occurred_at), desc(ConsentRecord.created_at))
        .limit(1)
    )
    record: ConsentRecord | None = await session.scalar(statement)
    return record


async def has_active_consent(
    session: AsyncSession,
    user: AuthenticatedUser,
    consent_type: ConsentType,
) -> bool:
    """Check whether a user granted the active policy version.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        consent_type: Consent bucket.

    Returns:
        True when the latest consent event grants the active policy version.

    Raises:
        ValueError: If owner identity cannot be persisted safely.
    """
    policy = get_active_policy(consent_type)
    record = await _latest_consent_record(session, user, consent_type)
    return bool(record and record.granted and record.policy_version == policy.version)


async def require_user_consent(
    session: AsyncSession,
    user: AuthenticatedUser,
    consent_type: ConsentType,
) -> None:
    """Fail if a protected operation is missing required consent.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        consent_type: Consent bucket.

    Raises:
        ConsentRequiredError: If the active consent policy is not granted.
        ValueError: If owner identity cannot be persisted safely.
    """
    if not await has_active_consent(session, user, consent_type):
        raise ConsentRequiredError(
            f"Consent '{consent_type.value}' is required for this operation."
        )


async def get_consent_state(
    session: AsyncSession,
    user: AuthenticatedUser,
) -> ConsentStateResponse:
    """Return current consent state for all active policies.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.

    Returns:
        Current consent state response.

    Raises:
        ValueError: If owner identity cannot be persisted safely.
    """
    statement = (
        select(ConsentRecord)
        .where(ConsentRecord.owner_subject == build_owner_subject(user))
        .order_by(desc(ConsentRecord.occurred_at), desc(ConsentRecord.created_at))
    )
    records = list((await session.scalars(statement)).all())
    latest_by_type: dict[str, ConsentRecord] = {}
    for record in records:
        latest_by_type.setdefault(record.consent_type, record)

    statuses = []
    for consent_type, policy in ACTIVE_CONSENT_POLICIES.items():
        latest_record = latest_by_type.get(consent_type.value)
        granted = bool(
            latest_record
            and latest_record.granted
            and latest_record.policy_version == policy.version
        )
        statuses.append(
            ConsentStatus(
                consent_type=consent_type,
                policy_version=policy.version,
                title=policy.title,
                required=policy.required,
                granted=granted,
                occurred_at=latest_record.occurred_at if latest_record else None,
                revoked_at=latest_record.revoked_at if latest_record else None,
            )
        )
    return ConsentStateResponse(consents=statuses)


async def grant_consent(
    session: AsyncSession,
    user: AuthenticatedUser,
    consent_type: ConsentType,
    request: Request,
    settings: Settings,
) -> ConsentRecord:
    """Persist a consent grant event and audit log.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        consent_type: Consent bucket.
        request: Current FastAPI request.
        settings: Application settings containing the privacy hash secret.

    Returns:
        Persisted consent record.

    Raises:
        ValueError: If owner identity cannot be persisted safely.
    """
    policy = get_active_policy(consent_type)
    now = _utc_now()
    ip_hash, user_agent_hash = request_privacy_hashes(request, settings)
    record = ConsentRecord(
        owner_subject=build_owner_subject(user),
        consent_type=consent_type.value,
        policy_version=policy.version,
        granted=True,
        occurred_at=now,
        revoked_at=None,
        request_id=request_id_from_headers(request),
        ip_hash=ip_hash,
        user_agent_hash=user_agent_hash,
    )
    async with persist_scope(session):
        session.add(record)
    await session.refresh(record)
    await record_audit_event(
        session,
        user,
        action="consent_granted",
        resource_type="consent",
        resource_id=consent_type.value,
        outcome="success",
        request=request,
        settings=settings,
        event_metadata={"consent_type": consent_type.value, "policy_version": policy.version},
    )
    return record


async def revoke_consent(
    session: AsyncSession,
    user: AuthenticatedUser,
    consent_type: ConsentType,
    request: Request,
    settings: Settings,
) -> ConsentRecord:
    """Persist a consent revocation event and audit log.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        consent_type: Consent bucket.
        request: Current FastAPI request.
        settings: Application settings containing the privacy hash secret.

    Returns:
        Persisted consent revocation record.

    Raises:
        ValueError: If owner identity cannot be persisted safely.
    """
    policy = get_active_policy(consent_type)
    now = _utc_now()
    ip_hash, user_agent_hash = request_privacy_hashes(request, settings)
    record = ConsentRecord(
        owner_subject=build_owner_subject(user),
        consent_type=consent_type.value,
        policy_version=policy.version,
        granted=False,
        occurred_at=now,
        revoked_at=now,
        request_id=request_id_from_headers(request),
        ip_hash=ip_hash,
        user_agent_hash=user_agent_hash,
    )
    async with persist_scope(session):
        session.add(record)
        event_metadata: dict[str, Any] = {
            "consent_type": consent_type.value,
            "policy_version": policy.version,
        }
        if consent_type in LEARNING_REVOCATION_CONSENTS:
            retraining_revoked_counts = await revoke_retraining_records_for_owner(
                session=session,
                owner_subject_hash=hash_actor_subject(user, settings),
            )
            learning_deleted_counts = await delete_learning_artifacts_for_owner(
                session=session,
                owner_subject_hash=hash_actor_subject(user, settings),
                object_store=build_learning_object_store(settings),
            )
            event_metadata["retraining_revoked_counts"] = retraining_revoked_counts
            event_metadata["learning_deleted_counts"] = learning_deleted_counts
        learning_delete_failed = bool(
            event_metadata.get("learning_deleted_counts", {}).get(
                "learning_image_object_delete_failures",
                0,
            )
        )
    await session.refresh(record)
    await record_audit_event(
        session,
        user,
        action="consent_revoked",
        resource_type="consent",
        resource_id=consent_type.value,
        outcome="failed" if learning_delete_failed else "success",
        request=request,
        settings=settings,
        event_metadata=event_metadata,
    )
    return record


async def _write_audit_out_of_band(audit_log: AuditLog) -> AuditLog:
    """Write one audit row via the privileged audit engine, in its own tx.

    Used for request-managed (FORCE RLS) sessions: the request role
    (``lemon_app``) holds only SELECT on ``audit_logs`` and audits must not ride
    the request transaction anyway, so they are committed independently through
    the privileged audit session factory (see ``get_audit_sessionmaker``). This
    matches the legacy "commit the audit immediately" behavior and keeps the
    audit even if the request transaction later rolls back.

    Args:
        audit_log: A freshly built, transient AuditLog not added to any session.

    Returns:
        The audit log after its independent commit (attributes stay loaded
        because the session factory uses ``expire_on_commit=False``).
    """
    audit_sessionmaker = get_audit_sessionmaker()
    async with audit_sessionmaker() as audit_session, audit_session.begin():
        audit_session.add(audit_log)
    return audit_log


async def record_audit_event(
    session: AsyncSession,
    user: AuthenticatedUser,
    *,
    action: str,
    resource_type: str,
    resource_id: str | None,
    outcome: AuditOutcome,
    request: Request,
    settings: Settings,
    event_metadata: dict[str, Any] | None = None,
) -> AuditLog:
    """Persist one sanitized audit event.

    Transaction-ownership aware (FORCE RLS rollout, see src/db/tx.py):

    * Request-managed sessions (``get_rls_context_session``): the request role
      cannot INSERT ``audit_logs`` and the audit must not ride the request
      transaction, so it is written via the privileged audit engine out-of-band
      (committed independently, so it survives a request-transaction rollback).
      The audit therefore commits *before* the owner-row commit at dependency
      exit — inverting the legacy order, where the service committed the row
      first; under Option A the audit is intentionally decoupled from the work it
      records, so a recorded ``success`` audit does not by itself guarantee the
      owner row is durable.
    * Legacy sessions (``get_async_session``): the request session is privileged
      (``DATABASE_URL``); persist with the historical ``add + commit``.

    Args:
        session: Request-scoped async database session.
        user: Authenticated actor.
        action: Event action name.
        resource_type: Resource category.
        resource_id: Optional resource identifier.
        outcome: Event outcome.
        request: Current FastAPI request.
        settings: Application settings containing the privacy hash secret.
        event_metadata: Optional sanitized metadata.

    Returns:
        Persisted audit log object.

    Raises:
        ValueError: If the authenticated subject is invalid.
    """
    audit_log = _build_audit_log(
        user=user,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        request=request,
        settings=settings,
        event_metadata=event_metadata,
    )
    if request_manages_transaction(session):
        return await _write_audit_out_of_band(audit_log)
    session.add(audit_log)
    await session.commit()
    return audit_log


async def record_sensitive_audit_event(
    session: AsyncSession,
    user: AuthenticatedUser,
    *,
    action: str,
    resource_type: str,
    resource_id: str | None,
    outcome: AuditOutcome,
    request: Request,
    settings: Settings,
    event_metadata: dict[str, Any] | None = None,
) -> AuditLog:
    """Persist a sanitized audit event for sensitive health data access.

    Args:
        session: Request-scoped async database session.
        user: Authenticated actor.
        action: Event action name.
        resource_type: Resource category.
        resource_id: Optional resource identifier.
        outcome: Event outcome.
        request: Current FastAPI request.
        settings: Application settings containing the privacy hash secret.
        event_metadata: Optional sanitized metadata.

    Returns:
        Persisted audit log object.

    Raises:
        ValueError: If the authenticated subject is invalid.
    """
    return await record_audit_event(
        session=session,
        user=user,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        request=request,
        settings=settings,
        event_metadata=event_metadata,
    )


async def delete_analysis_result_for_user(
    session: AsyncSession,
    user: AuthenticatedUser,
    result_id: UUID,
    request: Request,
    settings: Settings,
) -> bool:
    """Delete one analysis result owned by the current user.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        result_id: Persisted analysis result identifier.
        request: Current FastAPI request.
        settings: Application settings containing the privacy hash secret.

    Returns:
        True when a row was deleted, False when the row was not found for this owner.

    Raises:
        ValueError: If owner identity cannot be persisted safely.
    """
    owner_subject = build_owner_subject(user)
    async with persist_scope(session):
        record = await session.scalar(
            select(AnalysisResult).where(
                AnalysisResult.id == result_id,
                AnalysisResult.owner_subject == owner_subject,
            )
        )
        deleted = record is not None
        if record is not None:
            await session.delete(record)
    await record_audit_event(
        session,
        user,
        action="analysis_result_deleted",
        resource_type="analysis_result",
        resource_id=str(result_id),
        outcome="success" if deleted else "not_found",
        request=request,
        settings=settings,
    )
    return deleted


async def _scalar_records(session: AsyncSession, statement: Any) -> list[Any]:
    """Return all scalar ORM records for one select statement.

    Args:
        session: Request-scoped async database session.
        statement: SQLAlchemy select statement.

    Returns:
        Scalar ORM records returned by the statement.
    """
    return list((await session.scalars(statement)).all())


async def _records_for_ids(
    session: AsyncSession,
    statement: Any,
    ids: list[UUID],
) -> list[Any]:
    """Return linked records only when the parent id list is non-empty.

    Args:
        session: Request-scoped async database session.
        statement: SQLAlchemy select statement with an ``IN`` predicate.
        ids: Parent identifiers used to decide whether the lookup is needed.

    Returns:
        Linked ORM records or an empty list when there are no parent ids.
    """
    if not ids:
        return []
    return await _scalar_records(session, statement)


async def _delete_records(session: AsyncSession, records: list[Any]) -> None:
    """Delete ORM records in the provided order.

    Args:
        session: Request-scoped async database session.
        records: ORM records selected for delete-all cleanup.

    Returns:
        None.
    """
    for record in records:
        await session.delete(record)


async def revoke_retraining_records_for_owner(
    *,
    session: AsyncSession,
    owner_subject_hash: str,
) -> dict[str, int]:
    """Scrub user-linked retraining records for revoke/delete-all flows.

    Args:
        session: Request-scoped async database session.
        owner_subject_hash: HMAC of the authenticated owner subject.

    Returns:
        Sanitized counts of scrubbed retraining lineage records.
    """
    now = _utc_now()
    dataset_items = await _scalar_records(
        session,
        select(LearningDatasetItem).where(
            LearningDatasetItem.owner_subject_hash == owner_subject_hash
        ),
    )
    annotation_tasks = await _scalar_records(
        session,
        select(AnnotationTask).where(AnnotationTask.owner_subject_hash == owner_subject_hash),
    )
    for item in dataset_items:
        item.label_status = "revoked"
        item.media_object_id = None
        item.learning_image_object_id = None
        item.label_snapshot = {}
        item.label_hash = None
        item.quality_score = None
        item.consent_snapshot = {}
        item.retained_until = now
        item.revoked_at = now
    for task in annotation_tasks:
        task.status = "cancelled"
        task.media_object_id = None
        task.learning_image_object_id = None
        task.label_snapshot = {}
        task.review_notes_code = None
        task.reviewer_hash = None
        task.completed_at = now
    return {
        "learning_dataset_items_revoked": len(dataset_items),
        "annotation_tasks_cancelled": len(annotation_tasks),
    }


async def _medical_deletion_records_for_owner(
    session: AsyncSession,
    owner_subject_hash: str,
) -> dict[str, list[Any]]:
    """Return medical records that must be removed for delete-all.

    Args:
        session: Request-scoped async database session.
        owner_subject_hash: HMAC of the authenticated owner subject.

    Returns:
        Medical record groups keyed by sanitized deleted-count names.
    """
    medical_record_collections = await _scalar_records(
        session,
        select(MedicalRecordCollection).where(
            MedicalRecordCollection.owner_subject_hash == owner_subject_hash
        ),
    )
    medical_collection_ids = [record.id for record in medical_record_collections]
    patient_conditions = await _records_for_ids(
        session,
        select(PatientCondition).where(
            PatientCondition.medical_collection_id.in_(medical_collection_ids)
        ),
        medical_collection_ids,
    )
    patient_medications = await _records_for_ids(
        session,
        select(PatientMedication).where(
            PatientMedication.medical_collection_id.in_(medical_collection_ids)
        ),
        medical_collection_ids,
    )
    patient_status_snapshots = await _scalar_records(
        session,
        select(PatientStatusSnapshot).where(
            PatientStatusSnapshot.owner_subject_hash == owner_subject_hash
        ),
    )
    return {
        "patient_status_snapshots": patient_status_snapshots,
        "patient_conditions": patient_conditions,
        "patient_medications": patient_medications,
        "medical_record_collections": medical_record_collections,
    }


async def create_delete_all_user_data_request(
    session: AsyncSession,
    user: AuthenticatedUser,
    request: Request,
    settings: Settings,
) -> DeletionRequest:
    """Delete current-user health, supplement, analysis, and consent rows.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        request: Current FastAPI request.
        settings: Application settings containing the privacy hash secret.

    Returns:
        Persisted deletion request record with deleted row counts.

    Raises:
        ValueError: If owner identity cannot be persisted safely.
    """
    owner_subject = build_owner_subject(user)
    owner_subject_hash = hash_actor_subject(user, settings)
    now = _utc_now()
    deletion_request = DeletionRequest(
        id=uuid4(),
        owner_subject_hash=owner_subject_hash,
        request_type=DeletionRequestType.ALL_USER_DATA.value,
        status=DeletionRequestStatus.COMPLETED.value,
        requested_at=now,
        completed_at=now,
        deleted_counts={},
        failure_reason=None,
    )

    async with persist_scope(session):
        health_daily_summaries = await _scalar_records(
            session,
            select(HealthDailySummary).where(HealthDailySummary.owner_subject == owner_subject),
        )
        health_sync_batches = await _scalar_records(
            session,
            select(HealthSyncBatch).where(HealthSyncBatch.owner_subject == owner_subject),
        )
        body_profile_snapshots = await _scalar_records(
            session,
            select(BodyProfileSnapshot).where(BodyProfileSnapshot.owner_subject == owner_subject),
        )
        health_metric_samples = await _scalar_records(
            session,
            select(HealthMetricSample).where(HealthMetricSample.owner_subject == owner_subject),
        )
        supplement_analysis_runs = await _scalar_records(
            session,
            select(SupplementAnalysisRun).where(
                SupplementAnalysisRun.owner_subject == owner_subject
            ),
        )
        supplement_analysis_run_ids = [record.id for record in supplement_analysis_runs]
        supplement_image_evidence = await _records_for_ids(
            session,
            select(SupplementImageEvidence).where(
                SupplementImageEvidence.analysis_run_id.in_(supplement_analysis_run_ids)
            ),
            supplement_analysis_run_ids,
        )
        user_supplements = await _scalar_records(
            session,
            select(UserSupplement).where(UserSupplement.owner_subject == owner_subject),
        )
        user_supplement_ids = [record.id for record in user_supplements]
        user_supplement_ingredients = await _records_for_ids(
            session,
            select(UserSupplementIngredient).where(
                UserSupplementIngredient.user_supplement_id.in_(user_supplement_ids)
            ),
            user_supplement_ids,
        )
        meal_records = await _scalar_records(
            session,
            select(MealRecord).where(MealRecord.owner_subject == owner_subject),
        )
        meal_record_ids = [record.id for record in meal_records]
        meal_food_items = await _records_for_ids(
            session,
            select(MealFoodItem).where(MealFoodItem.meal_id.in_(meal_record_ids)),
            meal_record_ids,
        )
        food_image_analysis_runs = await _scalar_records(
            session,
            select(FoodImageAnalysisRun).where(FoodImageAnalysisRun.owner_subject == owner_subject),
        )
        analysis_records = await _scalar_records(
            session,
            select(AnalysisResult).where(AnalysisResult.owner_subject == owner_subject),
        )
        regulated_documents = await _scalar_records(
            session,
            select(RegulatedDocument).where(
                RegulatedDocument.owner_subject_hash == owner_subject_hash
            ),
        )
        medical_deletion_records = await _medical_deletion_records_for_owner(
            session,
            owner_subject_hash,
        )
        consent_records = await _scalar_records(
            session,
            select(ConsentRecord).where(ConsentRecord.owner_subject == owner_subject),
        )
        learning_deleted_counts = await delete_learning_artifacts_for_owner(
            session=session,
            owner_subject_hash=owner_subject_hash,
            object_store=build_learning_object_store(settings),
        )
        retraining_revoked_counts = await revoke_retraining_records_for_owner(
            session=session,
            owner_subject_hash=owner_subject_hash,
        )
        media_deleted_counts = await delete_media_artifacts_for_owner(
            session=session,
            owner_subject_hash=owner_subject_hash,
            object_store=build_media_object_store(settings),
        )

        await _delete_records(session, user_supplement_ingredients)
        await _delete_records(session, user_supplements)
        await _delete_records(session, food_image_analysis_runs)
        await _delete_records(session, meal_food_items)
        await _delete_records(session, meal_records)
        await _delete_records(session, supplement_image_evidence)
        await _delete_records(session, supplement_analysis_runs)
        await _delete_records(session, body_profile_snapshots)
        await _delete_records(session, health_metric_samples)
        await _delete_records(session, health_daily_summaries)
        await _delete_records(session, health_sync_batches)
        await _delete_records(session, analysis_records)
        for records in medical_deletion_records.values():
            await _delete_records(session, records)
        await _delete_records(session, regulated_documents)
        await _delete_records(session, consent_records)

        deletion_request.deleted_counts = {
            "analysis_results": len(analysis_records),
            "consent_records": len(consent_records),
            "health_daily_summaries": len(health_daily_summaries),
            "body_profile_snapshots": len(body_profile_snapshots),
            "health_metric_samples": len(health_metric_samples),
            "health_sync_batches": len(health_sync_batches),
            "food_image_analysis_runs": len(food_image_analysis_runs),
            "meal_food_items": len(meal_food_items),
            "meal_records": len(meal_records),
            **{
                count_name: len(records) for count_name, records in medical_deletion_records.items()
            },
            "regulated_documents": len(regulated_documents),
            "supplement_image_evidence": len(supplement_image_evidence),
            "supplement_analysis_runs": len(supplement_analysis_runs),
            "user_supplement_ingredients": len(user_supplement_ingredients),
            "user_supplements": len(user_supplements),
            **media_deleted_counts,
            **learning_deleted_counts,
            **retraining_revoked_counts,
        }
        learning_delete_failed, media_delete_failed = (
            bool(learning_deleted_counts["learning_image_object_delete_failures"]),
            bool(media_deleted_counts["media_object_delete_failures"]),
        )
        if learning_delete_failed or media_delete_failed:
            deletion_request.status = DeletionRequestStatus.FAILED.value
            deletion_request.completed_at = None
            deletion_request.failure_reason = (
                "learning_image_object_delete_failed"
                if learning_delete_failed
                else "media_object_delete_failed"
            )
        session.add(deletion_request)
        session.add(
            _build_audit_log(
                user=user,
                action="user_data_deleted",
                resource_type="user_data",
                resource_id=str(deletion_request.id),
                outcome="failed" if learning_delete_failed or media_delete_failed else "success",
                request=request,
                settings=settings,
                event_metadata={"deleted_counts": deletion_request.deleted_counts},
            )
        )
    return deletion_request


async def delete_media_artifacts_for_owner(
    *,
    session: AsyncSession,
    owner_subject_hash: str,
    object_store: MediaObjectStore,
) -> dict[str, int]:
    """Delete backend-only media references and retained objects for one user.

    Args:
        session: Request-scoped async database session.
        owner_subject_hash: HMAC of the owner subject.
        object_store: Object store used to delete retained media objects.

    Returns:
        Deleted row/object counts. Object delete failures preserve the media row
        with status=failed so a later retry can delete the private object.
    """
    media_objects = list(
        (
            await session.scalars(
                select(MediaObject).where(MediaObject.owner_subject_hash == owner_subject_hash)
            )
        ).all()
    )
    media_object_ids = [record.id for record in media_objects]
    media_processing_runs: list[MediaProcessingRun] = []
    if media_object_ids:
        media_processing_runs = list(
            (
                await session.scalars(
                    select(MediaProcessingRun).where(
                        MediaProcessingRun.media_object_id.in_(media_object_ids)
                    )
                )
            ).all()
        )

    deleted_rows = 0
    deleted_objects = 0
    object_delete_failures = 0
    retained_for_retry = 0
    for media_processing_run in media_processing_runs:
        await session.delete(media_processing_run)
    for media_object in media_objects:
        if media_object.deleted_at is None:
            try:
                await object_store.delete_object(
                    MediaObjectReference(
                        object_storage_provider=media_object.object_storage_provider,
                        object_ref=media_object.object_ref,
                        object_version_id=media_object.object_version_id,
                    )
                )
                deleted_objects += 1
            except MediaObjectStorageError:
                object_delete_failures += 1
                retained_for_retry += 1
                media_object.status = "failed"
                continue
        await session.delete(media_object)
        deleted_rows += 1

    return {
        "media_objects": deleted_rows,
        "media_processing_runs": len(media_processing_runs),
        "media_object_blobs": deleted_objects,
        "media_object_delete_failures": object_delete_failures,
        "media_objects_retained_for_retry": retained_for_retry,
    }


async def get_deletion_request(
    session: AsyncSession,
    user: AuthenticatedUser,
    deletion_request_id: UUID,
    settings: Settings,
) -> DeletionRequest | None:
    """Return a deletion request owned by the current user.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        deletion_request_id: Deletion request identifier.
        settings: Application settings containing the privacy hash secret.

    Returns:
        Deletion request row or None when not found for this owner.

    Raises:
        ValueError: If owner identity cannot be persisted safely.
    """
    statement = select(DeletionRequest).where(
        DeletionRequest.id == deletion_request_id,
        DeletionRequest.owner_subject_hash == hash_actor_subject(user, settings),
    )
    record: DeletionRequest | None = await session.scalar(statement)
    return record
