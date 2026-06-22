"""Regulated prescription and lab OCR intake API tests."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Any, Self, cast
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import SecretStr
from src.api.v1 import regulated_inputs
from src.config import Settings, get_settings
from src.db.dependencies import get_rls_context_session
from src.main import create_app
from src.models.db.privacy import AuditLog
from src.models.db.regulated import LabResultItem, PrescriptionItem, RegulatedDocument
from src.models.schemas.privacy import ConsentType
from src.models.schemas.regulated import RegulatedDocumentStatus, RegulatedDocumentType
from src.ocr.base import OCRAdapter, OCRImageInput, OCRResult
from src.regulated.factory import RegulatedOCRAdapters
from src.security.auth import AuthenticatedUser
from src.security.privacy import hash_actor_subject
from src.services.privacy import ConsentRequiredError


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
    """Fake async session for regulated route tests."""

    def __init__(self, document: RegulatedDocument | None = None) -> None:
        self.document = document
        self.added_documents: list[RegulatedDocument] = []
        self.added_audits: list[AuditLog] = []
        self.added_prescription_items: list[PrescriptionItem] = []
        self.added_lab_result_items: list[LabResultItem] = []
        self.committed = False
        # A real AsyncSession always exposes ``.info``; persist_scope reads it.
        self.info: dict[str, object] = {}

    async def flush(self) -> None:
        """No-op flush (persist_scope flushes pending writes)."""

    def begin(self) -> _TransactionContext:
        """Return a fake transaction context.

        Returns:
            Fake transaction context.
        """
        return _TransactionContext()

    async def scalar(self, _statement: object) -> RegulatedDocument | None:
        """Return the configured regulated document.

        Args:
            _statement: SQLAlchemy select statement.

        Returns:
            Stored regulated document.
        """
        return self.document

    def add(self, record: object) -> None:
        """Capture ORM records passed by route services.

        Args:
            record: ORM object.
        """
        if isinstance(record, RegulatedDocument):
            self.document = record
            self.added_documents.append(record)
            return
        if isinstance(record, AuditLog):
            self.added_audits.append(record)
            return
        if isinstance(record, PrescriptionItem):
            self.added_prescription_items.append(record)
            return
        if isinstance(record, LabResultItem):
            self.added_lab_result_items.append(record)

    async def refresh(self, record: object) -> None:
        """Populate generated timestamps on fake records.

        Args:
            record: ORM object to refresh.
        """
        regulated_document = cast(RegulatedDocument, record)
        regulated_document.created_at = datetime.now(UTC)
        regulated_document.updated_at = datetime.now(UTC)

    async def commit(self) -> None:
        """Record an audit commit."""
        self.committed = True


class _FakeOCRAdapter(OCRAdapter):
    """Fake OCR adapter for regulated route tests."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.call_count = 0

    async def extract_text(self, image: OCRImageInput) -> OCRResult:
        """Return fake OCR text.

        Args:
            image: OCR image input.

        Returns:
            Fake OCR result.
        """
        self.call_count += 1
        assert image.image_bytes
        return OCRResult(text=self.text, provider="fake_ocr", confidence=0.91)


def _settings(**overrides: Any) -> Settings:
    """Return route test settings.

    Args:
        **overrides: Settings field overrides.

    Returns:
        Settings object.
    """
    values: dict[str, Any] = {
        "_env_file": None,
        "privacy_hash_secret": SecretStr("test-privacy-secret"),
    }
    values.update(overrides)
    return Settings(**values)


def _png_bytes() -> bytes:
    """Return a tiny PNG image.

    Returns:
        PNG image bytes.
    """
    buffer = BytesIO()
    Image.new("RGB", (3, 2), color=(255, 255, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def _session_dependency(
    fake_session: _FakeRegulatedSession,
) -> Callable[[], AsyncIterator[object]]:
    """Build a FastAPI session dependency override.

    Args:
        fake_session: Fake async session.

    Returns:
        Dependency callable.
    """

    async def dependency() -> AsyncIterator[object]:
        """Yield the fake session.

        Yields:
            Fake session.
        """
        yield fake_session

    return dependency


def _client(fake_session: _FakeRegulatedSession, settings: Settings) -> TestClient:
    """Build a TestClient with fake DB dependencies.

    Args:
        fake_session: Fake async session.
        settings: Runtime settings.

    Returns:
        Test client.
    """
    app = create_app(settings=settings)
    app.dependency_overrides[get_settings] = lambda: settings
    # Routes adopted get_rls_context_session (ambient-tx Step 6, RLS Stage-2 rollout).
    app.dependency_overrides[get_rls_context_session] = _session_dependency(fake_session)
    return TestClient(app)


def _document(document_type: RegulatedDocumentType, settings: Settings) -> RegulatedDocument:
    """Build a regulated document fixture.

    Args:
        document_type: Regulated document type.
        settings: Runtime settings used for owner hashing.

    Returns:
        Regulated document ORM object.
    """
    now = datetime.now(UTC)
    user = AuthenticatedUser(subject="local-dev-user", issuer="local-development")
    return RegulatedDocument(
        id=uuid4(),
        owner_subject_hash=hash_actor_subject(user, settings),
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


def test_prescription_ocr_feature_default_off() -> None:
    """Verify prescription OCR intake fails closed by default."""
    client = _client(_FakeRegulatedSession(), _settings())

    response = client.post(
        "/api/v1/regulated-inputs/prescriptions/ocr",
        files={"image": ("prescription.png", _png_bytes(), "image/png")},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"]["code"] == "feature_disabled"


def test_prescription_ocr_requires_sensitive_specific_and_external_consents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify Google OCR path requires all regulated consent buckets before OCR."""
    settings = _settings(
        feature_prescription_ocr_intake=True,
        ocr_primary_provider="google_vision",
        allow_external_ocr=True,
        google_cloud_api_key="test-key",
    )
    fake_ocr = _FakeOCRAdapter("Amoxicillin 500mg 하루 2회 7일")

    async def deny_consent(*args: object, **_kwargs: object) -> None:
        """Deny prescription and external OCR consent buckets."""
        consent_type = cast(ConsentType, args[2])
        if consent_type in {
            ConsentType.PRESCRIPTION_OCR_INTAKE,
            ConsentType.EXTERNAL_OCR_PROCESSING,
        }:
            raise ConsentRequiredError(f"{consent_type.value} is required.")

    async def record_noop_audit(*_args: object, **_kwargs: object) -> None:
        """No-op audit writer for consent-block tests."""

    monkeypatch.setattr(regulated_inputs, "require_user_consent", deny_consent)
    monkeypatch.setattr(regulated_inputs, "record_sensitive_audit_event", record_noop_audit)
    monkeypatch.setattr(
        regulated_inputs,
        "build_regulated_ocr_adapters",
        lambda _settings: RegulatedOCRAdapters(ocr=fake_ocr),
    )
    client = _client(_FakeRegulatedSession(), settings)

    response = client.post(
        "/api/v1/regulated-inputs/prescriptions/ocr",
        files={"image": ("prescription.png", _png_bytes(), "image/png")},
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"]["required_consents"] == [
        "prescription_ocr_intake",
        "external_ocr_processing",
    ]
    assert fake_ocr.call_count == 0


def test_prescription_ocr_preview_uses_fake_provider_without_raw_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify enabled prescription OCR returns preview metadata without raw storage."""
    settings = _settings(feature_prescription_ocr_intake=True)
    fake_session = _FakeRegulatedSession()
    fake_ocr = _FakeOCRAdapter("Amoxicillin 500mg 하루 2회 7일")

    async def allow_consent(*_args: object, **_kwargs: object) -> None:
        """Allow every consent bucket."""

    monkeypatch.setattr(regulated_inputs, "require_user_consent", allow_consent)
    monkeypatch.setattr(
        regulated_inputs,
        "build_regulated_ocr_adapters",
        lambda _settings: RegulatedOCRAdapters(ocr=fake_ocr),
    )
    client = _client(fake_session, settings)

    response = client.post(
        "/api/v1/regulated-inputs/prescriptions/ocr",
        files={"image": ("prescription.png", _png_bytes(), "image/png")},
    )

    assert response.status_code == status.HTTP_202_ACCEPTED
    body = response.json()
    assert body["raw_image_stored"] is False
    assert body["raw_ocr_text_stored"] is False
    assert body["recognized_items"][0]["medication_name_text"] == "Amoxicillin"
    assert fake_session.added_documents[0].ocr_text_hash is not None
    assert "raw_ocr_text" not in fake_session.added_documents[0].parsed_snapshot
    assert fake_ocr.call_count == 1


def test_confirm_rejects_direct_dose_change_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify confirm route blocks direct dose-change advice in user-confirmed fields."""
    settings = _settings(feature_prescription_ocr_intake=True)
    document = _document(RegulatedDocumentType.PRESCRIPTION, settings)
    fake_session = _FakeRegulatedSession(document=document)

    async def allow_consent(*_args: object, **_kwargs: object) -> None:
        """Allow every consent bucket."""

    monkeypatch.setattr(regulated_inputs, "require_user_consent", allow_consent)
    client = _client(fake_session, settings)

    response = client.post(
        f"/api/v1/regulated-inputs/{document.id}/confirm",
        json={
            "document_type": "prescription",
            "prescription_items": [
                {
                    "medication_name_text": "Amoxicillin",
                    "dose_text": "오늘부터 줄이세요",
                }
            ],
            "user_confirmed": True,
            "consult_professional_acknowledged": True,
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["detail"]["code"] == "blocked_medical_output"
    assert fake_session.added_prescription_items == []
