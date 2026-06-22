"""Supplement analyze default-path tests with PaddleOCR as the primary OCR."""

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
from src.api.v1 import supplements
from src.config import Settings, get_settings
from src.db.dependencies import get_async_session
from src.main import create_app
from src.models.db.privacy import AuditLog
from src.models.db.supplement import SupplementAnalysisRun
from src.models.schemas.privacy import ConsentType
from src.models.schemas.supplement_parser import SupplementStructuredParseResult
from src.ocr.base import OCRAdapter, OCRImageInput, OCRResult
from src.ocr.providers.paddle import PADDLE_OCR_PROVIDER
from src.services.supplement_image_analysis import SupplementImageAnalysisAdapters


@pytest.fixture(autouse=True)
def _capture_supplement_audits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Capture out-of-band audits into the fake session (ambient-tx Step 7).

    The analyze route adopted a route-owned RLS transaction, so
    ``record_sensitive_audit_event`` runs out-of-band on a privileged session the
    fake cannot observe. Capture the call args into the fake's ``added_audits`` so
    no real audit connection opens during these fake-session route tests.
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
    """Fake async session for PaddleOCR route tests."""

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


class _FakePaddleOCRAdapter(OCRAdapter):
    """Fake PaddleOCR adapter for route tests."""

    def __init__(self, text: str = "비타민 D 1000\nVitamin D 25 ug") -> None:
        self.text = text
        self.call_count = 0
        self.received_image: OCRImageInput | None = None

    async def extract_text(self, image: OCRImageInput) -> OCRResult:
        """Return fake OCR text matching the PaddleOCR provider key.

        Args:
            image: OCR image input.

        Returns:
            Fake OCR result tagged with the PaddleOCR provider identifier.
        """
        self.call_count += 1
        self.received_image = image
        return OCRResult(text=self.text, provider=PADDLE_OCR_PROVIDER, confidence=0.88)


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
            ocr_text: OCR text passed from PaddleOCR.

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
                        "confidence": 0.88,
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


def _paddleocr_default_settings() -> Settings:
    """Return settings exercising the PaddleOCR default path.

    Returns:
        Settings object.
    """
    return Settings(_env_file=None)


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


def test_analyze_supplement_label_runs_paddleocr_default_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the default PaddleOCR pipeline runs without external OCR consent."""
    fake_session = _FakeSupplementSession()
    fake_ocr = _FakePaddleOCRAdapter()
    fake_parser = _FakeParser()
    seen_consents: list[ConsentType] = []

    async def allow_consent(*args: object, **_kwargs: object) -> None:
        """Capture consent checks and allow them."""
        seen_consents.append(cast(ConsentType, args[2]))

    monkeypatch.setattr(supplements, "require_user_consent", allow_consent)
    settings = _paddleocr_default_settings()
    assert settings.ocr_primary_provider == "paddleocr"

    client = _client(
        fake_session=fake_session,
        settings=settings,
        adapters=SupplementImageAnalysisAdapters(ocr=fake_ocr, parser=fake_parser),
    )

    response = client.post(
        "/api/v1/supplements/analyze",
        files={"image": ("label.png", _png_bytes(), "image/png")},
    )

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert seen_consents == [ConsentType.OCR_IMAGE_PROCESSING]
    assert fake_ocr.call_count == 1
    assert fake_parser.received_text == "비타민 D 1000\nVitamin D 25 μg"
    assert fake_session.added_analysis is not None
    assert fake_session.added_analysis.ocr_provider == PADDLE_OCR_PROVIDER
    body = response.json()
    assert body["parsed_product"]["product_name"] == "비타민 D 1000"
    assert body["ingredient_candidates"][0]["display_name"] == "비타민 D"
    assert body["pipeline_metadata"]["ocr_provider"] == PADDLE_OCR_PROVIDER
    assert body["pipeline_metadata"]["vision_roi_used"] is False
    assert body["pipeline_metadata"]["llm_parser_used"] is True
    # Backward compatible: recommendation is absent (None) unless opted in.
    assert body.get("recommendation") is None


def test_analyze_supplement_label_with_recommendation_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """with_recommendation=true bundles a safe recommendation in one response (single-flow)."""
    fake_session = _FakeSupplementSession()
    fake_ocr = _FakePaddleOCRAdapter()
    fake_parser = _FakeParser()

    async def allow_consent(*_args: object, **_kwargs: object) -> None:
        """Allow all consent checks."""

    monkeypatch.setattr(supplements, "require_user_consent", allow_consent)
    settings = _paddleocr_default_settings()

    client = _client(
        fake_session=fake_session,
        settings=settings,
        adapters=SupplementImageAnalysisAdapters(ocr=fake_ocr, parser=fake_parser),
    )

    response = client.post(
        "/api/v1/supplements/analyze",
        params={"with_recommendation": "true"},
        files={"image": ("label.png", _png_bytes(), "image/png")},
    )

    assert response.status_code == status.HTTP_202_ACCEPTED
    body = response.json()
    # Preview fields stay at the top level (backward-compatible superset model).
    assert body["parsed_product"]["product_name"] == "비타민 D 1000"
    # Bundled recommendation is present with the mandatory consult-a-doctor disclaimer.
    assert body["recommendation"] is not None
    assert "상담" in body["recommendation"]["clinical_disclaimer"]
