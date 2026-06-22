"""Current-user medical record and patient status services."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings
from src.db.tx import persist_scope
from src.models.db.medical import (
    MedicalRecordCollection,
    PatientCondition,
    PatientMedication,
    PatientStatusSnapshot,
)
from src.models.schemas.medical import (
    ClinicalStatus,
    MedicalRecordConfirmRequest,
    MedicalRecordCreateRequest,
    MedicalRecordListResponse,
    MedicalRecordResponse,
    MedicalRecordStatus,
    MedicationActiveStatus,
    PatientConditionResponse,
    PatientMedicationResponse,
    PatientStatusSnapshotCreate,
    PatientStatusSnapshotResponse,
)
from src.nutrition.chronic_priority import canonicalize_conditions
from src.security.auth import AuthenticatedUser
from src.security.privacy import hash_actor_subject

MAX_MEDICAL_CONTEXT_RECORDS = 50
MAX_MEDICAL_CONTEXT_CODES = 12
MEDICATION_REVIEW_KEYWORDS: dict[str, tuple[str, ...]] = {
    "anticoagulant_review": ("warfarin", "와파린", "anticoagulant", "항응고"),
    "thyroid_or_bone_binding_review": (
        "levothyroxine",
        "레보티록신",
        "thyroxine",
        "갑상선",
        "bisphosphonate",
        "비스포스포네이트",
    ),
    "metformin_b12_review": ("metformin", "메트포르민"),
    "serotonergic_review": ("maoi", "ssri", "세로토닌", "serotonin"),
    "statin_red_yeast_review": ("statin", "스타틴"),
    "oncology_or_immunosuppressant_review": ("chemo", "methotrexate", "항암", "메토트렉세이트"),
    "acetaminophen_liver_review": ("acetaminophen", "아세트아미노펜", "타이레놀"),
}


class MedicalRecordNotFoundError(ValueError):
    """Raised when a current-user medical record collection cannot be found."""


class MedicalRecordStateError(ValueError):
    """Raised when a medical record collection cannot transition as requested."""


@dataclass(frozen=True)
class MedicalContextSummary:
    """Bounded current-user medical context for safe explanation prompts.

    Attributes:
        condition_count: Number of active or unknown condition rows considered.
        canonical_condition_codes: Known condition codes matched by source-backed
            nutrition rule aliases. User-entered raw condition text is excluded.
        uncategorized_condition_count: Condition rows that did not map to a known code.
        active_medication_count: Number of active or unknown medication rows considered.
        medication_review_categories: Safe interaction-review buckets matched from
            medication names. Raw medication names and doses are excluded.
        uncategorized_medication_count: Medication rows without a known review bucket.
    """

    condition_count: int = 0
    canonical_condition_codes: tuple[str, ...] = ()
    uncategorized_condition_count: int = 0
    active_medication_count: int = 0
    medication_review_categories: tuple[str, ...] = ()
    uncategorized_medication_count: int = 0

    @property
    def available(self) -> bool:
        """Return whether any bounded medical context is available.

        Returns:
            True when at least one condition or medication row was summarized.
        """
        return self.condition_count > 0 or self.active_medication_count > 0


async def create_medical_record(
    session: AsyncSession,
    user: AuthenticatedUser,
    settings: Settings,
    request: MedicalRecordCreateRequest,
) -> tuple[MedicalRecordCollection, list[PatientCondition], list[PatientMedication]]:
    """Create a current-user medical record collection.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        settings: Application settings.
        request: Validated medical record create request.

    Returns:
        Persisted collection and child rows.

    Raises:
        ValueError: If owner identity cannot be hashed safely.
    """
    owner_hash = hash_actor_subject(user, settings)
    now = datetime.now(UTC)
    collection = MedicalRecordCollection(
        owner_subject_hash=owner_hash,
        record_type=request.record_type.value,
        source=request.source.value,
        source_document_id=request.source_document_id,
        status=(
            MedicalRecordStatus.ACTIVE.value
            if request.user_confirmed
            else MedicalRecordStatus.REQUIRES_REVIEW.value
        ),
        consent_snapshot={"consent_type": "sensitive_health_analysis"},
    )
    conditions: list[PatientCondition] = []
    medications: list[PatientMedication] = []
    async with persist_scope(session):
        session.add(collection)
        await session.flush()  # assign collection.id before building FK children

        if request.condition is not None:
            condition = PatientCondition(
                medical_collection_id=collection.id,
                condition_text=request.condition.condition_text,
                condition_code_system=request.condition.condition_code_system,
                condition_code_hash=(
                    request.condition.condition_code_hash.lower()
                    if request.condition.condition_code_hash
                    else None
                ),
                clinical_status=request.condition.clinical_status.value,
                onset_date_text=request.condition.onset_date_text,
                source=request.condition.source,
                confirmed_at=now if request.user_confirmed else None,
            )
            session.add(condition)
            conditions.append(condition)
        if request.medication is not None:
            medication = PatientMedication(
                medical_collection_id=collection.id,
                medication_name_text=request.medication.medication_name_text,
                dose_text=request.medication.dose_text,
                frequency_text=request.medication.frequency_text,
                route_text=request.medication.route_text,
                period_text=request.medication.period_text,
                active_status=request.medication.active_status.value,
                source_document_id=(
                    request.medication.source_document_id or request.source_document_id
                ),
                confirmed_at=now if request.user_confirmed else None,
            )
            session.add(medication)
            medications.append(medication)

        await session.flush()
        await session.refresh(collection)
        for row in [*conditions, *medications]:
            await session.refresh(row)
    return collection, conditions, medications


async def list_medical_records(
    session: AsyncSession,
    user: AuthenticatedUser,
    settings: Settings,
    *,
    include_archived: bool,
    limit: int,
) -> list[MedicalRecordResponse]:
    """List current-user medical record collections.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        settings: Application settings.
        include_archived: Whether archived rows should be returned.
        limit: Maximum collection rows to return.

    Returns:
        Medical record responses without owner hashes, document ids, or consent snapshots.

    Raises:
        ValueError: If owner identity cannot be hashed safely.
    """
    owner_hash = hash_actor_subject(user, settings)
    statuses = [MedicalRecordStatus.ACTIVE.value, MedicalRecordStatus.REQUIRES_REVIEW.value]
    if include_archived:
        statuses.append(MedicalRecordStatus.ARCHIVED.value)
    result = await session.scalars(
        select(MedicalRecordCollection)
        .where(
            MedicalRecordCollection.owner_subject_hash == owner_hash,
            MedicalRecordCollection.status.in_(statuses),
            MedicalRecordCollection.deleted_at.is_(None),
        )
        .order_by(desc(MedicalRecordCollection.created_at))
        .limit(limit)
    )
    collections = list(result.all())
    if not collections:
        return []
    collection_ids = [record.id for record in collections]
    conditions = await _conditions_for_collections(session, collection_ids)
    medications = await _medications_for_collections(session, collection_ids)
    return [
        medical_record_to_response(
            collection,
            [row for row in conditions if row.medical_collection_id == collection.id],
            [row for row in medications if row.medical_collection_id == collection.id],
        )
        for collection in collections
    ]


async def get_current_medical_context_summary(
    session: AsyncSession,
    user: AuthenticatedUser,
    settings: Settings,
    *,
    limit: int = MAX_MEDICAL_CONTEXT_RECORDS,
) -> MedicalContextSummary:
    """Return a bounded current-user condition and medication summary.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        settings: Application settings.
        limit: Maximum active medical collections to inspect.

    Returns:
        Current-user medical context summary without raw condition names,
        medication names, doses, owner hashes, consent snapshots, or source IDs.

    Raises:
        ValueError: If owner identity cannot be hashed safely.
    """
    owner_hash = hash_actor_subject(user, settings)
    result = await session.scalars(
        select(MedicalRecordCollection)
        .where(
            MedicalRecordCollection.owner_subject_hash == owner_hash,
            MedicalRecordCollection.status == MedicalRecordStatus.ACTIVE.value,
            MedicalRecordCollection.deleted_at.is_(None),
        )
        .order_by(desc(MedicalRecordCollection.created_at))
        .limit(limit)
    )
    collections = list(result.all())
    collection_ids = [record.id for record in collections]
    conditions = await _conditions_for_collections(session, collection_ids)
    medications = await _medications_for_collections(session, collection_ids)
    return build_medical_context_summary(conditions, medications)


def build_medical_context_summary(
    conditions: Sequence[PatientCondition],
    medications: Sequence[PatientMedication],
) -> MedicalContextSummary:
    """Build a sanitized medical-context summary from child rows.

    Args:
        conditions: Current-user condition rows.
        medications: Current-user medication rows.

    Returns:
        Bounded medical context summary that excludes raw condition and
        medication text.
    """
    active_conditions = [
        row
        for row in conditions
        if row.clinical_status in {ClinicalStatus.ACTIVE.value, ClinicalStatus.UNKNOWN.value}
    ][:MAX_MEDICAL_CONTEXT_RECORDS]
    active_medications = [
        row
        for row in medications
        if row.active_status
        in {
            MedicationActiveStatus.ACTIVE.value,
            MedicationActiveStatus.UNKNOWN.value,
        }
    ][:MAX_MEDICAL_CONTEXT_RECORDS]
    canonical_condition_codes = canonicalize_conditions(
        [row.condition_text for row in active_conditions]
    )[:MAX_MEDICAL_CONTEXT_CODES]
    medication_review_categories = _medication_review_categories(active_medications)
    return MedicalContextSummary(
        condition_count=len(active_conditions),
        canonical_condition_codes=tuple(canonical_condition_codes),
        uncategorized_condition_count=max(
            0,
            len(active_conditions) - len(canonical_condition_codes),
        ),
        active_medication_count=len(active_medications),
        medication_review_categories=medication_review_categories,
        uncategorized_medication_count=max(
            0,
            len(active_medications) - len(medication_review_categories),
        ),
    )


async def confirm_medical_record(
    session: AsyncSession,
    user: AuthenticatedUser,
    settings: Settings,
    record_id: UUID,
    request: MedicalRecordConfirmRequest,
) -> MedicalRecordResponse:
    """Confirm a current-user medical record collection.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        settings: Application settings.
        record_id: Medical record collection id.
        request: Confirmation request.

    Returns:
        Confirmed medical record response.

    Raises:
        MedicalRecordNotFoundError: If the record is not owned by the current user.
        MedicalRecordStateError: If the record is deleted.
        ValueError: If owner identity cannot be hashed safely.
    """
    owner_hash = hash_actor_subject(user, settings)
    collection = await session.scalar(
        select(MedicalRecordCollection).where(
            MedicalRecordCollection.id == record_id,
            MedicalRecordCollection.owner_subject_hash == owner_hash,
            MedicalRecordCollection.deleted_at.is_(None),
        )
    )
    if collection is None:
        raise MedicalRecordNotFoundError("medical record was not found.")
    if collection.status == MedicalRecordStatus.DELETED.value:
        raise MedicalRecordStateError("deleted medical records cannot be confirmed.")

    now = datetime.now(UTC)
    collection.status = request.status.value
    conditions = await _conditions_for_collections(session, [collection.id])
    medications = await _medications_for_collections(session, [collection.id])
    for row in [*conditions, *medications]:
        if row.confirmed_at is None:
            row.confirmed_at = now
    async with persist_scope(session):
        await session.flush()
        await session.refresh(collection)
        for row in [*conditions, *medications]:
            await session.refresh(row)
    return medical_record_to_response(collection, conditions, medications)


async def create_patient_status_snapshot(
    session: AsyncSession,
    user: AuthenticatedUser,
    settings: Settings,
    request: PatientStatusSnapshotCreate,
) -> PatientStatusSnapshot:
    """Create a non-diagnostic current-user patient status snapshot.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        settings: Application settings.
        request: Validated status snapshot payload.

    Returns:
        Persisted patient status snapshot.

    Raises:
        ValueError: If owner identity cannot be hashed safely.
    """
    now = datetime.now(UTC)
    status_at = request.status_at or now
    snapshot = PatientStatusSnapshot(
        owner_subject_hash=hash_actor_subject(user, settings),
        status_at=status_at,
        summary_type=request.summary_type.value,
        input_window_start=request.input_window_start,
        input_window_end=request.input_window_end,
        symptom_categories=request.symptom_categories,
        metric_summary=dict(request.metric_summary),
        medication_summary=dict(request.medication_summary),
        risk_flags=request.risk_flags,
        data_quality=request.data_quality.value,
        generated_by=request.generated_by.value,
        expires_at=request.expires_at or status_at + timedelta(hours=24),
    )
    async with persist_scope(session):
        session.add(snapshot)
        await session.flush()
        await session.refresh(snapshot)
    return snapshot


async def get_latest_patient_status_snapshot(
    session: AsyncSession,
    user: AuthenticatedUser,
    settings: Settings,
) -> PatientStatusSnapshotResponse:
    """Return the latest current-user non-diagnostic patient status snapshot.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        settings: Application settings.

    Returns:
        Latest status snapshot response, or a not-ready synthetic response.

    Raises:
        ValueError: If owner identity cannot be hashed safely.
    """
    now = datetime.now(UTC)
    record = await session.scalar(
        select(PatientStatusSnapshot)
        .where(
            PatientStatusSnapshot.owner_subject_hash == hash_actor_subject(user, settings),
            PatientStatusSnapshot.expires_at > now,
        )
        .order_by(desc(PatientStatusSnapshot.status_at), desc(PatientStatusSnapshot.created_at))
        .limit(1)
    )
    if record is None:
        return PatientStatusSnapshotResponse(
            status="not_ready",
            status_at=now,
            summary_type="system_derived",
            risk_flags=["data_insufficient"],
            data_quality="insufficient",
            generated_by="backend_rule",
            expires_at=now + timedelta(hours=1),
        )
    return patient_status_to_response(record)


def medical_record_to_response(
    collection: MedicalRecordCollection,
    conditions: Sequence[PatientCondition],
    medications: Sequence[PatientMedication],
) -> MedicalRecordResponse:
    """Convert a medical collection and child rows into an API response.

    Args:
        collection: Medical record collection row.
        conditions: Child condition rows.
        medications: Child medication rows.

    Returns:
        API response without owner hash, consent snapshot, source document id, or code hash.
    """
    return MedicalRecordResponse(
        id=collection.id,
        record_type=collection.record_type,
        source=collection.source,
        status=collection.status,
        conditions=[PatientConditionResponse.model_validate(row) for row in conditions],
        medications=[PatientMedicationResponse.model_validate(row) for row in medications],
        created_at=collection.created_at,
        updated_at=collection.updated_at,
    )


def medical_records_to_response(records: list[MedicalRecordResponse]) -> MedicalRecordListResponse:
    """Build a list response for medical records.

    Args:
        records: Medical record responses.

    Returns:
        List response.
    """
    return MedicalRecordListResponse(records=records)


def _medication_review_categories(
    medications: Sequence[PatientMedication],
) -> tuple[str, ...]:
    """Return safe medication-review categories from medication rows.

    Args:
        medications: Active medication rows.

    Returns:
        Deduplicated review category codes. Raw medication names are not returned.
    """
    categories: list[str] = []
    seen: set[str] = set()
    for medication in medications:
        category = _medication_review_category(medication.medication_name_text)
        if category is None or category in seen:
            continue
        categories.append(category)
        seen.add(category)
        if len(categories) >= MAX_MEDICAL_CONTEXT_CODES:
            break
    return tuple(categories)


def _medication_review_category(medication_name: str) -> str | None:
    """Map a medication name to a non-identifying review bucket.

    Args:
        medication_name: User-confirmed medication name.

    Returns:
        Safe review category code, or None when no known bucket matches.
    """
    normalized = medication_name.strip().casefold()
    if not normalized:
        return None
    for category, keywords in MEDICATION_REVIEW_KEYWORDS.items():
        if any(keyword.casefold() in normalized for keyword in keywords):
            return category
    return None


def patient_status_to_response(record: PatientStatusSnapshot) -> PatientStatusSnapshotResponse:
    """Convert a patient status snapshot row into an API response.

    Args:
        record: Patient status snapshot row.

    Returns:
        API response without owner hash and without diagnostic/raw fields.
    """
    return PatientStatusSnapshotResponse(
        id=record.id,
        status="ready",
        status_at=record.status_at,
        summary_type=record.summary_type,
        input_window_start=record.input_window_start,
        input_window_end=record.input_window_end,
        symptom_categories=record.symptom_categories,
        metric_summary=record.metric_summary,
        medication_summary=record.medication_summary,
        risk_flags=record.risk_flags,
        data_quality=record.data_quality,
        generated_by=record.generated_by,
        expires_at=record.expires_at,
    )


async def _conditions_for_collections(
    session: AsyncSession,
    collection_ids: Sequence[UUID],
) -> list[PatientCondition]:
    """Load condition rows for parent medical collections.

    Args:
        session: Request-scoped async database session.
        collection_ids: Parent collection ids.

    Returns:
        Child condition rows.
    """
    if not collection_ids:
        return []
    result = await session.scalars(
        select(PatientCondition).where(PatientCondition.medical_collection_id.in_(collection_ids))
    )
    return list(result.all())


async def _medications_for_collections(
    session: AsyncSession,
    collection_ids: Sequence[UUID],
) -> list[PatientMedication]:
    """Load medication rows for parent medical collections.

    Args:
        session: Request-scoped async database session.
        collection_ids: Parent collection ids.

    Returns:
        Child medication rows.
    """
    if not collection_ids:
        return []
    result = await session.scalars(
        select(PatientMedication).where(PatientMedication.medical_collection_id.in_(collection_ids))
    )
    return list(result.all())
