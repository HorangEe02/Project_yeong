"""Supplement image intake API tests."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
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
from src.db.dependencies import get_async_session, get_rls_context_session
from src.main import create_app
from src.models.db.privacy import AuditLog
from src.models.db.supplement import SupplementAnalysisRun
from src.models.schemas.privacy import ConsentType
from src.models.schemas.supplement import SupplementAnalysisStatus
from src.models.schemas.supplement_parser import SupplementStructuredParseResult
from src.ocr.base import OCRAdapter, OCRImageInput, OCRResult
from src.services.privacy import ConsentRequiredError
from src.services.supplement_image_analysis import SupplementImageAnalysisAdapters


@pytest.fixture(autouse=True)
def _capture_supplement_audits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Capture out-of-band audits into the fake session for assertion.

    The orchestrator routes adopted a route-owned RLS transaction
    (ambient-tx Step 7), so ``record_sensitive_audit_event`` runs out-of-band on a
    privileged session that the fake cannot observe. Capture the call args into the
    fake's ``added_audits`` so the audit assertions keep working and no real audit
    connection is opened during these fake-session route tests. Tests that override
    this with their own ``record_sensitive_audit_event`` patch still win (the later
    monkeypatch takes precedence).
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

        Returns:
            None.
        """


class _FakeScalarResult:
    """Minimal scalar result wrapper for fake async session queries."""

    def __init__(self, rows: list[SupplementAnalysisRun]) -> None:
        """Store rows for later ``all`` retrieval.

        Args:
            rows: Supplement analysis rows returned by a fake query.
        """
        self._rows = rows

    def all(self) -> list[SupplementAnalysisRun]:
        """Return all fake rows.

        Returns:
            Stored supplement analysis rows.
        """
        return list(self._rows)


class _FakeSupplementSession:
    """Fake async session for supplement intake route tests."""

    def __init__(
        self,
        existing: SupplementAnalysisRun | None = None,
        finalize_runs: list[SupplementAnalysisRun] | None = None,
    ) -> None:
        self.existing = existing
        self.finalize_runs = finalize_runs or []
        self.added_analysis: SupplementAnalysisRun | None = None
        self.added_analyses: list[SupplementAnalysisRun] = []
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
            Fake async transaction context.
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

    async def scalar(self, statement: object) -> SupplementAnalysisRun | None:
        """Return the row a service expects from a select.

        Intake idempotency lookups (filtered by ``client_request_id``) get the
        configured ``existing`` row, while the parser's by-id lookup gets the
        matching just-added run so routes exercising real OCR/parse adapters work
        end-to-end against the fake session.

        Args:
            statement: SQLAlchemy select statement.

        Returns:
            Matching supplement analysis run, the configured existing row, or None.
        """
        try:
            bound_values = set(statement.compile().params.values())  # type: ignore[attr-defined]
        except Exception:  # defensive: opaque fake statements never fail to compile
            bound_values = set()
        for run in self.added_analyses:
            if run.id is not None and run.id in bound_values:
                return run
        return self.existing

    async def scalars(self, _statement: object) -> _FakeScalarResult:
        """Return fake rows for analysis-session lookups.

        Args:
            _statement: SQLAlchemy select statement.

        Returns:
            Fake scalar result with configured finalize rows.
        """
        return _FakeScalarResult([*self.finalize_runs, *self.added_analyses])

    def add(self, record: object) -> None:
        """Capture ORM records passed by route services.

        Args:
            record: ORM object passed by a service.

        Returns:
            None.
        """
        if isinstance(record, SupplementAnalysisRun):
            self.added_analysis = record
            self.added_analyses.append(record)
            return
        if isinstance(record, AuditLog):
            self.added_audits.append(record)

    async def refresh(self, record: object) -> None:
        """Populate server-generated fields after fake persistence.

        Args:
            record: ORM object to refresh.

        Returns:
            None.
        """
        supplement_run = cast(SupplementAnalysisRun, record)
        supplement_run.id = uuid4()
        supplement_run.created_at = datetime.now(UTC)
        supplement_run.updated_at = datetime.now(UTC)

    async def commit(self) -> None:
        """Record an audit commit.

        Returns:
            None.
        """
        self.committed = True


def _png_bytes() -> bytes:
    """Return a tiny PNG image.

    Returns:
        PNG image bytes.
    """
    buffer = BytesIO()
    Image.new("RGB", (3, 2), color=(255, 255, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def _existing_run(image_sha256: str = "a" * 64) -> SupplementAnalysisRun:
    """Return an existing supplement analysis run fixture.

    Args:
        image_sha256: Stored image hash.

    Returns:
        Existing supplement analysis run.
    """
    now = datetime.now(UTC)
    return SupplementAnalysisRun(
        id=uuid4(),
        owner_subject="local-development::local-dev-user",
        client_request_id="client-1",
        status=SupplementAnalysisStatus.REQUIRES_CONFIRMATION.value,
        image_sha256=image_sha256,
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


def _multi_image_run(
    *,
    group_id: str,
    image_role: str,
    parsed_snapshot: dict[str, object],
    image_sha256: str,
) -> SupplementAnalysisRun:
    """Return a grouped supplement analysis run fixture.

    Args:
        group_id: Multi-image analysis group id.
        image_role: Role assigned to this image.
        parsed_snapshot: Sanitized parsed snapshot overrides.
        image_sha256: Stored image hash.

    Returns:
        Existing supplement analysis run with safe multi-image metadata.
    """
    record = _existing_run(image_sha256=image_sha256)
    snapshot = {
        "parsed_product": {},
        "ingredient_candidates": [],
        "label_sections": [],
        "evidence_spans": [],
        "multi_image_group_id": group_id,
        "image_role": image_role,
        "pipeline_metadata": {
            "intake_completed": True,
            "image_count": 2,
            "image_role": image_role,
            "ocr_provider": "paddleocr_local",
            "ocr_text_present": True,
            "raw_image_stored": False,
            "raw_ocr_text_stored": False,
        },
    }
    snapshot.update(parsed_snapshot)
    record.client_request_id = f"client-{image_role}"
    record.ocr_provider = "paddleocr_local"
    record.ocr_text_hash = "c" * 64
    record.parsed_snapshot = snapshot
    return record


def _session_dependency(
    fake_session: _FakeSupplementSession,
) -> Callable[[], AsyncIterator[object]]:
    """Build a FastAPI dependency override yielding a fake session.

    Args:
        fake_session: Fake session to yield.

    Returns:
        Dependency callable.
    """

    async def dependency() -> AsyncIterator[object]:
        """Yield the fake session.

        Yields:
            Fake session object.
        """
        yield fake_session

    return dependency


async def _allow_consent(*_args: object, **_kwargs: object) -> None:
    """No-op consent dependency for route tests.

    Args:
        *_args: Positional call arguments.
        **_kwargs: Keyword call arguments.

    Returns:
        None.
    """


async def _deny_consent(*_args: object, **_kwargs: object) -> None:
    """Raise a missing-consent service error.

    Args:
        *_args: Positional call arguments.
        **_kwargs: Keyword call arguments.

    Returns:
        None.

    Raises:
        ConsentRequiredError: Always raised for this test.
    """
    raise ConsentRequiredError("OCR image processing consent is required.")


async def _record_noop_audit(*_args: object, **_kwargs: object) -> None:
    """No-op audit writer for error-path route tests.

    Args:
        *_args: Positional call arguments.
        **_kwargs: Keyword call arguments.

    Returns:
        None.
    """


def _empty_analysis_adapters() -> SupplementImageAnalysisAdapters:
    """Return an adapter bundle with OCR intentionally disabled for route tests.

    Returns:
        Empty supplement image analysis adapter bundle.
    """
    return SupplementImageAnalysisAdapters()


def _settings(
    *,
    supplement_image_max_bytes: int = 5 * 1024 * 1024,
    supplement_image_max_pixels: int = 12_000_000,
    supplement_preview_ttl_minutes: int = 30,
) -> Settings:
    """Return settings for route tests.

    Args:
        supplement_image_max_bytes: Maximum image byte size.
        supplement_image_max_pixels: Maximum decoded image pixels.
        supplement_preview_ttl_minutes: Preview TTL in minutes.

    Returns:
        Settings object.
    """
    return Settings(
        supplement_image_max_bytes=supplement_image_max_bytes,
        supplement_image_max_pixels=supplement_image_max_pixels,
        supplement_preview_ttl_minutes=supplement_preview_ttl_minutes,
        ocr_primary_provider="paddleocr",
        allow_external_ocr=False,
        enable_clova_ocr=False,
        enable_local_ocr=True,
    )


def test_analyze_supplement_label_accepts_valid_png_and_stores_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify supplement analyze performs image intake and returns a preview."""
    fake_session = _FakeSupplementSession()
    monkeypatch.setattr(supplements, "require_user_consent", _allow_consent)
    app = create_app()
    app.dependency_overrides[get_async_session] = _session_dependency(fake_session)
    app.dependency_overrides[get_rls_context_session] = _session_dependency(fake_session)
    app.dependency_overrides[supplements.get_supplement_image_analysis_adapters] = (
        _empty_analysis_adapters
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/supplements/analyze",
        files={"image": ("label.png", _png_bytes(), "image/png")},
        data={"client_request_id": "client-1"},
    )

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert fake_session.added_analysis is not None
    assert fake_session.added_analysis.owner_subject == "local-development::local-dev-user"
    stored_idempotency_key = fake_session.added_analysis.client_request_id
    assert stored_idempotency_key is not None
    prefix, sep, suffix = stored_idempotency_key.partition(":")
    assert sep == ":"
    assert len(prefix) == 16
    assert all(char in "0123456789abcdef" for char in prefix)
    assert suffix == "client-1"
    assert fake_session.added_analysis.ocr_text_hash is None
    assert fake_session.added_analysis.parsed_snapshot["ingredient_candidates"] == []
    assert len(fake_session.added_audits) == 1
    body = response.json()
    assert body["status"] == "requires_confirmation"
    assert body["ingredient_candidates"] == []
    assert body["algorithm_version"] == "supplement-intake-v1.0.0"


def test_analyze_supplement_label_schedules_post_commit_learning_when_gate_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the route schedules learning storage as a post-commit background task.

    Proves the Step 7 Phase 2 wiring: when the image-learning gate passes, the
    route hands the orchestrator's deferred artifacts to
    ``store_supplement_learning_artifacts`` via FastAPI ``BackgroundTasks``. The
    background task runs after the route body (where the intake row is already
    committed inline), so the captured artifacts reference the durable run id.
    """
    fake_session = _FakeSupplementSession()
    monkeypatch.setattr(supplements, "require_user_consent", _allow_consent)

    learning_consents = (
        ConsentType.OCR_IMAGE_PROCESSING,
        ConsentType.DATA_RETENTION,
        ConsentType.IMAGE_LEARNING_DATASET,
    )

    async def _grant_learning_consents(
        *_args: object, **_kwargs: object
    ) -> tuple[ConsentType, ...]:
        return learning_consents

    monkeypatch.setattr(
        supplements, "_collect_learning_consents_if_enabled", _grant_learning_consents
    )
    # Avoid depending on real object-storage configuration in the route body.
    monkeypatch.setattr(supplements, "build_learning_object_store", lambda _settings: object())

    captured: list[dict[str, object]] = []

    async def _recording_store(**kwargs: object) -> None:
        captured.append(kwargs)

    monkeypatch.setattr(supplements, "store_supplement_learning_artifacts", _recording_store)

    settings = Settings(
        privacy_hash_secret=SecretStr("test-privacy-secret"),
        enable_image_learning_pipeline=True,
        enable_pgvector_storage=True,
        image_retention_days=30,
    )
    app = create_app(settings=settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_async_session] = _session_dependency(fake_session)
    app.dependency_overrides[get_rls_context_session] = _session_dependency(fake_session)
    app.dependency_overrides[supplements.get_supplement_image_analysis_adapters] = (
        _empty_analysis_adapters
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/supplements/analyze",
        files={"image": ("label.png", _png_bytes(), "image/png")},
        data={"client_request_id": "client-learn"},
    )

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert fake_session.added_analysis is not None
    # The background task ran (TestClient executes background tasks) with the
    # deferred artifacts pointing at the now-durable analysis run.
    assert len(captured) == 1
    artifacts = captured[0]["artifacts"]
    assert artifacts.analysis_id == fake_session.added_analysis.id
    assert artifacts.learning_consents == learning_consents
    assert captured[0]["settings"] is settings
    assert captured[0]["object_store"] is not None
    # Audit metadata exposes only the scheduling signal, never a created flag.
    intake_audit = fake_session.added_audits[-1]
    assert intake_audit.event_metadata["learning_image_object_scheduled"] is True


def test_analyze_supplement_label_skips_learning_schedule_when_gate_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify no background learning task is scheduled without learning consents."""
    fake_session = _FakeSupplementSession()
    monkeypatch.setattr(supplements, "require_user_consent", _allow_consent)

    captured: list[dict[str, object]] = []

    async def _recording_store(**kwargs: object) -> None:
        captured.append(kwargs)

    monkeypatch.setattr(supplements, "store_supplement_learning_artifacts", _recording_store)

    app = create_app()
    app.dependency_overrides[get_async_session] = _session_dependency(fake_session)
    app.dependency_overrides[get_rls_context_session] = _session_dependency(fake_session)
    app.dependency_overrides[supplements.get_supplement_image_analysis_adapters] = (
        _empty_analysis_adapters
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/supplements/analyze",
        files={"image": ("label.png", _png_bytes(), "image/png")},
        data={"client_request_id": "client-no-learn"},
    )

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert captured == []
    intake_audit = fake_session.added_audits[-1]
    assert intake_audit.event_metadata["learning_image_object_scheduled"] is False


def test_analyze_supplement_label_multi_accepts_roles_and_returns_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify multi-image intake preserves per-image previews and safe batch metadata."""
    fake_session = _FakeSupplementSession()
    monkeypatch.setattr(supplements, "require_user_consent", _allow_consent)
    app = create_app()
    app.dependency_overrides[get_async_session] = _session_dependency(fake_session)
    app.dependency_overrides[get_rls_context_session] = _session_dependency(fake_session)
    app.dependency_overrides[supplements.get_supplement_image_analysis_adapters] = (
        _empty_analysis_adapters
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/supplements/analyze-multi",
        files=[
            ("images", ("front.png", _png_bytes(), "image/png")),
            ("images", ("facts.png", _png_bytes(), "image/png")),
        ],
        data={"image_roles": ["front_label", "intake_method"]},
    )

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert len(fake_session.added_analyses) == 2
    body = response.json()
    assert body["analysis_group_id"].startswith("multi-")
    assert body["image_count"] == 2
    assert body["pipeline_metadata"]["image_count"] == 2
    assert body["pipeline_metadata"]["image_role"] == "mixed"
    assert body["pipeline_metadata"]["raw_image_stored"] is False
    assert body["pipeline_metadata"]["raw_ocr_text_stored"] is False
    assert body["previews"][0]["image_role"] == "front_label"
    assert body["previews"][1]["image_role"] == "intake_method"
    assert body["previews"][0]["multi_image_group_id"] == body["analysis_group_id"]
    assert body["previews"][1]["pipeline_metadata"]["image_count"] == 2
    assert body["merged_preview"] is None
    assert body["missing_required_sections"] == [
        "product_name",
        "supplement_facts",
        "precautions",
    ]
    assert body["action_required"] == "additional_label_image_required"
    assert all("ocr_text" not in preview for preview in body["previews"])


def test_analyze_supplement_label_multi_accepts_json_roles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify mobile clients can send role lists as a JSON form field."""
    fake_session = _FakeSupplementSession()
    monkeypatch.setattr(supplements, "require_user_consent", _allow_consent)
    app = create_app()
    app.dependency_overrides[get_async_session] = _session_dependency(fake_session)
    app.dependency_overrides[get_rls_context_session] = _session_dependency(fake_session)
    app.dependency_overrides[supplements.get_supplement_image_analysis_adapters] = (
        _empty_analysis_adapters
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/supplements/analyze-multi",
        files=[
            ("images", ("front.png", _png_bytes(), "image/png")),
            ("images", ("facts.png", _png_bytes(), "image/png")),
        ],
        data={"image_roles_json": '["front_label","supplement_facts"]'},
    )

    assert response.status_code == status.HTTP_202_ACCEPTED
    body = response.json()
    assert body["previews"][0]["image_role"] == "front_label"
    assert body["previews"][1]["image_role"] == "supplement_facts"
    assert body["merged_preview"] is None


class _SequenceOCRAdapterForFusion(OCRAdapter):
    """Fake OCR adapter returning one configured result per image call."""

    def __init__(self, results: list[OCRResult]) -> None:
        self._results = results
        self.calls = 0

    async def extract_text(self, image: OCRImageInput) -> OCRResult:
        """Return the configured result for the current call index."""
        _ = image
        result = self._results[min(self.calls, len(self._results) - 1)]
        self.calls += 1
        return result


class _FixedParserForFusion:
    """Fake structured parser returning a fixed result and capturing input text."""

    def __init__(self, result: SupplementStructuredParseResult) -> None:
        self._result = result
        self.received_text: str | None = None

    async def parse_supplement_ocr_text(self, ocr_text: str) -> SupplementStructuredParseResult:
        """Capture the fused OCR text and return the configured parse result."""
        self.received_text = ocr_text
        return self._result


def _fusion_parse_result() -> SupplementStructuredParseResult:
    """Return a minimal valid structured parse result for fusion tests."""
    return SupplementStructuredParseResult.model_validate(
        {
            "parsed_product": {"product_name": "비타민 D 1000"},
            "ingredient_candidates": [
                {"display_name": "비타민 D", "amount": 25, "unit": "ug", "confidence": 0.9}
            ],
            "intake_method": {
                "text": "하루 1회 1캡슐",
                "confidence": 0.86,
                "evidence_refs": ["intake-1"],
            },
            "precautions": [],
            "low_confidence_fields": [],
            "warnings": [],
        }
    )


def _fusion_adapters() -> SupplementImageAnalysisAdapters:
    """Adapters with a per-image OCR sequence and a fixed parser for fusion tests."""
    return SupplementImageAnalysisAdapters(
        ocr=_SequenceOCRAdapterForFusion(
            [
                OCRResult(text="ALPHAONE Vitamin D Complex", provider="clova", confidence=0.9),
                OCRResult(text="BRAVOTWO 하루 1회 1캡슐", provider="clova", confidence=0.8),
            ]
        ),
        parser=_FixedParserForFusion(_fusion_parse_result()),
    )


def test_analyze_supplement_label_multi_single_product_fuses_to_one_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """single_product fuses N images into ONE run with a single merged preview."""
    fake_session = _FakeSupplementSession()
    monkeypatch.setattr(supplements, "require_user_consent", _allow_consent)
    # Fusion is dark-launched (default False); enable it explicitly for this path.
    fusion_settings = Settings(supplement_one_shot_fusion_enabled=True)
    app = create_app(settings=fusion_settings)
    app.dependency_overrides[get_settings] = lambda: fusion_settings
    app.dependency_overrides[get_async_session] = _session_dependency(fake_session)
    app.dependency_overrides[get_rls_context_session] = _session_dependency(fake_session)
    app.dependency_overrides[supplements.get_supplement_image_analysis_adapters] = _fusion_adapters
    client = TestClient(app)

    response = client.post(
        "/api/v1/supplements/analyze-multi",
        files=[
            ("images", ("front.png", _png_bytes(), "image/png")),
            ("images", ("intake.png", _png_bytes(), "image/png")),
        ],
        data={
            "image_roles": ["front_label", "intake_method"],
            "merge_strategy": "single_product",
        },
    )

    assert response.status_code == status.HTTP_202_ACCEPTED
    # Two images fused into exactly ONE persisted analysis run.
    assert len(fake_session.added_analyses) == 1
    body = response.json()
    assert len(body["previews"]) == 1
    assert body["merged_preview"] is not None
    assert body["result_mode"] == "single_product"
    assert body["merged_preview"]["parsed_product"]["product_name"] == "비타민 D 1000"
    # Privacy: no raw OCR text exposed anywhere in the response.
    assert "ocr_text" not in body["merged_preview"]
    assert all("ocr_text" not in preview for preview in body["previews"])
    # Audit records the one-shot fusion and never stores raw OCR text.
    created = [
        audit
        for audit in fake_session.added_audits
        if audit.action == "supplement_image_multi_intake_created"
    ]
    assert created
    assert created[-1].event_metadata["merge_strategy"] == "single_product"
    assert created[-1].event_metadata["raw_ocr_text_stored"] is False


def test_analyze_supplement_label_multi_distinct_products_keeps_per_image(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """distinct_products keeps the per-image path: one run per image."""
    fake_session = _FakeSupplementSession()
    monkeypatch.setattr(supplements, "require_user_consent", _allow_consent)
    app = create_app()
    app.dependency_overrides[get_async_session] = _session_dependency(fake_session)
    app.dependency_overrides[get_rls_context_session] = _session_dependency(fake_session)
    app.dependency_overrides[supplements.get_supplement_image_analysis_adapters] = _fusion_adapters
    client = TestClient(app)

    response = client.post(
        "/api/v1/supplements/analyze-multi",
        files=[
            ("images", ("front.png", _png_bytes(), "image/png")),
            ("images", ("intake.png", _png_bytes(), "image/png")),
        ],
        data={
            "image_roles": ["front_label", "intake_method"],
            "merge_strategy": "distinct_products",
        },
    )

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert len(fake_session.added_analyses) == 2
    body = response.json()
    assert body["result_mode"] == "distinct_products"
    assert body["merged_preview"] is None
    assert len(body["previews"]) == 2


def test_analyze_supplement_label_multi_single_product_falls_through_when_fusion_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dark-launch default: single_product without the flag uses the per-image path.

    With ``supplement_one_shot_fusion_enabled`` False (the dark-launch default),
    a single_product request must fall through to the distinct per-image branch
    and persist one run per image — never the fused single run.
    """
    fake_session = _FakeSupplementSession()
    monkeypatch.setattr(supplements, "require_user_consent", _allow_consent)
    disabled_settings = Settings(supplement_one_shot_fusion_enabled=False)
    app = create_app(settings=disabled_settings)
    app.dependency_overrides[get_settings] = lambda: disabled_settings
    app.dependency_overrides[get_async_session] = _session_dependency(fake_session)
    app.dependency_overrides[get_rls_context_session] = _session_dependency(fake_session)
    app.dependency_overrides[supplements.get_supplement_image_analysis_adapters] = _fusion_adapters
    client = TestClient(app)

    response = client.post(
        "/api/v1/supplements/analyze-multi",
        files=[
            ("images", ("front.png", _png_bytes(), "image/png")),
            ("images", ("intake.png", _png_bytes(), "image/png")),
        ],
        data={
            "image_roles": ["front_label", "intake_method"],
            "merge_strategy": "single_product",
        },
    )

    assert response.status_code == status.HTTP_202_ACCEPTED
    # Flag off → fusion skipped → per-image distinct path → one run per image.
    assert len(fake_session.added_analyses) == 2


def test_analyze_supplement_label_multi_single_product_schedules_per_image_learning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One-shot fusion schedules one post-commit learning task PER image.

    The fused parse is a single preview, but each physical image must reach the
    section-detector dataset with its own layout-bearing OCR result, so the route
    schedules ``store_supplement_learning_artifacts`` once per image. All
    artifacts link to the single fused run id.
    """
    fake_session = _FakeSupplementSession()
    monkeypatch.setattr(supplements, "require_user_consent", _allow_consent)

    learning_consents = (
        ConsentType.OCR_IMAGE_PROCESSING,
        ConsentType.DATA_RETENTION,
        ConsentType.IMAGE_LEARNING_DATASET,
    )

    async def _grant_learning_consents(
        *_args: object, **_kwargs: object
    ) -> tuple[ConsentType, ...]:
        return learning_consents

    monkeypatch.setattr(
        supplements, "_collect_learning_consents_if_enabled", _grant_learning_consents
    )
    monkeypatch.setattr(supplements, "build_learning_object_store", lambda _settings: object())

    captured: list[dict[str, object]] = []

    async def _recording_store(**kwargs: object) -> None:
        captured.append(kwargs)

    monkeypatch.setattr(supplements, "store_supplement_learning_artifacts", _recording_store)

    settings = Settings(
        privacy_hash_secret=SecretStr("test-privacy-secret"),
        enable_image_learning_pipeline=True,
        enable_pgvector_storage=True,
        image_retention_days=30,
        supplement_one_shot_fusion_enabled=True,
    )
    app = create_app(settings=settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_async_session] = _session_dependency(fake_session)
    app.dependency_overrides[get_rls_context_session] = _session_dependency(fake_session)
    app.dependency_overrides[supplements.get_supplement_image_analysis_adapters] = _fusion_adapters
    client = TestClient(app)

    response = client.post(
        "/api/v1/supplements/analyze-multi",
        files=[
            ("images", ("front.png", _png_bytes(), "image/png")),
            ("images", ("intake.png", _png_bytes(), "image/png")),
        ],
        data={
            "image_roles": ["front_label", "intake_method"],
            "merge_strategy": "single_product",
        },
    )

    assert response.status_code == status.HTTP_202_ACCEPTED
    # Exactly ONE fused analysis run for the whole batch...
    assert len(fake_session.added_analyses) == 1
    # ...but one scheduled learning task PER image (two images here).
    assert len(captured) == 2
    # Every per-image artifact links to the single fused run.
    analysis_ids = {kwargs["artifacts"].analysis_id for kwargs in captured}
    assert len(analysis_ids) == 1
    assert all(kwargs["artifacts"].learning_consents == learning_consents for kwargs in captured)


def test_analyze_supplement_label_multi_rejects_role_count_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify multi-image role metadata must align one-to-one with uploads."""
    fake_session = _FakeSupplementSession()
    monkeypatch.setattr(supplements, "require_user_consent", _allow_consent)
    app = create_app()
    app.dependency_overrides[get_async_session] = _session_dependency(fake_session)
    app.dependency_overrides[get_rls_context_session] = _session_dependency(fake_session)
    app.dependency_overrides[supplements.get_supplement_image_analysis_adapters] = (
        _empty_analysis_adapters
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/supplements/analyze-multi",
        files=[
            ("images", ("front.png", _png_bytes(), "image/png")),
            ("images", ("facts.png", _png_bytes(), "image/png")),
        ],
        data={"image_roles": ["front_label"]},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["detail"]["code"] == "image_role_count_mismatch"
    assert fake_session.added_analyses == []


def test_create_supplement_analysis_session_returns_upload_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify session create returns a safe group id before any image is uploaded."""
    fake_session = _FakeSupplementSession()
    monkeypatch.setattr(supplements, "require_user_consent", _allow_consent)
    app = create_app()
    app.dependency_overrides[get_async_session] = _session_dependency(fake_session)
    app.dependency_overrides[get_rls_context_session] = _session_dependency(fake_session)
    client = TestClient(app)

    response = client.post("/api/v1/supplements/analysis-sessions")

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["analysis_group_id"].startswith("multi-")
    assert body["status"] == "created"
    assert body["image_count"] == 0
    assert body["max_images"] == 6
    assert body["missing_required_sections"] == [
        "product_name",
        "supplement_facts",
        "intake_method",
        "precautions",
    ]
    assert body["action_required"] == "additional_label_image_required"
    assert len(fake_session.added_audits) == 1


def test_upload_supplement_analysis_session_image_returns_current_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify a session image upload stores role metadata and returns the group preview."""
    fake_session = _FakeSupplementSession()
    monkeypatch.setattr(supplements, "require_user_consent", _allow_consent)
    app = create_app()
    app.dependency_overrides[get_async_session] = _session_dependency(fake_session)
    app.dependency_overrides[get_rls_context_session] = _session_dependency(fake_session)
    app.dependency_overrides[supplements.get_supplement_image_analysis_adapters] = (
        _empty_analysis_adapters
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/supplements/analysis-sessions/multi-test/images",
        files={"image": ("facts.png", _png_bytes(), "image/png")},
        data={
            "image_role": "supplement_facts",
            "client_request_id": "image-1",
            "ocr_provider": "configured",
        },
    )

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert len(fake_session.added_analyses) == 1
    stored = fake_session.added_analyses[0]
    assert stored.client_request_id is not None
    assert stored.client_request_id.endswith(":multi-test:image-1")
    assert stored.parsed_snapshot["multi_image_group_id"] == "multi-test"
    assert stored.parsed_snapshot["image_role"] == "supplement_facts"
    body = response.json()
    assert body["analysis_group_id"] == "multi-test"
    assert body["image_count"] == 1
    assert body["previews"][0]["image_role"] == "supplement_facts"
    assert body["previews"][0]["pipeline_metadata"]["image_count"] == 1
    assert body["merged_preview"] is None
    assert "ocr_text" not in body["previews"][0]


def test_finalize_supplement_analysis_session_returns_merged_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify a persisted multi-image batch can be finalized into one safe preview."""
    group_id = "multi-test"
    front = _multi_image_run(
        group_id=group_id,
        image_role="front_label",
        image_sha256="a" * 64,
        parsed_snapshot={
            "parsed_product": {"product_name": "테스트 비타민"},
            "label_sections": [
                {
                    "section_id": "front",
                    "section_type": "unknown",
                    "heading_text": "front",
                    "text_bundle": "제품명 확인",
                    "confidence": 0.8,
                    "evidence_refs": ["front-name"],
                }
            ],
            "evidence_spans": [
                {
                    "span_id": "front-name",
                    "source_type": "ocr_layout",
                    "section_type": "unknown",
                    "text_excerpt": "제품명 확인",
                    "confidence": 0.8,
                }
            ],
        },
    )
    facts = _multi_image_run(
        group_id=group_id,
        image_role="supplement_facts",
        image_sha256="b" * 64,
        parsed_snapshot={
            "ingredient_candidates": [
                {
                    "display_name": "비타민 C",
                    "amount": 500,
                    "unit": "mg",
                    "confidence": 0.86,
                    "source": "ocr_layout",
                }
            ],
            "label_sections": [
                {
                    "section_id": "facts",
                    "section_type": "supplement_facts",
                    "heading_text": "Supplement Facts",
                    "text_bundle": "성분표 확인",
                    "confidence": 0.86,
                    "evidence_refs": ["facts-vitamin-c"],
                },
                {
                    "section_id": "intake",
                    "section_type": "intake_method",
                    "heading_text": "섭취 방법",
                    "text_bundle": "섭취 방법 확인",
                    "confidence": 0.82,
                    "evidence_refs": ["facts-intake"],
                },
                {
                    "section_id": "precautions",
                    "section_type": "precautions",
                    "heading_text": "주의사항",
                    "text_bundle": "주의사항 확인",
                    "confidence": 0.8,
                    "evidence_refs": ["facts-precaution"],
                },
            ],
            "intake_method": {
                "text": "섭취 방법 확인",
                "confidence": 0.82,
                "evidence_refs": ["facts-intake"],
            },
            "precautions": [
                {
                    "text": "주의사항 확인",
                    "category": "unknown",
                    "severity": "warning",
                    "confidence": 0.8,
                    "evidence_refs": ["facts-precaution"],
                }
            ],
            "evidence_spans": [
                {
                    "span_id": "facts-vitamin-c",
                    "source_type": "ocr_layout",
                    "section_type": "supplement_facts",
                    "text_excerpt": "성분표 확인",
                    "confidence": 0.86,
                },
                {
                    "span_id": "facts-intake",
                    "source_type": "ocr_layout",
                    "section_type": "intake_method",
                    "text_excerpt": "섭취 방법 확인",
                    "confidence": 0.82,
                },
                {
                    "span_id": "facts-precaution",
                    "source_type": "ocr_layout",
                    "section_type": "precautions",
                    "text_excerpt": "주의사항 확인",
                    "confidence": 0.8,
                },
            ],
        },
    )
    fake_session = _FakeSupplementSession(finalize_runs=[front, facts])
    monkeypatch.setattr(supplements, "require_user_consent", _allow_consent)
    app = create_app()
    app.dependency_overrides[get_async_session] = _session_dependency(fake_session)
    app.dependency_overrides[get_rls_context_session] = _session_dependency(fake_session)
    client = TestClient(app)

    response = client.post(f"/api/v1/supplements/analysis-sessions/{group_id}/finalize")

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["analysis_group_id"] == group_id
    assert body["image_count"] == 2
    assert body["missing_required_sections"] == []
    assert body["action_required"] == "review_required"
    assert body["pipeline_metadata"]["image_count"] == 2
    assert body["pipeline_metadata"]["image_role"] == "mixed"
    assert body["merged_preview"]["multi_image_group_id"] == group_id
    assert body["merged_preview"]["image_role"] == "mixed"
    assert body["merged_preview"]["parsed_product"]["product_name"] == "테스트 비타민"
    assert body["merged_preview"]["ingredient_candidates"][0]["display_name"] == "비타민 C"
    assert body["merged_preview"]["intake_method"]["text"] == "섭취 방법 확인"
    assert "ocr_text" not in body["merged_preview"]


def test_finalize_supplement_analysis_session_returns_404_for_missing_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify finalize fails closed when the current user has no such group."""
    fake_session = _FakeSupplementSession(finalize_runs=[])
    monkeypatch.setattr(supplements, "require_user_consent", _allow_consent)
    monkeypatch.setattr(supplements, "record_sensitive_audit_event", _record_noop_audit)
    app = create_app()
    app.dependency_overrides[get_async_session] = _session_dependency(fake_session)
    app.dependency_overrides[get_rls_context_session] = _session_dependency(fake_session)
    client = TestClient(app)

    response = client.post("/api/v1/supplements/analysis-sessions/missing/finalize")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"]["code"] == "analysis_session_not_found"


def test_analyze_supplement_label_requires_ocr_consent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify supplement image intake fails closed without OCR consent."""
    fake_session = _FakeSupplementSession()
    settings = _settings()
    monkeypatch.setattr(supplements, "require_user_consent", _deny_consent)
    monkeypatch.setattr(supplements, "record_sensitive_audit_event", _record_noop_audit)
    app = create_app(settings=settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_async_session] = _session_dependency(fake_session)
    app.dependency_overrides[get_rls_context_session] = _session_dependency(fake_session)
    client = TestClient(app)

    response = client.post(
        "/api/v1/supplements/analyze",
        files={"image": ("label.png", _png_bytes(), "image/png")},
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"]["code"] == "consent_required"
    assert response.json()["detail"]["required_consents"] == ["ocr_image_processing"]


def test_analyze_supplement_label_rejects_media_type_spoofing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify content-type and image bytes must agree."""
    fake_session = _FakeSupplementSession()
    monkeypatch.setattr(supplements, "require_user_consent", _allow_consent)
    monkeypatch.setattr(supplements, "record_sensitive_audit_event", _record_noop_audit)
    app = create_app()
    app.dependency_overrides[get_async_session] = _session_dependency(fake_session)
    app.dependency_overrides[get_rls_context_session] = _session_dependency(fake_session)
    client = TestClient(app)

    response = client.post(
        "/api/v1/supplements/analyze",
        files={"image": ("label.jpg", _png_bytes(), "image/jpeg")},
    )

    assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    assert response.json()["detail"]["code"] == "unsupported_media_type"
    assert fake_session.added_analysis is None


def test_analyze_supplement_label_rejects_oversized_image(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify supplement image byte limits are enforced through settings."""
    fake_session = _FakeSupplementSession()
    settings = _settings(supplement_image_max_bytes=1024)
    monkeypatch.setattr(supplements, "require_user_consent", _allow_consent)
    monkeypatch.setattr(supplements, "record_sensitive_audit_event", _record_noop_audit)
    app = create_app(settings=settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_async_session] = _session_dependency(fake_session)
    app.dependency_overrides[get_rls_context_session] = _session_dependency(fake_session)
    client = TestClient(app)

    response = client.post(
        "/api/v1/supplements/analyze",
        files={"image": ("label.png", b"x" * 1025, "image/png")},
    )

    assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE
    assert response.json()["detail"]["code"] == "payload_too_large"
    assert fake_session.added_analysis is None


def test_analyze_supplement_label_rejects_idempotency_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify a client idempotency key cannot be reused for another image."""
    fake_session = _FakeSupplementSession(existing=_existing_run(image_sha256="b" * 64))
    monkeypatch.setattr(supplements, "require_user_consent", _allow_consent)
    monkeypatch.setattr(supplements, "record_sensitive_audit_event", _record_noop_audit)
    app = create_app()
    app.dependency_overrides[get_async_session] = _session_dependency(fake_session)
    app.dependency_overrides[get_rls_context_session] = _session_dependency(fake_session)
    client = TestClient(app)

    response = client.post(
        "/api/v1/supplements/analyze",
        files={"image": ("label.png", _png_bytes(), "image/png")},
        data={"client_request_id": "client-1"},
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"]["code"] == "idempotency_conflict"
    assert fake_session.added_analysis is None
