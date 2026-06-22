"""Regulated OCR intake service tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Self, cast
from uuid import uuid4

import pytest
from fastapi import UploadFile
from PIL import Image
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession
from src.config import Settings
from src.db.tx import REQUEST_MANAGED_TX
from src.models.db.medical import MedicalRecordCollection, PatientMedication
from src.models.db.regulated import LabResultItem, PrescriptionItem, RegulatedDocument
from src.models.schemas.regulated import (
    LabResultItemConfirm,
    PrescriptionItemConfirm,
    RegulatedDocumentConfirmRequest,
    RegulatedDocumentStatus,
    RegulatedDocumentType,
)
from src.ocr.base import OCRAdapter, OCRImageInput, OCRResult
from src.regulated.factory import RegulatedOCRAdapters
from src.regulated.ocr_intake import (
    RegulatedMedicalOutputBlockedError,
    assert_no_blocked_medical_outputs,
    confirm_regulated_document,
    create_lab_result_ocr_preview,
    create_prescription_ocr_preview,
)
from src.security.auth import AuthenticatedUser
from src.security.privacy import hash_actor_subject
from starlette.datastructures import Headers


class _TransactionContext:
    """Async context manager used by the fake session transaction."""

    async def __aenter__(self) -> Self:
        """Enter the fake transaction.

        Returns:
            Context manager instance.
        """
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        """Exit the fake transaction.

        Args:
            *_exc_info: Exception information ignored by the fake context.
        """


class _FakeRegulatedSession:
    """Fake async session for regulated intake service tests."""

    def __init__(
        self,
        document: RegulatedDocument | None = None,
        *,
        request_managed: bool = False,
    ) -> None:
        self.document = document
        self.added_documents: list[RegulatedDocument] = []
        self.added_prescription_items: list[PrescriptionItem] = []
        self.added_lab_result_items: list[LabResultItem] = []
        self.added_medical_collections: list[MedicalRecordCollection] = []
        self.added_patient_medications: list[PatientMedication] = []
        self.commits = 0
        # A real AsyncSession always exposes ``.info``; persist_scope reads it.
        self.info: dict[str, object] = {REQUEST_MANAGED_TX: True} if request_managed else {}

    def begin(self) -> _TransactionContext:
        """Return a fake transaction context.

        Returns:
            Fake transaction context.
        """
        return _TransactionContext()

    async def flush(self) -> None:
        """No-op flush (persist_scope flushes pending writes)."""

    async def commit(self) -> None:
        """Count commits (own-mode must commit exactly once)."""
        self.commits += 1

    async def rollback(self) -> None:
        """No-op rollback (own-mode rolls back on exception)."""

    async def scalar(self, _statement: object) -> RegulatedDocument | None:
        """Return the configured regulated document.

        Args:
            _statement: SQLAlchemy select statement.

        Returns:
            Stored regulated document or None.
        """
        return self.document

    def add(self, record: object) -> None:
        """Capture ORM records passed by services.

        Args:
            record: ORM object.
        """
        if isinstance(record, RegulatedDocument):
            self.document = record
            self.added_documents.append(record)
            return
        if isinstance(record, PrescriptionItem):
            self.added_prescription_items.append(record)
            return
        if isinstance(record, LabResultItem):
            self.added_lab_result_items.append(record)
            return
        if isinstance(record, MedicalRecordCollection):
            self.added_medical_collections.append(record)
            return
        if isinstance(record, PatientMedication):
            self.added_patient_medications.append(record)

    async def refresh(self, record: object) -> None:
        """Populate generated timestamps on fake records.

        Args:
            record: ORM object to refresh.
        """
        regulated_document = cast(RegulatedDocument, record)
        regulated_document.created_at = datetime.now(UTC)
        regulated_document.updated_at = datetime.now(UTC)


class _FakeOCRAdapter(OCRAdapter):
    """Fake OCR adapter returning configured text."""

    def __init__(self, text: str, *, confidence: float | None = 0.88) -> None:
        self.text = text
        self.confidence = confidence
        self.call_count = 0
        self.received_image: OCRImageInput | None = None

    async def extract_text(self, image: OCRImageInput) -> OCRResult:
        """Capture OCR input and return fake OCR output.

        Args:
            image: OCR image input.

        Returns:
            Fake OCR result.
        """
        self.call_count += 1
        self.received_image = image
        return OCRResult(text=self.text, provider="fake_ocr", confidence=self.confidence)


def _settings() -> Settings:
    """Return service test settings.

    Returns:
        Settings object.
    """
    return Settings(_env_file=None, privacy_hash_secret=SecretStr("test-privacy-secret"))


def _user() -> AuthenticatedUser:
    """Return an authenticated user fixture.

    Returns:
        Authenticated user model.
    """
    return AuthenticatedUser(subject="user_123", issuer="https://auth.example.com/")


def _png_bytes() -> bytes:
    """Return a tiny PNG image.

    Returns:
        PNG image bytes.
    """
    buffer = BytesIO()
    Image.new("RGB", (3, 2), color=(255, 255, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def _upload() -> UploadFile:
    """Build an UploadFile for service tests.

    Returns:
        PNG UploadFile object.
    """
    return UploadFile(
        file=BytesIO(_png_bytes()),
        filename="document.png",
        headers=Headers({"content-type": "image/png"}),
    )


def _document(document_type: RegulatedDocumentType, settings: Settings) -> RegulatedDocument:
    """Build a regulated document fixture.

    Args:
        document_type: Regulated document type.
        settings: Runtime settings used for owner hashing.

    Returns:
        Regulated document ORM object.
    """
    now = datetime.now(UTC)
    return RegulatedDocument(
        id=uuid4(),
        owner_subject_hash=hash_actor_subject(_user(), settings),
        document_type=document_type.value,
        status=RegulatedDocumentStatus.REQUIRES_CONFIRMATION.value,
        image_sha256="a" * 64,
        image_mime_type="image/png",
        image_size_bytes=128,
        ocr_provider="fake_ocr",
        ocr_confidence=None,
        ocr_text_hash="b" * 64,
        parsed_snapshot={"recognized_items": []},
        warning_codes=[],
        consult_cta={
            "type": "consult_professional",
            "title": "전문가 상담이 필요한 정보입니다.",
            "message": "담당 의료진 또는 약사와 상담하세요.",
            "action": "contact_clinician_or_pharmacist",
        },
        algorithm_version="regulated-ocr-intake-v1.0.0",
        raw_image_deleted_at=now,
        expires_at=now + timedelta(minutes=30),
        confirmed_at=None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_prescription_ocr_preview_stores_hashes_not_raw_text() -> None:
    """Verify prescription OCR preview stores structured fields without raw OCR text."""
    settings = _settings()
    fake_session = _FakeRegulatedSession()
    fake_ocr = _FakeOCRAdapter("Amoxicillin 500mg 하루 2회 7일")

    response = await create_prescription_ocr_preview(
        session=cast(AsyncSession, fake_session),
        user=_user(),
        image=_upload(),
        settings=settings,
        adapters=RegulatedOCRAdapters(ocr=fake_ocr),
    )

    assert response.raw_image_stored is False
    assert response.raw_ocr_text_stored is False
    assert response.recognized_items[0].medication_name_text == "Amoxicillin"
    assert response.recognized_items[0].dose_text == "500mg"
    assert fake_session.added_documents[0].ocr_text_hash is not None
    assert fake_session.added_documents[0].raw_image_deleted_at is not None
    assert "raw_ocr_text" not in fake_session.added_documents[0].parsed_snapshot
    assert fake_ocr.call_count == 1


@pytest.mark.asyncio
async def test_lab_result_ocr_preview_parses_visible_value_fields() -> None:
    """Verify lab OCR preview extracts value-like fields without diagnosis output."""
    settings = _settings()
    fake_session = _FakeRegulatedSession()
    fake_ocr = _FakeOCRAdapter("HbA1c 6.1 % 4.0-5.6")

    response = await create_lab_result_ocr_preview(
        session=cast(AsyncSession, fake_session),
        user=_user(),
        image=_upload(),
        settings=settings,
        adapters=RegulatedOCRAdapters(ocr=fake_ocr),
    )

    assert response.raw_image_stored is False
    assert response.raw_ocr_text_stored is False
    assert response.recognized_items[0].test_name_text == "HbA1c"
    assert response.recognized_items[0].value_text == "6.1"
    assert "diagnosis" not in str(fake_session.added_documents[0].parsed_snapshot).lower()


@pytest.mark.asyncio
async def test_confirm_prescription_stores_user_confirmed_items() -> None:
    """Verify confirmation persists only user-confirmed prescription fields."""
    settings = _settings()
    document = _document(RegulatedDocumentType.PRESCRIPTION, settings)
    fake_session = _FakeRegulatedSession(document=document)

    response = await confirm_regulated_document(
        session=cast(AsyncSession, fake_session),
        user=_user(),
        document_id=document.id,
        request=RegulatedDocumentConfirmRequest(
            document_type=RegulatedDocumentType.PRESCRIPTION,
            prescription_items=[
                PrescriptionItemConfirm(
                    medication_name_text="Amoxicillin",
                    dose_text="500mg",
                    frequency_text="하루 2회",
                    period_text="7일",
                )
            ],
        ),
        settings=settings,
    )

    assert response.status == RegulatedDocumentStatus.CONFIRMED
    assert document.status == RegulatedDocumentStatus.CONFIRMED.value
    assert fake_session.added_prescription_items[0].medication_name_text == "Amoxicillin"
    assert fake_session.added_lab_result_items == []
    assert fake_session.added_medical_collections[0].record_type == "prescription"
    assert fake_session.added_medical_collections[0].source == "regulated_ocr_confirmed"
    assert fake_session.added_medical_collections[0].source_document_id == document.id
    assert fake_session.added_patient_medications[0].medication_name_text == "Amoxicillin"
    assert fake_session.added_patient_medications[0].source_document_id == document.id
    serialized_medical = str(fake_session.added_medical_collections[0].__dict__) + str(
        fake_session.added_patient_medications[0].__dict__
    )
    assert "raw_ocr_text" not in serialized_medical
    assert "provider_payload" not in serialized_medical


@pytest.mark.asyncio
async def test_confirm_lab_result_stores_user_confirmed_items() -> None:
    """Verify confirmation persists only user-confirmed lab result fields."""
    settings = _settings()
    document = _document(RegulatedDocumentType.LAB_RESULT, settings)
    document.consult_cta["action"] = "contact_clinician"
    fake_session = _FakeRegulatedSession(document=document)

    await confirm_regulated_document(
        session=cast(AsyncSession, fake_session),
        user=_user(),
        document_id=document.id,
        request=RegulatedDocumentConfirmRequest(
            document_type=RegulatedDocumentType.LAB_RESULT,
            lab_result_items=[
                LabResultItemConfirm(
                    test_name_text="HbA1c",
                    value_text="6.1",
                    unit_text="%",
                    reference_range_text="4.0-5.6",
                )
            ],
        ),
        settings=settings,
    )

    assert fake_session.added_lab_result_items[0].test_name_text == "HbA1c"
    assert fake_session.added_prescription_items == []
    assert fake_session.added_medical_collections[0].record_type == "lab_result"
    assert fake_session.added_medical_collections[0].source_document_id == document.id
    assert fake_session.added_patient_medications == []


@pytest.mark.asyncio
async def test_preview_owns_transaction_in_legacy_mode() -> None:
    """Verify legacy (get_async_session) sessions commit the OCR preview exactly once."""
    settings = _settings()
    fake_session = _FakeRegulatedSession()  # no marker → OWN mode
    fake_ocr = _FakeOCRAdapter("Amoxicillin 500mg 하루 2회 7일")

    await create_prescription_ocr_preview(
        session=cast(AsyncSession, fake_session),
        user=_user(),
        image=_upload(),
        settings=settings,
        adapters=RegulatedOCRAdapters(ocr=fake_ocr),
    )

    assert fake_session.commits == 1


@pytest.mark.asyncio
async def test_preview_participates_in_request_managed_transaction() -> None:
    """Verify RLS (get_rls_context_session) sessions never commit the OCR preview."""
    settings = _settings()
    fake_session = _FakeRegulatedSession(request_managed=True)
    fake_ocr = _FakeOCRAdapter("Amoxicillin 500mg 하루 2회 7일")

    await create_prescription_ocr_preview(
        session=cast(AsyncSession, fake_session),
        user=_user(),
        image=_upload(),
        settings=settings,
        adapters=RegulatedOCRAdapters(ocr=fake_ocr),
    )

    assert fake_session.commits == 0


@pytest.mark.asyncio
async def test_confirm_owns_transaction_in_legacy_mode() -> None:
    """Verify legacy sessions commit the confirmation (document + items + audit) once."""
    settings = _settings()
    document = _document(RegulatedDocumentType.PRESCRIPTION, settings)
    fake_session = _FakeRegulatedSession(document=document)  # no marker → OWN mode

    await confirm_regulated_document(
        session=cast(AsyncSession, fake_session),
        user=_user(),
        document_id=document.id,
        request=RegulatedDocumentConfirmRequest(
            document_type=RegulatedDocumentType.PRESCRIPTION,
            prescription_items=[
                PrescriptionItemConfirm(
                    medication_name_text="Amoxicillin",
                    dose_text="500mg",
                    frequency_text="하루 2회",
                    period_text="7일",
                )
            ],
        ),
        settings=settings,
    )

    assert fake_session.commits == 1


@pytest.mark.asyncio
async def test_confirm_participates_in_request_managed_transaction() -> None:
    """Verify RLS sessions never commit the confirmation; the dependency owns the tx.

    The document update, child item inserts, and medical-collection writes must all
    stay in the request transaction so the transaction-local RLS GUCs survive.
    """
    settings = _settings()
    document = _document(RegulatedDocumentType.PRESCRIPTION, settings)
    fake_session = _FakeRegulatedSession(document=document, request_managed=True)

    await confirm_regulated_document(
        session=cast(AsyncSession, fake_session),
        user=_user(),
        document_id=document.id,
        request=RegulatedDocumentConfirmRequest(
            document_type=RegulatedDocumentType.PRESCRIPTION,
            prescription_items=[
                PrescriptionItemConfirm(
                    medication_name_text="Amoxicillin",
                    dose_text="500mg",
                    frequency_text="하루 2회",
                    period_text="7일",
                )
            ],
        ),
        settings=settings,
    )

    assert fake_session.commits == 0


def test_direct_dose_change_guidance_is_blocked() -> None:
    """Verify direct medication adjustment language is rejected."""
    with pytest.raises(RegulatedMedicalOutputBlockedError):
        assert_no_blocked_medical_outputs(
            {"prescription_items": [{"dose_text": "오늘부터 줄이세요"}]}
        )
