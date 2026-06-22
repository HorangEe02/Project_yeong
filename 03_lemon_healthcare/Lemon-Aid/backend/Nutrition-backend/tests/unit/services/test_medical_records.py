"""Medical record and patient status service tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.config import Settings
from src.db.tx import REQUEST_MANAGED_TX
from src.models.db.medical import (
    MedicalRecordCollection,
    PatientCondition,
    PatientMedication,
    PatientStatusSnapshot,
)
from src.models.schemas.medical import (
    MedicalRecordConfirmRequest,
    MedicalRecordCreateRequest,
    PatientConditionInput,
    PatientStatusSnapshotCreate,
)
from src.security.auth import AuthenticatedUser
from src.security.privacy import hash_actor_subject
from src.services.medical_records import (
    build_medical_context_summary,
    confirm_medical_record,
    create_medical_record,
    create_patient_status_snapshot,
    get_latest_patient_status_snapshot,
    medical_record_to_response,
    patient_status_to_response,
)


class _FakeScalarResult:
    """Fake SQLAlchemy scalar result for service tests."""

    def __init__(self, rows: list[object]) -> None:
        """Initialize fake rows.

        Args:
            rows: Rows returned by `all`.
        """
        self._rows = rows

    def all(self) -> list[object]:
        """Return rows.

        Returns:
            Stored fake rows.
        """
        return self._rows


class _FakeSession:
    """Fake async session for medical service tests."""

    def __init__(
        self,
        *,
        scalar_rows: list[object | None] | None = None,
        request_managed: bool = False,
    ) -> None:
        """Initialize fake session.

        Args:
            scalar_rows: Ordered scalar return values.
            request_managed: When True, stamp the marker so ``persist_scope``
                participates (flush only) instead of owning the transaction.
        """
        self.scalar_rows = list(scalar_rows or [])
        self.added: list[object] = []
        self.refreshed: list[object] = []
        self.commits = 0
        # A real AsyncSession always exposes ``.info``; persist_scope reads it.
        self.info: dict[str, object] = {REQUEST_MANAGED_TX: True} if request_managed else {}

    async def scalar(self, _statement: object) -> object | None:
        """Return next scalar value.

        Args:
            _statement: SQLAlchemy statement ignored by the fake.

        Returns:
            Next scalar value or None.
        """
        if not self.scalar_rows:
            return None
        return self.scalar_rows.pop(0)

    async def scalars(self, _statement: object) -> _FakeScalarResult:
        """Return empty scalar result.

        Args:
            _statement: SQLAlchemy statement ignored by the fake.

        Returns:
            Empty fake scalar result.
        """
        return _FakeScalarResult([])

    def add(self, record: object) -> None:
        """Capture added row.

        Args:
            record: ORM row.
        """
        self.added.append(record)

    async def flush(self) -> None:
        """Populate parent id after fake insert."""
        for record in self.added:
            if getattr(record, "id", None) is None:
                record.id = uuid4()

    async def commit(self) -> None:
        """Count commits (own-mode must commit exactly once)."""
        self.commits += 1

    async def rollback(self) -> None:
        """No-op rollback (own-mode rolls back on exception)."""

    async def refresh(self, record: object) -> None:
        """Populate generated timestamps.

        Args:
            record: ORM row.
        """
        if getattr(record, "created_at", None) is None:
            record.created_at = datetime.now(UTC)
        if getattr(record, "updated_at", None) is None:
            record.updated_at = datetime.now(UTC)
        self.refreshed.append(record)


def _settings() -> Settings:
    """Return test settings.

    Returns:
        Development settings instance with the default privacy hash fixture.
    """
    return Settings()


def _user() -> AuthenticatedUser:
    """Return authenticated user fixture.

    Returns:
        Authenticated user.
    """
    return AuthenticatedUser(
        subject="user-1",
        issuer="https://auth.example.com/",
        claims={"sub": "user-1"},
    )


@pytest.mark.asyncio
async def test_create_medical_record_hashes_owner_and_hides_internal_fields() -> None:
    """Verify medical records store hashed owner keys and responses hide internals."""
    fake_session = _FakeSession()
    request = MedicalRecordCreateRequest(
        record_type="condition",
        condition=PatientConditionInput(
            condition_text="사용자 확인 질환명",
            clinical_status="active",
        ),
        user_confirmed=True,
    )

    collection, conditions, medications = await create_medical_record(
        cast(AsyncSession, fake_session),
        _user(),
        _settings(),
        request,
    )
    response = medical_record_to_response(collection, conditions, medications)

    assert collection.owner_subject_hash == hash_actor_subject(_user(), _settings())
    assert collection.owner_subject_hash != "https://auth.example.com/::user-1"
    assert collection.status == "active"
    assert conditions[0].confirmed_at is not None
    assert medications == []
    serialized = response.model_dump(mode="json")
    assert "owner_subject_hash" not in serialized
    assert "condition_code_hash" not in serialized
    assert "source_document_id" not in serialized
    assert "consent_snapshot" not in serialized


def test_patient_status_response_is_non_diagnostic_and_hides_owner() -> None:
    """Verify patient status responses contain codes only and hide owner hash."""
    now = datetime(2026, 5, 27, 10, 0, tzinfo=UTC)
    record = PatientStatusSnapshot(
        id=uuid4(),
        owner_subject_hash="a" * 64,
        status_at=now,
        summary_type="system_derived",
        symptom_categories=["sleep"],
        metric_summary={"steps_days_present": 3},
        medication_summary={"active_count": 2},
        risk_flags=["data_insufficient"],
        data_quality="partial",
        generated_by="backend_rule",
        expires_at=now + timedelta(hours=24),
    )

    response = patient_status_to_response(record)

    serialized = response.model_dump(mode="json")
    assert serialized["status"] == "ready"
    assert "owner_subject_hash" not in serialized
    assert "diagnosis" not in str(serialized)
    assert "treatment_instruction" not in str(serialized)


def test_patient_status_create_rejects_diagnostic_summary_keys() -> None:
    """Verify patient status snapshots reject diagnostic or raw summary keys."""
    with pytest.raises(ValueError):
        PatientStatusSnapshotCreate(metric_summary={"diagnosis": "not allowed"})


@pytest.mark.asyncio
async def test_latest_patient_status_returns_not_ready_when_absent() -> None:
    """Verify missing patient status yields a non-persisted not-ready response."""
    response = await get_latest_patient_status_snapshot(
        cast(AsyncSession, _FakeSession(scalar_rows=[None])),
        _user(),
        _settings(),
    )

    serialized = response.model_dump(mode="json")
    assert serialized["status"] == "not_ready"
    assert serialized["data_quality"] == "insufficient"
    assert serialized["risk_flags"] == ["data_insufficient"]
    assert serialized["id"] is None


def test_medical_response_hides_code_hash() -> None:
    """Verify condition code hashes stay internal."""
    collection = MedicalRecordCollection(
        id=uuid4(),
        owner_subject_hash="a" * 64,
        record_type="condition",
        source="user_manual",
        status="active",
        consent_snapshot={"consent_type": "sensitive_health_analysis"},
    )
    condition = PatientCondition(
        id=uuid4(),
        medical_collection_id=collection.id,
        condition_text="사용자 확인 질환명",
        condition_code_hash="b" * 64,
        clinical_status="active",
        source="user_confirmed",
    )

    response = medical_record_to_response(collection, [condition], [])

    serialized = response.model_dump(mode="json")
    assert "condition_code_hash" not in serialized


def test_medical_context_summary_uses_buckets_without_raw_text() -> None:
    """Verify supplement explanations receive only bounded medical buckets."""
    collection_id = uuid4()
    conditions = [
        PatientCondition(
            id=uuid4(),
            medical_collection_id=collection_id,
            condition_text="high blood pressure",
            clinical_status="active",
            source="user_confirmed",
        ),
        PatientCondition(
            id=uuid4(),
            medical_collection_id=collection_id,
            condition_text="사용자 확인 질환명",
            clinical_status="inactive",
            source="user_confirmed",
        ),
    ]
    medications = [
        PatientMedication(
            id=uuid4(),
            medical_collection_id=collection_id,
            medication_name_text="Warfarin 5 mg",
            active_status="active",
        ),
        PatientMedication(
            id=uuid4(),
            medical_collection_id=collection_id,
            medication_name_text="Stopped medication",
            active_status="stopped",
        ),
    ]

    summary = build_medical_context_summary(conditions, medications)

    serialized = str(summary)
    assert summary.available is True
    assert summary.condition_count == 1
    assert summary.canonical_condition_codes == ("hypertension",)
    assert summary.active_medication_count == 1
    assert summary.medication_review_categories == ("anticoagulant_review",)
    assert "Warfarin" not in serialized
    assert "high blood pressure" not in serialized
    assert "사용자 확인 질환명" not in serialized


# --- persist_scope transaction-ownership contract (ambient-tx Step 5) ----------
#
# Under the request-managed (RLS) session the medical-record write services must
# PARTICIPATE (flush only, never commit) so the transaction-local owner GUCs
# survive to the dependency's commit-on-exit; under a legacy session they must
# OWN the transaction (commit exactly once), reproducing today's add+commit.


def _create_request() -> MedicalRecordCreateRequest:
    """Return a minimal user-confirmed medical record create request."""
    return MedicalRecordCreateRequest(
        record_type="condition",
        condition=PatientConditionInput(
            condition_text="사용자 확인 질환명",
            clinical_status="active",
        ),
        user_confirmed=True,
    )


def _existing_collection() -> MedicalRecordCollection:
    """Return a persisted (owner-matched, non-deleted) collection for confirm tests."""
    collection = MedicalRecordCollection(
        owner_subject_hash=hash_actor_subject(_user(), _settings()),
        record_type="condition",
        source="user_manual",
        source_document_id=None,
        status="requires_review",
        consent_snapshot={"consent_type": "sensitive_health_analysis"},
    )
    collection.id = uuid4()
    collection.created_at = datetime.now(UTC)
    collection.updated_at = datetime.now(UTC)
    return collection


@pytest.mark.asyncio
async def test_create_medical_record_participates_without_commit_when_request_managed() -> None:
    session = _FakeSession(request_managed=True)
    collection, _conditions, _medications = await create_medical_record(
        cast(AsyncSession, session), _user(), _settings(), _create_request()
    )
    assert session.commits == 0  # GUCs must survive to the dependency commit
    assert collection.id is not None


@pytest.mark.asyncio
async def test_create_medical_record_commits_once_in_legacy_own_mode() -> None:
    session = _FakeSession(request_managed=False)
    await create_medical_record(
        cast(AsyncSession, session), _user(), _settings(), _create_request()
    )
    assert session.commits == 1


@pytest.mark.asyncio
async def test_confirm_medical_record_participates_without_commit_when_request_managed() -> None:
    session = _FakeSession(request_managed=True, scalar_rows=[_existing_collection()])
    await confirm_medical_record(
        cast(AsyncSession, session),
        _user(),
        _settings(),
        uuid4(),
        MedicalRecordConfirmRequest(),
    )
    assert session.commits == 0


@pytest.mark.asyncio
async def test_confirm_medical_record_commits_once_in_legacy_own_mode() -> None:
    session = _FakeSession(request_managed=False, scalar_rows=[_existing_collection()])
    await confirm_medical_record(
        cast(AsyncSession, session),
        _user(),
        _settings(),
        uuid4(),
        MedicalRecordConfirmRequest(),
    )
    assert session.commits == 1


@pytest.mark.asyncio
async def test_create_patient_status_participates_without_commit_when_request_managed() -> None:
    session = _FakeSession(request_managed=True)
    snapshot = await create_patient_status_snapshot(
        cast(AsyncSession, session), _user(), _settings(), PatientStatusSnapshotCreate()
    )
    assert session.commits == 0
    assert snapshot.id is not None


@pytest.mark.asyncio
async def test_create_patient_status_commits_once_in_legacy_own_mode() -> None:
    session = _FakeSession(request_managed=False)
    await create_patient_status_snapshot(
        cast(AsyncSession, session), _user(), _settings(), PatientStatusSnapshotCreate()
    )
    assert session.commits == 1
