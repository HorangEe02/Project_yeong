"""Supplement analyze Google Vision integration tests with fake adapters."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace
from typing import Self, cast
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import SecretStr
from src.api.v1 import supplements
from src.config import Settings, get_settings
from src.db.dependencies import get_async_session
from src.main import create_app
from src.models.db.privacy import AuditLog
from src.models.db.supplement import SupplementAnalysisRun
from src.models.schemas.privacy import ConsentType
from src.models.schemas.supplement_parser import SupplementStructuredParseResult
from src.ocr.base import OCRAdapter, OCRError, OCRImageInput, OCRResult
from src.services.privacy import ConsentRequiredError
from src.services.supplement_image_analysis import SupplementImageAnalysisAdapters


@pytest.fixture(autouse=True)
def _capture_supplement_audits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Capture out-of-band audits into the fake session (ambient-tx Step 7).

    The analyze route adopted a route-owned RLS transaction, so
    ``record_sensitive_audit_event`` runs out-of-band on a privileged session the
    fake cannot observe. Capture the call args into the fake's ``added_audits`` so
    no real audit connection opens during these fake-session route tests. Tests
    that install their own ``record_sensitive_audit_event`` patch still win.
    """

    async def _capture(session: object, _current_user: object, **kwargs: object) -> None:
        audits = getattr(session, "added_audits", None)
        if audits is not None:
            audits.append(SimpleNamespace(**kwargs))

    monkeypatch.setattr(supplements, "record_sensitive_audit_event", _capture)


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


class _FakeSupplementSession:
    """Fake async session for Google Vision route tests."""

    def __init__(self) -> None:
        self.added_analysis: SupplementAnalysisRun | None = None
        self.added_audits: list[AuditLog] = []
        self.committed = False
        # A real AsyncSession always exposes ``.info``; persist_scope reads it.
        self.info: dict[str, object] = {}

    async def flush(self) -> None:
        """No-op flush (persist_scope flushes pending writes)."""

    async def rollback(self) -> None:
        """No-op rollback (persist_scope own-mode rolls back on exception)."""

    def begin(self) -> _TransactionContext:
        """Return a fake transaction context.

        Returns:
            Fake transaction context.
        """
        return _TransactionContext()

    async def execute(self, *_args: object, **_kwargs: object) -> None:
        """No-op execute for the route-owned RLS set_config statements.

        Returns:
            None.
        """

    def in_transaction(self) -> bool:
        """Return whether the fake session has an active implicit transaction.

        Returns:
            False because these tests do not model SQLAlchemy's implicit read transaction.
        """
        return False

    async def scalar(self, _statement: object) -> SupplementAnalysisRun | None:
        """Return the analysis row added by intake.

        Args:
            _statement: SQLAlchemy select statement.

        Returns:
            Stored supplement analysis row.
        """
        return self.added_analysis

    def add(self, record: object) -> None:
        """Capture ORM records passed by services.

        Args:
            record: ORM object.
        """
        if isinstance(record, SupplementAnalysisRun):
            self.added_analysis = record
            return
        if isinstance(record, AuditLog):
            self.added_audits.append(record)

    async def refresh(self, record: object) -> None:
        """Populate generated fields on fake records.

        Args:
            record: ORM object to refresh.
        """
        supplement_run = cast(SupplementAnalysisRun, record)
        if getattr(supplement_run, "id", None) is None:
            supplement_run.id = uuid4()
        supplement_run.created_at = datetime.now(UTC)
        supplement_run.updated_at = datetime.now(UTC)

    async def commit(self) -> None:
        """Record that a commit occurred."""
        self.committed = True


class _FakeGoogleVisionOCRAdapter(OCRAdapter):
    """Fake Google Vision adapter for route tests."""

    def __init__(self, text: str = "비타민 D 1000\nVitamin D 25 ug", *, fail: bool = False) -> None:
        self.text = text
        self.fail = fail
        self.call_count = 0
        self.received_image: OCRImageInput | None = None

    async def extract_text(self, image: OCRImageInput) -> OCRResult:
        """Return fake OCR text or raise a provider error.

        Args:
            image: OCR image input.

        Returns:
            Fake OCR result.

        Raises:
            OCRError: When configured to fail.
        """
        self.call_count += 1
        self.received_image = image
        if self.fail:
            raise OCRError("fake Google Vision failure")
        return OCRResult(text=self.text, provider="google_vision_document", confidence=0.91)


class _FakeParser:
    """Fake structured parser used after OCR succeeds."""

    def __init__(self) -> None:
        self.received_text: str | None = None

    async def parse_supplement_ocr_text(
        self,
        ocr_text: str,
    ) -> SupplementStructuredParseResult:
        """Return a deterministic parser result.

        Args:
            ocr_text: OCR text passed from Google Vision.

        Returns:
            Structured parser result.
        """
        self.received_text = ocr_text
        return SupplementStructuredParseResult.model_validate(
            {
                "parsed_product": {"product_name": "비타민 D 1000"},
                "ingredient_candidates": [
                    {
                        "display_name": "비타민 D",
                        "amount": 25,
                        "unit": "ug",
                        "confidence": 0.91,
                    }
                ],
                "low_confidence_fields": [],
                "warnings": [],
            }
        )


def _png_bytes() -> bytes:
    """Return a tiny PNG image.

    Returns:
        PNG image bytes.
    """
    buffer = BytesIO()
    Image.new("RGB", (3, 2), color=(255, 255, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def _session_dependency(
    fake_session: _FakeSupplementSession,
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


def _google_vision_settings() -> Settings:
    """Return Google Vision enabled local settings.

    Returns:
        Settings object.
    """
    return Settings(
        _env_file=None,
        ocr_primary_provider="google_vision",
        allow_external_ocr=True,
        google_cloud_api_key=SecretStr("test-key"),
    )


def _client(
    *,
    fake_session: _FakeSupplementSession,
    settings: Settings,
    adapters: SupplementImageAnalysisAdapters,
) -> TestClient:
    """Build a TestClient with fake DB and OCR dependencies.

    Args:
        fake_session: Fake async session.
        settings: Runtime settings.
        adapters: Fake analysis adapters.

    Returns:
        Test client.
    """
    app = create_app(settings=settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_async_session] = _session_dependency(fake_session)
    app.dependency_overrides[supplements.get_supplement_image_analysis_adapters] = lambda: adapters
    return TestClient(app)


def test_analyze_supplement_label_runs_google_vision_ocr_and_parser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify OCR and parser run together when both OCR consents are granted."""
    fake_session = _FakeSupplementSession()
    fake_ocr = _FakeGoogleVisionOCRAdapter()
    fake_parser = _FakeParser()
    seen_consents: list[ConsentType] = []

    async def allow_consent(*args: object, **_kwargs: object) -> None:
        """Capture consent checks and allow them."""
        seen_consents.append(cast(ConsentType, args[2]))

    monkeypatch.setattr(supplements, "require_user_consent", allow_consent)
    client = _client(
        fake_session=fake_session,
        settings=_google_vision_settings(),
        adapters=SupplementImageAnalysisAdapters(ocr=fake_ocr, parser=fake_parser),
    )

    response = client.post(
        "/api/v1/supplements/analyze",
        files={"image": ("label.png", _png_bytes(), "image/png")},
    )

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert seen_consents == [
        ConsentType.OCR_IMAGE_PROCESSING,
        ConsentType.EXTERNAL_OCR_PROCESSING,
    ]
    assert fake_ocr.call_count == 1
    assert fake_parser.received_text == "비타민 D 1000\nVitamin D 25 μg"
    assert fake_session.added_analysis is not None
    assert fake_session.added_analysis.ocr_provider == "google_vision_document"
    assert fake_session.added_analysis.ocr_text_hash is not None
    assert "Vitamin D 25 ug" not in str(fake_session.added_analysis.parsed_snapshot)
    body = response.json()
    assert body["parsed_product"]["product_name"] == "비타민 D 1000"
    assert body["ingredient_candidates"][0]["display_name"] == "비타민 D"
    audit_actions = [audit.action for audit in fake_session.added_audits]
    assert "supplement_ocr_provider_completed" in audit_actions


def test_analyze_supplement_label_requires_external_ocr_consent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify Google Vision is not called when external OCR consent is missing."""
    fake_session = _FakeSupplementSession()
    fake_ocr = _FakeGoogleVisionOCRAdapter()

    async def deny_external_consent(*args: object, **_kwargs: object) -> None:
        """Deny only the external OCR consent bucket."""
        consent_type = cast(ConsentType, args[2])
        if consent_type == ConsentType.EXTERNAL_OCR_PROCESSING:
            raise ConsentRequiredError("external OCR consent is required.")

    monkeypatch.setattr(supplements, "require_user_consent", deny_external_consent)
    monkeypatch.setattr(supplements, "record_sensitive_audit_event", _record_noop_audit)
    client = _client(
        fake_session=fake_session,
        settings=_google_vision_settings(),
        adapters=SupplementImageAnalysisAdapters(ocr=fake_ocr, parser=_FakeParser()),
    )

    response = client.post(
        "/api/v1/supplements/analyze",
        files={"image": ("label.png", _png_bytes(), "image/png")},
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"]["required_consents"] == ["external_ocr_processing"]
    assert fake_ocr.call_count == 0
    assert fake_session.added_analysis is None


def test_analyze_supplement_label_degrades_when_google_vision_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify provider failures return an intake-only preview with safe warnings."""
    fake_session = _FakeSupplementSession()
    fake_ocr = _FakeGoogleVisionOCRAdapter(fail=True)

    async def allow_consent(*_args: object, **_kwargs: object) -> None:
        """Allow every consent bucket."""

    monkeypatch.setattr(supplements, "require_user_consent", allow_consent)
    client = _client(
        fake_session=fake_session,
        settings=_google_vision_settings(),
        adapters=SupplementImageAnalysisAdapters(ocr=fake_ocr, parser=_FakeParser()),
    )

    response = client.post(
        "/api/v1/supplements/analyze",
        files={"image": ("label.png", _png_bytes(), "image/png")},
    )

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert fake_ocr.call_count == 1
    assert fake_session.added_analysis is not None
    assert fake_session.added_analysis.ocr_text_hash is None
    assert fake_session.added_analysis.parsed_snapshot["ingredient_candidates"] == []
    assert any("Automatic text extraction" in warning for warning in response.json()["warnings"])
    audit = next(
        item
        for item in fake_session.added_audits
        if item.action == "supplement_ocr_provider_failed"
    )
    assert audit.event_metadata == {
        "ocr_provider": None,
        "ocr_confidence_present": False,
        "warning_codes": ["automatic_ocr_unavailable"],
        "raw_image_stored": False,
        "raw_ocr_text_stored": False,
    }


async def _record_noop_audit(*_args: object, **_kwargs: object) -> None:
    """No-op audit writer for consent-block tests."""
