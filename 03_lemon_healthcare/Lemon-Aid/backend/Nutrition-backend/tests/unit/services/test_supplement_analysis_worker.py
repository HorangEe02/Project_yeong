"""Async supplement analysis worker tests."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Self, cast
from uuid import uuid4

import pytest
from PIL import Image
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from src.config import Settings
from src.models.db.supplement import SupplementAnalysisRun
from src.models.schemas.supplement import SupplementAnalysisStatus
from src.security.auth import AuthenticatedUser
from src.services import supplement_analysis_worker
from src.services.supplement_analysis_worker import (
    ANALYSIS_FAILED_WARNING,
    CapturedImage,
    CapturedRequest,
    reconstruct_upload_file,
    run_single_supplement_analysis_job,
)
from src.services.supplement_image_analysis import SupplementImageAnalysisAdapters


def _png_bytes() -> bytes:
    """Return a tiny PNG image."""
    buffer = BytesIO()
    Image.new("RGB", (3, 2), color=(255, 255, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def _user() -> AuthenticatedUser:
    """Return a deterministic authenticated owner for worker tests."""
    return AuthenticatedUser(issuer="local-development", subject="local-dev-user", scopes=())


def _settings() -> Settings:
    """Return hermetic settings for worker tests."""
    return Settings(
        privacy_hash_secret=SecretStr("test-privacy-secret"),
        supplement_analyze_async_enabled=True,
    )


def _processing_run() -> SupplementAnalysisRun:
    """Return a pre-created run in ``processing`` status."""
    now = datetime.now(UTC)
    return SupplementAnalysisRun(
        id=uuid4(),
        owner_subject="local-development::local-dev-user",
        client_request_id="abc:client-1",
        status=SupplementAnalysisStatus.PROCESSING.value,
        image_sha256="a" * 64,
        image_mime_type="image/png",
        image_size_bytes=128,
        ocr_provider="intake-only",
        parsed_snapshot={"parsed_product": {}, "ingredient_candidates": []},
        match_snapshot={"matched_product_candidates": []},
        warnings=[],
        algorithm_version="supplement-intake-v1.0.0",
        expires_at=now + timedelta(minutes=30),
        created_at=now,
        updated_at=now,
    )


class _TransactionContext:
    """Async context manager used by the fake session transaction."""

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        return None


class _FakeWorkerSession:
    """Fake async session for worker job tests."""

    def __init__(self, record: SupplementAnalysisRun) -> None:
        self.record = record
        self.info: dict[str, object] = {}
        self.committed = False

    async def flush(self) -> None:
        return None

    async def rollback(self) -> None:
        return None

    def begin(self) -> _TransactionContext:
        return _TransactionContext()

    async def execute(self, *_args: object, **_kwargs: object) -> None:
        return None

    def in_transaction(self) -> bool:
        return False

    async def get(self, _entity: object, ident: object) -> SupplementAnalysisRun | None:
        return self.record if ident == self.record.id else None

    async def refresh(self, _record: object) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


class _FakeSessionContext:
    """Async context manager yielding a pre-built fake session."""

    def __init__(self, session: _FakeWorkerSession) -> None:
        self._session = session

    async def __aenter__(self) -> _FakeWorkerSession:
        return self._session

    async def __aexit__(self, *_exc_info: object) -> bool:
        return False


class _FakeSessionFactory:
    """Callable session factory returning one fixed fake session per call."""

    def __init__(self, session: _FakeWorkerSession) -> None:
        self._session = session

    def __call__(self) -> _FakeSessionContext:
        return _FakeSessionContext(self._session)


def _captured() -> CapturedImage:
    """Return a captured single image payload."""
    run_id = uuid4()
    return CapturedImage(
        analysis_id=run_id,
        client_request_id="client-1",
        image_bytes=_png_bytes(),
        content_type="image/png",
        filename="label.png",
    )


def _request_snapshot() -> CapturedRequest:
    """Return a request metadata snapshot for worker audits."""
    return CapturedRequest.from_request("203.0.113.1", {"user-agent": "pytest"})


@pytest.fixture(autouse=True)
def _silence_worker_audits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the out-of-band audit writer so no real audit engine is opened."""

    async def _noop_audit(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(supplement_analysis_worker, "record_sensitive_audit_event", _noop_audit)


def test_reconstruct_upload_file_preserves_content_type_and_filename() -> None:
    """Verify the rebuilt UploadFile exposes the captured content type + name."""
    upload = reconstruct_upload_file(_captured())
    assert upload.content_type == "image/png"
    assert upload.filename == "label.png"


def test_run_single_job_flips_processing_to_ready_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The worker flips a processing row to requires_confirmation on success."""
    record = _processing_run()
    captured = _captured()
    captured = CapturedImage(
        analysis_id=record.id,
        client_request_id=captured.client_request_id,
        image_bytes=captured.image_bytes,
        content_type=captured.content_type,
        filename=captured.filename,
    )
    fake_session = _FakeWorkerSession(record)

    class _Result:
        def __init__(self, run: SupplementAnalysisRun) -> None:
            self.record = run
            self.learning_artifacts = None
            self.ocr_attempted = False
            self.ocr_result = None
            self.ocr_warning_codes: tuple[str, ...] = ()
            self.reused_existing = False
            self.parser_used = False
            self.vision_region = None

            class _Meta:
                mime_type = "image/png"
                size_bytes = 128

            self.image_metadata = _Meta()

    async def _fake_analyze(**_kwargs: object) -> _Result:
        # Pipeline writes happen here; the record is the pre-created processing row.
        return _Result(record)

    monkeypatch.setattr(supplement_analysis_worker, "analyze_supplement_image", _fake_analyze)

    asyncio.run(
        run_single_supplement_analysis_job(
            analysis_id=record.id,
            captured=captured,
            user=_user(),
            settings=_settings(),
            adapters=SupplementImageAnalysisAdapters(),
            http_request=_request_snapshot(),
            session_factory=cast(
                async_sessionmaker[AsyncSession], _FakeSessionFactory(fake_session)
            ),
        )
    )

    assert record.status == SupplementAnalysisStatus.REQUIRES_CONFIRMATION.value


def test_run_single_job_flips_processing_to_failed_on_pipeline_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A raised pipeline error rolls back and flips the row to failed safely."""
    record = _processing_run()
    captured = CapturedImage(
        analysis_id=record.id,
        client_request_id="client-1",
        image_bytes=_png_bytes(),
        content_type="image/png",
        filename="label.png",
    )
    fake_session = _FakeWorkerSession(record)

    async def _raising_analyze(**_kwargs: object) -> object:
        raise RuntimeError("simulated pipeline failure with secret 12345")

    monkeypatch.setattr(supplement_analysis_worker, "analyze_supplement_image", _raising_analyze)

    asyncio.run(
        run_single_supplement_analysis_job(
            analysis_id=record.id,
            captured=captured,
            user=_user(),
            settings=_settings(),
            adapters=SupplementImageAnalysisAdapters(),
            http_request=_request_snapshot(),
            session_factory=cast(
                async_sessionmaker[AsyncSession], _FakeSessionFactory(fake_session)
            ),
        )
    )

    assert record.status == SupplementAnalysisStatus.FAILED.value
    # Only a safe coded warning is stored — never the raw exception text.
    assert record.warnings == [ANALYSIS_FAILED_WARNING]
    assert all("secret" not in warning for warning in record.warnings)
