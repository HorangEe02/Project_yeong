"""Async (202 + poll) supplement analysis route tests."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from io import BytesIO
from types import SimpleNamespace
from typing import Self, cast
from uuid import UUID, uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import SecretStr
from src.api.v1 import supplements
from src.config import Settings, get_settings
from src.db.dependencies import get_async_session, get_rls_context_session
from src.main import create_app
from src.models.db.privacy import AuditLog
from src.models.db.supplement import SupplementAnalysisRun
from src.models.schemas.supplement import SupplementAnalysisStatus
from src.services.supplement_image_analysis import SupplementImageAnalysisAdapters

OWNER_SUBJECT = "local-development::local-dev-user"


@pytest.fixture(autouse=True)
def _capture_supplement_audits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Capture out-of-band audits into the fake session for assertion."""

    async def _capture(session: object, _current_user: object, **kwargs: object) -> None:
        audits = getattr(session, "added_audits", None)
        if audits is not None:
            audits.append(SimpleNamespace(**kwargs))

    monkeypatch.setattr(supplements, "record_sensitive_audit_event", _capture)


@pytest.fixture(autouse=True)
def _no_real_worker(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    """Replace the worker spawn so the detached pipeline never actually runs.

    Returns:
        A list capturing the scheduled worker coroutines (closed without await).
    """
    spawned: list[dict[str, object]] = []

    def _fake_spawn(coro: object) -> None:
        spawned.append({"coro": coro})
        # Close the un-awaited coroutine to avoid a RuntimeWarning.
        close = getattr(coro, "close", None)
        if callable(close):
            close()

    monkeypatch.setattr(supplements, "_spawn_analysis_worker", _fake_spawn)
    return spawned


class _TransactionContext:
    """Async context manager used by the fake session transaction."""

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        return None


class _FakeScalarResult:
    """Minimal scalar result wrapper for fake async session queries."""

    def __init__(self, rows: list[SupplementAnalysisRun]) -> None:
        self._rows = rows

    def all(self) -> list[SupplementAnalysisRun]:
        return list(self._rows)


class _FakeSupplementSession:
    """Fake async session for async supplement analysis route tests."""

    def __init__(
        self,
        *,
        existing: SupplementAnalysisRun | None = None,
        poll_record: SupplementAnalysisRun | None = None,
        group_runs: list[SupplementAnalysisRun] | None = None,
    ) -> None:
        self.existing = existing
        self.poll_record = poll_record
        self.group_runs = group_runs or []
        self.added_analysis: SupplementAnalysisRun | None = None
        self.added_analyses: list[SupplementAnalysisRun] = []
        self.added_audits: list[AuditLog] = []
        self.committed = False
        self.info: dict[str, object] = {}

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

    async def scalar(self, statement: object) -> SupplementAnalysisRun | None:
        try:
            bound_values = set(statement.compile().params.values())  # type: ignore[attr-defined]
        except Exception:
            bound_values = set()
        for run in self.added_analyses:
            if run.id is not None and run.id in bound_values:
                return run
        return self.existing

    async def scalars(self, _statement: object) -> _FakeScalarResult:
        return _FakeScalarResult([*self.group_runs, *self.added_analyses])

    async def get(self, _entity: object, ident: object) -> SupplementAnalysisRun | None:
        if self.poll_record is not None and self.poll_record.id == ident:
            return self.poll_record
        for run in self.added_analyses:
            if run.id == ident:
                return run
        return None

    def add(self, record: object) -> None:
        if isinstance(record, SupplementAnalysisRun):
            self.added_analysis = record
            self.added_analyses.append(record)
            return
        if isinstance(record, AuditLog):
            self.added_audits.append(record)

    async def refresh(self, record: object) -> None:
        run = cast(SupplementAnalysisRun, record)
        run.id = uuid4()
        run.created_at = datetime.now(UTC)
        run.updated_at = datetime.now(UTC)

    async def commit(self) -> None:
        self.committed = True


def _png_bytes() -> bytes:
    """Return a tiny PNG image."""
    buffer = BytesIO()
    Image.new("RGB", (3, 2), color=(255, 255, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def _run(
    *,
    run_status: str = SupplementAnalysisStatus.REQUIRES_CONFIRMATION.value,
    owner_subject: str = OWNER_SUBJECT,
    updated_at: datetime | None = None,
    warnings: list[str] | None = None,
    group_id: str | None = None,
) -> SupplementAnalysisRun:
    """Return a supplement analysis run fixture in the requested status."""
    now = datetime.now(UTC)
    snapshot: dict[str, object] = {"parsed_product": {}, "ingredient_candidates": []}
    if group_id is not None:
        snapshot["multi_image_group_id"] = group_id
        snapshot["image_role"] = "front_label"
    return SupplementAnalysisRun(
        id=uuid4(),
        owner_subject=owner_subject,
        client_request_id="abc:client-1",
        status=run_status,
        image_sha256="a" * 64,
        image_mime_type="image/png",
        image_size_bytes=128,
        ocr_provider="intake-only",
        parsed_snapshot=snapshot,
        match_snapshot={"matched_product_candidates": []},
        warnings=warnings or [],
        algorithm_version="supplement-intake-v1.0.0",
        expires_at=now + timedelta(minutes=30),
        created_at=now,
        updated_at=updated_at or now,
    )


def _session_dependency(
    fake_session: _FakeSupplementSession,
) -> Callable[[], AsyncIterator[object]]:
    """Build a FastAPI dependency override yielding a fake session."""

    async def dependency() -> AsyncIterator[object]:
        yield fake_session

    return dependency


async def _allow_consent(*_args: object, **_kwargs: object) -> None:
    """No-op consent dependency for route tests."""


def _async_settings() -> Settings:
    """Return settings with the async analyze flag enabled."""
    return Settings(
        privacy_hash_secret=SecretStr("test-privacy-secret"),
        supplement_analyze_async_enabled=True,
    )


def _empty_analysis_adapters() -> SupplementImageAnalysisAdapters:
    """Return an adapter bundle with OCR intentionally disabled for route tests."""
    return SupplementImageAnalysisAdapters()


def _build_app(
    fake_session: _FakeSupplementSession,
    settings: Settings,
) -> TestClient:
    """Build a TestClient with the fake session + settings wired in."""
    app = create_app(settings=settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_async_session] = _session_dependency(fake_session)
    app.dependency_overrides[get_rls_context_session] = _session_dependency(fake_session)
    app.dependency_overrides[supplements.get_supplement_image_analysis_adapters] = (
        _empty_analysis_adapters
    )
    return TestClient(app)


def test_analyze_async_returns_202_accepted_with_processing_status(
    monkeypatch: pytest.MonkeyPatch,
    _no_real_worker: list[dict[str, object]],
) -> None:
    """With the flag on, submit returns 202 processing + analysis_id, no preview."""
    fake_session = _FakeSupplementSession()
    monkeypatch.setattr(supplements, "require_user_consent", _allow_consent)
    client = _build_app(fake_session, _async_settings())

    response = client.post(
        "/api/v1/supplements/analyze",
        files={"image": ("label.png", _png_bytes(), "image/png")},
        data={"client_request_id": "client-1"},
    )

    assert response.status_code == status.HTTP_202_ACCEPTED
    body = response.json()
    assert body["status"] == "processing"
    UUID(body["analysis_id"])  # well-formed id
    assert body["poll_url"] == f"/api/v1/supplements/analyses/{body['analysis_id']}"
    assert "preview" not in body
    # The run was created in processing status and exactly one worker scheduled.
    assert fake_session.added_analysis is not None
    assert fake_session.added_analysis.status == SupplementAnalysisStatus.PROCESSING.value
    assert len(_no_real_worker) == 1


def test_analyze_multi_async_returns_202_group_accepted(
    monkeypatch: pytest.MonkeyPatch,
    _no_real_worker: list[dict[str, object]],
) -> None:
    """Multi submit returns 202 with a group id + per-image analysis ids."""
    fake_session = _FakeSupplementSession()
    monkeypatch.setattr(supplements, "require_user_consent", _allow_consent)
    client = _build_app(fake_session, _async_settings())

    response = client.post(
        "/api/v1/supplements/analyze-multi",
        files=[
            ("images", ("front.png", _png_bytes(), "image/png")),
            ("images", ("facts.png", _png_bytes(), "image/png")),
        ],
        data={"image_roles": ["front_label", "supplement_facts"]},
    )

    assert response.status_code == status.HTTP_202_ACCEPTED
    body = response.json()
    assert body["status"] == "processing"
    assert body["analysis_group_id"].startswith("multi-")
    assert len(body["analysis_ids"]) == 2
    assert body["poll_url"] == (f"/api/v1/supplements/analyses/group/{body['analysis_group_id']}")
    assert len(fake_session.added_analyses) == 2
    assert all(
        run.status == SupplementAnalysisStatus.PROCESSING.value
        for run in fake_session.added_analyses
    )
    assert len(_no_real_worker) == 1


def test_poll_returns_processing_then_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    """Poll reports processing for a processing row and the preview when ready."""
    processing = _run(run_status=SupplementAnalysisStatus.PROCESSING.value)
    fake_session = _FakeSupplementSession(poll_record=processing)
    monkeypatch.setattr(supplements, "require_user_consent", _allow_consent)
    client = _build_app(fake_session, _async_settings())

    processing_response = client.get(f"/api/v1/supplements/analyses/{processing.id}")
    assert processing_response.status_code == status.HTTP_200_OK
    body = processing_response.json()
    assert body["status"] == "processing"
    assert body["preview"] is None
    assert body["error"] is None

    # Flip to ready and poll again.
    processing.status = SupplementAnalysisStatus.REQUIRES_CONFIRMATION.value
    ready_response = client.get(f"/api/v1/supplements/analyses/{processing.id}")
    assert ready_response.status_code == status.HTTP_200_OK
    ready_body = ready_response.json()
    assert ready_body["status"] == "requires_confirmation"
    assert ready_body["preview"] is not None
    assert ready_body["preview"]["analysis_id"] == str(processing.id)
    assert ready_body["error"] is None


def test_poll_returns_failed_with_safe_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed row surfaces a safe coded error and no preview."""
    failed = _run(
        run_status=SupplementAnalysisStatus.FAILED.value,
        warnings=["analysis_failed"],
    )
    fake_session = _FakeSupplementSession(poll_record=failed)
    monkeypatch.setattr(supplements, "require_user_consent", _allow_consent)
    client = _build_app(fake_session, _async_settings())

    response = client.get(f"/api/v1/supplements/analyses/{failed.id}")
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["status"] == "failed"
    assert body["preview"] is None
    assert body["error"]["code"] == "analysis_failed"


def test_poll_stale_processing_reports_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """A processing row past the worker deadline is reported as a coded timeout."""
    settings = _async_settings()
    stale_age = settings.supplement_analyze_worker_deadline_sec + 60
    stale = _run(
        run_status=SupplementAnalysisStatus.PROCESSING.value,
        updated_at=datetime.now(UTC) - timedelta(seconds=stale_age),
    )
    fake_session = _FakeSupplementSession(poll_record=stale)
    monkeypatch.setattr(supplements, "require_user_consent", _allow_consent)
    client = _build_app(fake_session, settings)

    response = client.get(f"/api/v1/supplements/analyses/{stale.id}")
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["status"] == "failed"
    assert body["error"]["code"] == "analysis_timeout"


def test_poll_owner_isolation_returns_404_for_foreign_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A run owned by a different subject is not readable via the poll route."""
    foreign = _run(owner_subject="local-development::someone-else")
    fake_session = _FakeSupplementSession(poll_record=foreign)
    monkeypatch.setattr(supplements, "require_user_consent", _allow_consent)
    client = _build_app(fake_session, _async_settings())

    response = client.get(f"/api/v1/supplements/analyses/{foreign.id}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_poll_unknown_run_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unknown analysis id returns 404."""
    fake_session = _FakeSupplementSession(poll_record=None)
    monkeypatch.setattr(supplements, "require_user_consent", _allow_consent)
    client = _build_app(fake_session, _async_settings())

    response = client.get(f"/api/v1/supplements/analyses/{uuid4()}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_group_poll_aggregates_processing_then_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Group poll is processing while any row processes, ready when all are ready."""
    group_id = "multi-aggregate"
    run_one = _run(run_status=SupplementAnalysisStatus.PROCESSING.value, group_id=group_id)
    run_two = _run(
        run_status=SupplementAnalysisStatus.REQUIRES_CONFIRMATION.value, group_id=group_id
    )
    fake_session = _FakeSupplementSession(group_runs=[run_one, run_two])
    monkeypatch.setattr(supplements, "require_user_consent", _allow_consent)
    client = _build_app(fake_session, _async_settings())

    processing_response = client.get(f"/api/v1/supplements/analyses/group/{group_id}")
    assert processing_response.status_code == status.HTTP_200_OK
    assert processing_response.json()["status"] == "processing"

    run_one.status = SupplementAnalysisStatus.REQUIRES_CONFIRMATION.value
    ready_response = client.get(f"/api/v1/supplements/analyses/group/{group_id}")
    assert ready_response.status_code == status.HTTP_200_OK
    ready_body = ready_response.json()
    assert ready_body["status"] == "requires_confirmation"
    assert ready_body["preview"] is not None
    assert ready_body["preview"]["analysis_group_id"] == group_id


def test_group_poll_unknown_group_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty group returns 404."""
    fake_session = _FakeSupplementSession(group_runs=[])
    monkeypatch.setattr(supplements, "require_user_consent", _allow_consent)
    client = _build_app(fake_session, _async_settings())

    response = client.get("/api/v1/supplements/analyses/group/multi-missing")
    assert response.status_code == status.HTTP_404_NOT_FOUND
