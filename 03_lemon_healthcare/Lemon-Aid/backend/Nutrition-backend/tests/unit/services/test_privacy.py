"""Privacy service tests."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import TracebackType
from typing import cast
from uuid import uuid4

import pytest
from fastapi import Request
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession
from src.config import Settings
from src.db.tx import REQUEST_MANAGED_TX
from src.learning.object_storage import LearningObjectStorageError
from src.media.object_storage import MediaObjectReference, MediaObjectStorageError
from src.models.db.analysis_result import AnalysisResult
from src.models.db.health import (
    BodyProfileSnapshot,
    HealthDailySummary,
    HealthMetricSample,
    HealthSyncBatch,
)
from src.models.db.learning import ImageEmbeddingJob, ImageEmbeddingRecord, LearningImageObject
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
from src.models.schemas.privacy import ConsentType
from src.privacy.consent_policies import ACTIVE_CONSENT_POLICIES
from src.security.auth import AuthenticatedUser
from src.services.privacy import (
    create_delete_all_user_data_request,
    delete_analysis_result_for_user,
    grant_consent,
    record_audit_event,
    revoke_consent,
)


class _FakeAuditSession:
    """Fake async session that captures audit writes."""

    def __init__(self) -> None:
        self.added: list[object] = []
        self.committed = False
        self.info: dict[str, object] = {}

    def add(self, record: object) -> None:
        """Capture a persisted object.

        Args:
            record: ORM object passed by the service.

        Returns:
            None.
        """
        self.added.append(record)

    async def commit(self) -> None:
        """Record a fake commit.

        Returns:
            None.
        """
        self.committed = True


class _FakeScalarResult:
    """Fake SQLAlchemy scalar result for predefined records."""

    def __init__(self, records: list[object]) -> None:
        self._records = records

    def all(self) -> list[object]:
        """Return captured records.

        Returns:
            Predefined scalar records.
        """
        return self._records


class _FakeTransaction:
    """Fake async transaction context manager."""

    async def __aenter__(self) -> None:
        """Enter the fake transaction.

        Returns:
            None.
        """

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        """Exit the fake transaction.

        Args:
            exc_type: Exception type when the block failed.
            exc: Exception instance when the block failed.
            traceback: Exception traceback when the block failed.

        Returns:
            False so exceptions propagate.
        """
        return False


class _FakeDeletionSession:
    """Fake async session that serves model-specific query results."""

    def __init__(
        self,
        records_by_model: dict[type[object], list[object]],
        *,
        request_managed: bool = False,
    ) -> None:
        self._records_by_model = records_by_model
        self.deleted: list[object] = []
        self.added: list[object] = []
        self.commits = 0
        # A real AsyncSession always exposes ``.info``; persist_scope reads it.
        self.info: dict[str, object] = {REQUEST_MANAGED_TX: True} if request_managed else {}

    async def flush(self) -> None:
        """No-op flush (persist_scope flushes pending writes)."""

    async def commit(self) -> None:
        """Count commits (persist_scope own-mode must commit exactly once)."""
        self.commits += 1

    async def rollback(self) -> None:
        """No-op rollback (persist_scope own-mode rolls back on exception)."""

    def begin(self) -> _FakeTransaction:
        """Return a fake transaction context manager.

        Returns:
            Fake async transaction.
        """
        return _FakeTransaction()

    async def scalars(self, statement: object) -> _FakeScalarResult:
        """Return records keyed by the selected ORM entity.

        Args:
            statement: SQLAlchemy select statement.

        Returns:
            Fake scalar result for the selected model.
        """
        column_descriptions = getattr(statement, "column_descriptions", [])
        model = column_descriptions[0].get("entity") if column_descriptions else None
        if not isinstance(model, type):
            return _FakeScalarResult([])
        return _FakeScalarResult(self._records_by_model.get(model, []))

    async def scalar(self, statement: object) -> object | None:
        """Return the first configured record for the selected ORM entity, or None.

        Args:
            statement: SQLAlchemy select statement.

        Returns:
            First configured record for the model, or None when none is configured.
        """
        column_descriptions = getattr(statement, "column_descriptions", [])
        model = column_descriptions[0].get("entity") if column_descriptions else None
        if not isinstance(model, type):
            return None
        records = self._records_by_model.get(model, [])
        return records[0] if records else None

    async def delete(self, record: object) -> None:
        """Capture a deleted object.

        Args:
            record: ORM object passed by the service.

        Returns:
            None.
        """
        self.deleted.append(record)

    def add(self, record: object) -> None:
        """Capture a persisted object.

        Args:
            record: ORM object passed by the service.

        Returns:
            None.
        """
        self.added.append(record)

    async def refresh(self, _record: object) -> None:
        """No-op refresh for fake ORM records.

        Args:
            _record: ORM object refreshed by the service.

        Returns:
            None.
        """


class _FakeLearningObjectStore:
    """Fake learning object store that records deletes."""

    def __init__(self, *, fail: bool = False) -> None:
        """Initialize captured object deletes.

        Args:
            fail: Whether delete_image should raise a storage error.
        """
        self.fail = fail
        self.deleted: list[tuple[str, str | None]] = []

    async def delete_image(self, object_uri: str, version_id: str | None = None) -> None:
        """Capture a private object deletion request.

        Args:
            object_uri: Private object URI.
            version_id: Optional object version.

        Returns:
            None.

        Raises:
            LearningObjectStorageError: When fail=True.
        """
        if self.fail:
            raise LearningObjectStorageError("sensitive object URI should not be printed")
        self.deleted.append((object_uri, version_id))


class _FakeMediaObjectStore:
    """Fake media object store that records deletes."""

    def __init__(self, *, fail: bool = False) -> None:
        """Initialize captured media object deletes.

        Args:
            fail: Whether delete_object should raise a storage error.
        """
        self.fail = fail
        self.deleted: list[MediaObjectReference] = []

    async def delete_object(self, reference: MediaObjectReference) -> None:
        """Capture a private media object deletion request.

        Args:
            reference: Private media object reference.

        Returns:
            None.

        Raises:
            MediaObjectStorageError: When fail=True.
        """
        if self.fail:
            raise MediaObjectStorageError("sensitive object ref should not be printed")
        self.deleted.append(reference)


def _request() -> Request:
    """Return a request fixture with auditable metadata.

    Returns:
        Starlette request object.
    """
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/analysis-results/activity-score",
            "headers": [
                (b"user-agent", b"raw-test-agent"),
                (b"x-request-id", b"req-123"),
            ],
            "client": ("203.0.113.10", 12345),
        }
    )


def _user() -> AuthenticatedUser:
    """Return an authenticated user fixture.

    Returns:
        Authenticated user model.
    """
    return AuthenticatedUser(
        subject="user_123",
        issuer="https://auth.example.com/",
        claims={"sub": "user_123"},
    )


def test_external_ocr_processing_policy_is_active() -> None:
    """Verify Google Vision OCR has a separate active consent bucket."""
    policy = ACTIVE_CONSENT_POLICIES[ConsentType.EXTERNAL_OCR_PROCESSING]

    assert policy.consent_type == ConsentType.EXTERNAL_OCR_PROCESSING
    assert policy.version == "2026-05-15"
    assert policy.required is False
    assert len(policy.content_hash) == 64


def test_raw_ocr_text_retention_policy_is_active_and_optional() -> None:
    """Verify the dedicated OCR-source-retention consent is an optional opt-in."""
    policy = ACTIVE_CONSENT_POLICIES[ConsentType.RAW_OCR_TEXT_RETENTION]

    assert policy.consent_type == ConsentType.RAW_OCR_TEXT_RETENTION
    assert policy.required is False
    assert len(policy.content_hash) == 64


@pytest.mark.asyncio
async def test_revoke_image_learning_consent_deletes_learning_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify learning opt-out deletes retained image and vector artifacts."""
    now = datetime.now(UTC)
    analysis_id = uuid4()
    image_object = LearningImageObject(
        id=uuid4(),
        owner_subject_hash="a" * 64,
        analysis_id=analysis_id,
        image_sha256="b" * 64,
        object_uri="s3://learning-images/private/object.png",
        object_storage_provider="supabase_s3",
        object_version_id="version-1",
        image_mime_type="image/png",
        image_size_bytes=1024,
        retained_until=now + timedelta(days=30),
        status="ready",
        consent_snapshot={"consents": []},
    )
    embedding_job = ImageEmbeddingJob(
        id=uuid4(),
        image_object_id=image_object.id,
        analysis_id=analysis_id,
        owner_subject_hash="a" * 64,
        embedding_model="clip-test",
        status="pending",
        attempt_count=0,
        next_run_at=now,
        metadata_snapshot={"display_name": "Vitamin C"},
    )
    embedding_record = ImageEmbeddingRecord(
        id=uuid4(),
        owner_subject_hash="a" * 64,
        analysis_id=analysis_id,
        image_object_id=image_object.id,
        image_sha256=image_object.image_sha256,
        embedding_model="clip-test",
        embedding_dimensions=3,
        embedding=(0.1, 0.2, 0.3),
        embedding_metadata={"display_name": "Vitamin C"},
    )
    dataset_item = LearningDatasetItem(
        id=uuid4(),
        dataset_version_id=uuid4(),
        owner_subject_hash="a" * 64,
        learning_image_object_id=image_object.id,
        source_domain="supplement",
        task_type="paddleocr_recognition",
        label_status="human_reviewed",
        split="train",
        label_snapshot={"text_label": "confirmed label"},
        label_hash="c" * 64,
        quality_score=Decimal("0.9000"),
        consent_snapshot={"consents": ["image_learning_dataset"]},
        retained_until=now + timedelta(days=30),
    )
    annotation_task = AnnotationTask(
        id=uuid4(),
        owner_subject_hash="a" * 64,
        task_type="ocr_textline_label",
        status="accepted",
        assignee_role="data_reviewer",
        label_snapshot={"text_label": "confirmed label"},
        review_notes_code="accepted",
        reviewer_hash="d" * 64,
        completed_at=now,
    )
    fake_session = _FakeDeletionSession(
        {
            ImageEmbeddingJob: [embedding_job],
            ImageEmbeddingRecord: [embedding_record],
            LearningImageObject: [image_object],
            LearningDatasetItem: [dataset_item],
            AnnotationTask: [annotation_task],
        }
    )
    fake_store = _FakeLearningObjectStore()
    monkeypatch.setattr(
        "src.services.privacy.build_learning_object_store",
        lambda _settings: fake_store,
    )
    settings = Settings(privacy_hash_secret=SecretStr("test-privacy-secret"))

    consent_record = await revoke_consent(
        cast(AsyncSession, fake_session),
        _user(),
        ConsentType.IMAGE_LEARNING_DATASET,
        _request(),
        settings,
    )

    assert consent_record.granted is False
    assert fake_store.deleted == [(image_object.object_uri, image_object.object_version_id)]
    assert fake_session.deleted == [embedding_job, embedding_record, image_object]
    assert dataset_item.label_status == "revoked"
    assert dataset_item.learning_image_object_id is None
    assert dataset_item.label_snapshot == {}
    assert dataset_item.label_hash is None
    assert dataset_item.consent_snapshot == {}
    assert dataset_item.revoked_at is not None
    assert annotation_task.status == "cancelled"
    assert annotation_task.label_snapshot == {}
    assert annotation_task.review_notes_code is None
    assert annotation_task.reviewer_hash is None
    audit_log = fake_session.added[1]
    assert isinstance(audit_log, AuditLog)
    assert audit_log.event_metadata["learning_deleted_counts"] == {
        "learning_image_objects": 1,
        "image_embedding_jobs": 1,
        "image_embedding_records": 1,
        "learning_image_object_blobs": 1,
        "learning_image_object_delete_failures": 0,
        "learning_image_objects_retained_for_retry": 0,
    }
    assert audit_log.event_metadata["retraining_revoked_counts"] == {
        "learning_dataset_items_revoked": 1,
        "annotation_tasks_cancelled": 1,
    }
    serialized_metadata = str(audit_log.event_metadata)
    assert image_object.object_uri not in serialized_metadata
    assert "owner_subject_hash" not in serialized_metadata


@pytest.mark.asyncio
async def test_record_audit_event_sanitizes_sensitive_metadata() -> None:
    """Verify audit logs exclude raw snapshots and store hashed request metadata."""
    fake_session = _FakeAuditSession()
    settings = Settings(privacy_hash_secret=SecretStr("test-privacy-secret"))

    audit_log = await record_audit_event(
        cast(AsyncSession, fake_session),
        _user(),
        action="analysis_result_created",
        resource_type="analysis_result",
        resource_id="result-123",
        outcome="success",
        request=_request(),
        settings=settings,
        event_metadata={
            "analysis_type": "activity_score",
            "input_snapshot": {"daily_steps": 7000},
            "authorization": "Bearer raw-token",
            "nested": {"token": "raw-nested-token", "safe": "ok"},
        },
    )

    assert fake_session.committed is True
    assert fake_session.added == [audit_log]
    assert isinstance(audit_log, AuditLog)
    assert audit_log.event_metadata == {
        "analysis_type": "activity_score",
        "nested": {"safe": "ok"},
    }
    assert audit_log.actor_subject_hash != "https://auth.example.com/::user_123"
    assert audit_log.ip_hash != "203.0.113.10"
    assert audit_log.user_agent_hash != "raw-test-agent"
    assert len(audit_log.record_hash) == 64


@pytest.mark.asyncio
async def test_delete_all_user_data_includes_p1_health_and_supplement_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify all owner-scoped P1 rows are included in all-user-data deletion."""
    owner_subject = "https://auth.example.com/::user_123"
    now = datetime.now(UTC)
    supplement = UserSupplement(
        id=uuid4(),
        owner_subject=owner_subject,
        display_name="Vitamin C",
        serving_snapshot={"serving_size": "1 tablet"},
        intake_schedule={"daily_count": 1},
    )
    supplement_ingredient = UserSupplementIngredient(
        id=uuid4(),
        user_supplement_id=supplement.id,
        display_name="Vitamin C",
        amount=Decimal("500"),
        unit="mg",
        confidence=Decimal("1.0"),
        source="user_confirmed",
    )
    supplement_run = SupplementAnalysisRun(
        id=uuid4(),
        owner_subject=owner_subject,
        status="requires_confirmation",
        image_sha256="a" * 64,
        image_mime_type="image/png",
        image_size_bytes=1024,
        parsed_snapshot={"items": []},
        match_snapshot={"matches": []},
        warnings=[],
        algorithm_version="supplement-parser-v1",
        expires_at=now + timedelta(minutes=30),
    )
    health_summary = HealthDailySummary(
        id=uuid4(),
        owner_subject=owner_subject,
        measured_date=date(2026, 5, 12),
        source_platform="manual",
        steps=7000,
    )
    health_batch = HealthSyncBatch(
        id=uuid4(),
        owner_subject=owner_subject,
        client_batch_id="batch-123",
        source_platform="manual",
        record_count=1,
        accepted_count=1,
        rejected_count=0,
        input_snapshot={"source": "manual"},
        result_snapshot={"accepted": 1},
    )
    body_profile = BodyProfileSnapshot(
        id=uuid4(),
        owner_subject=owner_subject,
        effective_at=now,
        source="manual",
        sex="male",
        birth_year=1990,
        height_cm=Decimal("175.0"),
        weight_kg=Decimal("72.0"),
        consent_snapshot={"consents": ["sensitive_health_analysis"]},
    )
    health_metric_sample = HealthMetricSample(
        id=uuid4(),
        owner_subject=owner_subject,
        metric_type="steps",
        measured_at=now,
        value_numeric=Decimal("7000"),
        unit="count",
        source_platform="manual",
        source_record_hash="e" * 64,
        quality_flags=[],
    )
    analysis_result = AnalysisResult(
        id=uuid4(),
        owner_subject=owner_subject,
        analysis_type="nutrition_analysis",
        algorithm_version="phase1-core-v1",
        input_snapshot={"meal": "sample"},
        result_snapshot={"score": 1},
    )
    consent_record = ConsentRecord(
        id=uuid4(),
        owner_subject=owner_subject,
        consent_type="sensitive_health_analysis",
        policy_version="2026-05-11",
        granted=True,
        occurred_at=now,
    )
    regulated_document = RegulatedDocument(
        id=uuid4(),
        owner_subject_hash="a" * 64,
        document_type="prescription",
        status="requires_confirmation",
        image_sha256="b" * 64,
        image_mime_type="image/png",
        image_size_bytes=1024,
        parsed_snapshot={"recognized_items": []},
        warning_codes=[],
        consult_cta={"type": "consult_professional"},
        algorithm_version="regulated-ocr-intake-v1.0.0",
        raw_image_deleted_at=now,
        expires_at=now + timedelta(minutes=30),
    )
    medical_collection = MedicalRecordCollection(
        id=uuid4(),
        owner_subject_hash="a" * 64,
        record_type="medication",
        source="regulated_ocr_confirmed",
        source_document_id=regulated_document.id,
        status="active",
        consent_snapshot={"consents": ["sensitive_health_analysis"]},
    )
    patient_condition = PatientCondition(
        id=uuid4(),
        medical_collection_id=medical_collection.id,
        condition_text="confirmed condition",
        condition_code_system="internal",
        condition_code_hash="f" * 64,
        clinical_status="active",
        source="user_confirmed",
        confirmed_at=now,
    )
    patient_medication = PatientMedication(
        id=uuid4(),
        medical_collection_id=medical_collection.id,
        medication_name_text="confirmed medication",
        dose_text="confirmed dose",
        frequency_text="confirmed frequency",
        active_status="active",
        source_document_id=regulated_document.id,
        confirmed_at=now,
    )
    patient_status_snapshot = PatientStatusSnapshot(
        id=uuid4(),
        owner_subject_hash="a" * 64,
        status_at=now,
        summary_type="confirmed_record_summary",
        symptom_categories=[],
        metric_summary={"records": 1},
        medication_summary={"active_count": 1},
        risk_flags=["data_insufficient"],
        data_quality="partial",
        generated_by="backend_rule",
        expires_at=now + timedelta(days=1),
    )
    media_object = MediaObject(
        id=uuid4(),
        owner_subject_hash="a" * 64,
        domain="supplement_label",
        object_storage_provider="supabase_s3",
        object_ref="supplement/2026/05/object.png",
        image_sha256="c" * 64,
        image_mime_type="image/png",
        image_size_bytes=1024,
        exif_stripped=True,
        retained_until=now + timedelta(days=30),
        status="retained",
        consent_snapshot={"consents": []},
    )
    media_processing_run = MediaProcessingRun(
        id=uuid4(),
        media_object_id=media_object.id,
        pipeline_type="quality_check",
        provider="internal",
        status="succeeded",
        sanitized_snapshot={"quality": "usable"},
        warning_codes=[],
    )
    supplement_image_evidence = SupplementImageEvidence(
        id=uuid4(),
        analysis_run_id=supplement_run.id,
        media_object_id=media_object.id,
        image_role="supplement_facts",
        quality_status="usable",
        quality_codes=[],
        roi_snapshot={"boxes": []},
    )
    meal_record = MealRecord(
        id=uuid4(),
        owner_subject=owner_subject,
        client_request_id="meal-req-123",
        eaten_at=now,
        meal_type="lunch",
        source="gallery",
        status="requires_confirmation",
        nutrition_summary={"kcal": 600},
        confidence=Decimal("0.8000"),
    )
    meal_food_item = MealFoodItem(
        id=uuid4(),
        meal_id=meal_record.id,
        food_name_text="sample food",
        portion_amount=Decimal("1.0"),
        portion_unit="serving",
        kcal=Decimal("600"),
        source="vision",
        confidence=Decimal("0.7000"),
        sort_order=0,
    )
    food_image_analysis_run = FoodImageAnalysisRun(
        id=uuid4(),
        owner_subject=owner_subject,
        client_request_id="food-image-req-123",
        media_object_id=media_object.id,
        meal_id=meal_record.id,
        image_sha256="d" * 64,
        image_mime_type="image/png",
        image_size_bytes=2048,
        detector_model="food-detector-test",
        classifier_model="food-classifier-test",
        status="requires_confirmation",
        detected_items_snapshot={"items": []},
        nutrition_estimate_snapshot={"items": []},
        warning_codes=[],
    )
    dataset_item = LearningDatasetItem(
        id=uuid4(),
        dataset_version_id=uuid4(),
        owner_subject_hash="a" * 64,
        media_object_id=media_object.id,
        source_domain="food",
        task_type="food_classification",
        label_status="human_reviewed",
        split="train",
        label_snapshot={"class_label": "sample"},
        label_hash="f" * 64,
        quality_score=Decimal("0.8500"),
        consent_snapshot={"consents": ["food_image_processing"]},
        retained_until=now + timedelta(days=30),
    )
    annotation_task = AnnotationTask(
        id=uuid4(),
        owner_subject_hash="a" * 64,
        media_object_id=media_object.id,
        learning_image_object_id=uuid4(),
        task_type="food_class",
        status="accepted",
        assignee_role="nutrition_reviewer",
        label_snapshot={"class_label": "sample"},
        review_notes_code="accepted",
        reviewer_hash="f" * 64,
        completed_at=now,
    )
    fake_session = _FakeDeletionSession(
        {
            HealthDailySummary: [health_summary],
            HealthSyncBatch: [health_batch],
            BodyProfileSnapshot: [body_profile],
            HealthMetricSample: [health_metric_sample],
            SupplementAnalysisRun: [supplement_run],
            UserSupplement: [supplement],
            UserSupplementIngredient: [supplement_ingredient],
            AnalysisResult: [analysis_result],
            RegulatedDocument: [regulated_document],
            MedicalRecordCollection: [medical_collection],
            PatientCondition: [patient_condition],
            PatientMedication: [patient_medication],
            PatientStatusSnapshot: [patient_status_snapshot],
            ConsentRecord: [consent_record],
            MediaObject: [media_object],
            MediaProcessingRun: [media_processing_run],
            SupplementImageEvidence: [supplement_image_evidence],
            MealRecord: [meal_record],
            MealFoodItem: [meal_food_item],
            FoodImageAnalysisRun: [food_image_analysis_run],
            LearningDatasetItem: [dataset_item],
            AnnotationTask: [annotation_task],
        }
    )
    fake_media_store = _FakeMediaObjectStore()
    monkeypatch.setattr(
        "src.services.privacy.build_media_object_store",
        lambda _settings: fake_media_store,
    )
    settings = Settings(privacy_hash_secret=SecretStr("test-privacy-secret"))

    deletion_request = await create_delete_all_user_data_request(
        cast(AsyncSession, fake_session),
        _user(),
        _request(),
        settings,
    )

    assert fake_session.deleted == [
        media_processing_run,
        media_object,
        supplement_ingredient,
        supplement,
        food_image_analysis_run,
        meal_food_item,
        meal_record,
        supplement_image_evidence,
        supplement_run,
        body_profile,
        health_metric_sample,
        health_summary,
        health_batch,
        analysis_result,
        patient_status_snapshot,
        patient_condition,
        patient_medication,
        medical_collection,
        regulated_document,
        consent_record,
    ]
    assert fake_media_store.deleted == [
        MediaObjectReference(
            object_storage_provider=media_object.object_storage_provider,
            object_ref=media_object.object_ref,
            object_version_id=media_object.object_version_id,
        )
    ]
    assert isinstance(deletion_request, DeletionRequest)
    assert dataset_item.label_status == "revoked"
    assert dataset_item.media_object_id is None
    assert dataset_item.label_snapshot == {}
    assert dataset_item.label_hash is None
    assert dataset_item.consent_snapshot == {}
    assert annotation_task.status == "cancelled"
    assert annotation_task.media_object_id is None
    assert annotation_task.learning_image_object_id is None
    assert annotation_task.label_snapshot == {}
    assert annotation_task.review_notes_code is None
    assert annotation_task.reviewer_hash is None
    assert deletion_request.deleted_counts == {
        "annotation_tasks_cancelled": 1,
        "analysis_results": 1,
        "consent_records": 1,
        "body_profile_snapshots": 1,
        "health_daily_summaries": 1,
        "health_metric_samples": 1,
        "health_sync_batches": 1,
        "food_image_analysis_runs": 1,
        "image_embedding_jobs": 0,
        "image_embedding_records": 0,
        "learning_image_object_blobs": 0,
        "learning_image_object_delete_failures": 0,
        "learning_image_objects_retained_for_retry": 0,
        "learning_image_objects": 0,
        "learning_dataset_items_revoked": 1,
        "meal_food_items": 1,
        "meal_records": 1,
        "media_object_blobs": 1,
        "media_object_delete_failures": 0,
        "media_objects_retained_for_retry": 0,
        "media_objects": 1,
        "media_processing_runs": 1,
        "medical_record_collections": 1,
        "patient_conditions": 1,
        "patient_medications": 1,
        "patient_status_snapshots": 1,
        "regulated_documents": 1,
        "supplement_image_evidence": 1,
        "supplement_analysis_runs": 1,
        "user_supplement_ingredients": 1,
        "user_supplements": 1,
    }
    assert fake_session.added[0] is deletion_request
    assert isinstance(fake_session.added[1], AuditLog)
    serialized_metadata = str(fake_session.added[1].event_metadata)
    assert media_object.object_ref not in serialized_metadata
    assert "owner_subject_hash" not in serialized_metadata


@pytest.mark.asyncio
async def test_delete_all_user_data_marks_failed_when_learning_object_delete_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify delete-all requests fail closed when private object deletion fails."""
    owner_subject = "https://auth.example.com/::user_123"
    now = datetime.now(UTC)
    image_object = LearningImageObject(
        id=uuid4(),
        owner_subject_hash="a" * 64,
        analysis_id=uuid4(),
        image_sha256="b" * 64,
        object_uri="s3://learning-images/private/object.png",
        object_storage_provider="supabase_s3",
        object_version_id="version-1",
        image_mime_type="image/png",
        image_size_bytes=1024,
        retained_until=now + timedelta(days=30),
        status="ready",
        consent_snapshot={"consents": []},
    )
    embedding_job = ImageEmbeddingJob(
        id=uuid4(),
        image_object_id=image_object.id,
        analysis_id=image_object.analysis_id,
        owner_subject_hash=image_object.owner_subject_hash,
        embedding_model="clip-test",
        status="pending",
        attempt_count=0,
        next_run_at=now,
        metadata_snapshot={"display_name": "Vitamin C"},
    )
    embedding_record = ImageEmbeddingRecord(
        id=uuid4(),
        owner_subject_hash=image_object.owner_subject_hash,
        analysis_id=image_object.analysis_id,
        image_object_id=image_object.id,
        image_sha256=image_object.image_sha256,
        embedding_model="clip-test",
        embedding_dimensions=3,
        embedding=(0.1, 0.2, 0.3),
        embedding_metadata={"display_name": "Vitamin C"},
    )
    consent_record = ConsentRecord(
        id=uuid4(),
        owner_subject=owner_subject,
        consent_type="image_learning_dataset",
        policy_version="2026-05-24",
        granted=True,
        occurred_at=now,
    )
    fake_session = _FakeDeletionSession(
        {
            ImageEmbeddingJob: [embedding_job],
            ImageEmbeddingRecord: [embedding_record],
            LearningImageObject: [image_object],
            ConsentRecord: [consent_record],
        }
    )
    fake_store = _FakeLearningObjectStore(fail=True)
    monkeypatch.setattr(
        "src.services.privacy.build_learning_object_store",
        lambda _settings: fake_store,
    )
    settings = Settings(privacy_hash_secret=SecretStr("test-privacy-secret"))

    deletion_request = await create_delete_all_user_data_request(
        cast(AsyncSession, fake_session),
        _user(),
        _request(),
        settings,
    )

    assert deletion_request.status == "failed"
    assert deletion_request.completed_at is None
    assert deletion_request.failure_reason == "learning_image_object_delete_failed"
    assert deletion_request.deleted_counts["learning_image_objects"] == 0
    assert deletion_request.deleted_counts["learning_image_object_delete_failures"] == 1
    assert deletion_request.deleted_counts["learning_image_objects_retained_for_retry"] == 1
    assert image_object.status == "failed"
    assert fake_session.deleted == [embedding_job, embedding_record, consent_record]
    audit_log = fake_session.added[1]
    assert isinstance(audit_log, AuditLog)
    assert audit_log.outcome == "failed"
    serialized_metadata = str(audit_log.event_metadata)
    assert image_object.object_uri not in serialized_metadata
    assert "owner_subject_hash" not in serialized_metadata


@pytest.mark.asyncio
async def test_delete_all_user_data_marks_failed_when_media_object_delete_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify delete-all requests fail closed when private media deletion fails."""
    owner_subject = "https://auth.example.com/::user_123"
    now = datetime.now(UTC)
    media_object = MediaObject(
        id=uuid4(),
        owner_subject_hash="a" * 64,
        domain="supplement_label",
        object_storage_provider="supabase_s3",
        object_ref="supplement/2026/05/object.png",
        object_version_id="version-1",
        image_sha256="c" * 64,
        image_mime_type="image/png",
        image_size_bytes=1024,
        exif_stripped=True,
        retained_until=now + timedelta(days=30),
        status="retained",
        consent_snapshot={"consents": []},
    )
    media_processing_run = MediaProcessingRun(
        id=uuid4(),
        media_object_id=media_object.id,
        pipeline_type="quality_check",
        provider="internal",
        status="succeeded",
        sanitized_snapshot={"quality": "usable"},
        warning_codes=[],
    )
    consent_record = ConsentRecord(
        id=uuid4(),
        owner_subject=owner_subject,
        consent_type="sensitive_health_analysis",
        policy_version="2026-05-11",
        granted=True,
        occurred_at=now,
    )
    fake_session = _FakeDeletionSession(
        {
            MediaObject: [media_object],
            MediaProcessingRun: [media_processing_run],
            ConsentRecord: [consent_record],
        }
    )
    fake_media_store = _FakeMediaObjectStore(fail=True)
    monkeypatch.setattr(
        "src.services.privacy.build_media_object_store",
        lambda _settings: fake_media_store,
    )
    settings = Settings(privacy_hash_secret=SecretStr("test-privacy-secret"))

    deletion_request = await create_delete_all_user_data_request(
        cast(AsyncSession, fake_session),
        _user(),
        _request(),
        settings,
    )

    assert deletion_request.status == "failed"
    assert deletion_request.completed_at is None
    assert deletion_request.failure_reason == "media_object_delete_failed"
    assert deletion_request.deleted_counts["media_objects"] == 0
    assert deletion_request.deleted_counts["media_object_delete_failures"] == 1
    assert deletion_request.deleted_counts["media_objects_retained_for_retry"] == 1
    assert media_object.status == "failed"
    assert fake_session.deleted == [media_processing_run, consent_record]
    audit_log = fake_session.added[1]
    assert isinstance(audit_log, AuditLog)
    assert audit_log.outcome == "failed"
    serialized_metadata = str(audit_log.event_metadata)
    assert media_object.object_ref not in serialized_metadata
    assert "owner_subject_hash" not in serialized_metadata


def _patch_audit_spy(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    """Replace record_audit_event with a spy so persist_scope can be tested in isolation.

    Returns:
        A list that captures the keyword arguments of each record_audit_event call.
        (Participate-mode record_audit_event writes out-of-band via the privileged
        audit engine, which a pure unit test cannot reach; the audit's own behavior is
        covered by ``test_record_audit_event_*`` and the Stage-2 suite.)
    """
    calls: list[dict[str, object]] = []

    async def _spy(_session: object, _user: object, **kwargs: object) -> None:
        calls.append(kwargs)

    monkeypatch.setattr("src.services.privacy.record_audit_event", _spy)
    return calls


def _privacy_settings() -> Settings:
    return Settings(privacy_hash_secret=SecretStr("test-privacy-secret"))


@pytest.mark.asyncio
async def test_grant_consent_owns_transaction_in_legacy_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy (get_async_session) sessions commit the consent grant exactly once."""
    audit_calls = _patch_audit_spy(monkeypatch)
    fake_session = _FakeDeletionSession({})  # no marker → OWN mode

    record = await grant_consent(
        cast(AsyncSession, fake_session),
        _user(),
        ConsentType.EXTERNAL_OCR_PROCESSING,
        _request(),
        _privacy_settings(),
    )

    assert record.granted is True
    assert fake_session.added == [record]  # only the consent row; audit is decoupled
    assert fake_session.commits == 1
    assert len(audit_calls) == 1
    assert audit_calls[0]["outcome"] == "success"


@pytest.mark.asyncio
async def test_grant_consent_participates_in_request_managed_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RLS (get_rls_context_session) sessions never commit; the dependency owns the tx."""
    audit_calls = _patch_audit_spy(monkeypatch)
    fake_session = _FakeDeletionSession({}, request_managed=True)

    await grant_consent(
        cast(AsyncSession, fake_session),
        _user(),
        ConsentType.EXTERNAL_OCR_PROCESSING,
        _request(),
        _privacy_settings(),
    )

    assert fake_session.commits == 0
    assert len(audit_calls) == 1


@pytest.mark.asyncio
async def test_revoke_consent_participates_in_request_managed_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RLS sessions never commit the revocation; the dependency owns the tx."""
    audit_calls = _patch_audit_spy(monkeypatch)
    # EXTERNAL_OCR_PROCESSING is not a learning consent → no object-store side effects.
    fake_session = _FakeDeletionSession({}, request_managed=True)

    record = await revoke_consent(
        cast(AsyncSession, fake_session),
        _user(),
        ConsentType.EXTERNAL_OCR_PROCESSING,
        _request(),
        _privacy_settings(),
    )

    assert record.granted is False
    assert fake_session.commits == 0
    # The audit is decoupled: only the consent revocation row hits the request session.
    assert fake_session.added == [record]
    assert audit_calls[0]["outcome"] == "success"


@pytest.mark.asyncio
async def test_revoke_learning_consent_records_failed_outcome_on_object_store_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing learning object-store delete propagates outcome='failed' to the audit.

    Covers the revoke_consent learning path (IMAGE_LEARNING_DATASET) under participate mode and
    the failed-outcome marker that the design flags as the named risk surface.
    """
    audit_calls = _patch_audit_spy(monkeypatch)
    now = datetime.now(UTC)
    image_object = LearningImageObject(
        id=uuid4(),
        owner_subject_hash="a" * 64,
        analysis_id=uuid4(),
        image_sha256="b" * 64,
        object_uri="s3://learning-images/private/object.png",
        object_storage_provider="supabase_s3",
        object_version_id="version-1",
        image_mime_type="image/png",
        image_size_bytes=1024,
        retained_until=now + timedelta(days=30),
        status="ready",
        consent_snapshot={"consents": []},
    )
    fake_session = _FakeDeletionSession({LearningImageObject: [image_object]}, request_managed=True)
    fake_store = _FakeLearningObjectStore(fail=True)
    monkeypatch.setattr(
        "src.services.privacy.build_learning_object_store", lambda _settings: fake_store
    )

    await revoke_consent(
        cast(AsyncSession, fake_session),
        _user(),
        ConsentType.IMAGE_LEARNING_DATASET,
        _request(),
        _privacy_settings(),
    )

    assert fake_session.commits == 0  # participate: dependency owns the commit
    assert audit_calls[0]["outcome"] == "failed"
    failures = audit_calls[0]["event_metadata"]["learning_deleted_counts"][
        "learning_image_object_delete_failures"
    ]
    assert failures >= 1


def _analysis_result(result_id: object) -> AnalysisResult:
    now = datetime.now(UTC)
    return AnalysisResult(
        id=result_id,
        owner_subject="https://auth.example.com/::user_123",
        analysis_type="activity_score",
        algorithm_version="activity-v1.0.0",
        input_snapshot={},
        result_snapshot={},
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_delete_analysis_result_owns_transaction_in_legacy_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy sessions commit a successful delete once and audit outcome=success."""
    audit_calls = _patch_audit_spy(monkeypatch)
    result_id = uuid4()
    record = _analysis_result(result_id)
    fake_session = _FakeDeletionSession({AnalysisResult: [record]})  # OWN mode

    deleted = await delete_analysis_result_for_user(
        cast(AsyncSession, fake_session),
        _user(),
        result_id,
        _request(),
        _privacy_settings(),
    )

    assert deleted is True
    assert fake_session.deleted == [record]
    assert fake_session.commits == 1
    assert audit_calls[0]["outcome"] == "success"


@pytest.mark.asyncio
async def test_delete_analysis_result_participates_and_reports_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RLS sessions never commit; a missing row reports not_found without deleting."""
    audit_calls = _patch_audit_spy(monkeypatch)
    fake_session = _FakeDeletionSession({}, request_managed=True)  # participate, no row

    deleted = await delete_analysis_result_for_user(
        cast(AsyncSession, fake_session),
        _user(),
        uuid4(),
        _request(),
        _privacy_settings(),
    )

    assert deleted is False
    assert fake_session.deleted == []
    assert fake_session.commits == 0
    assert audit_calls[0]["outcome"] == "not_found"
