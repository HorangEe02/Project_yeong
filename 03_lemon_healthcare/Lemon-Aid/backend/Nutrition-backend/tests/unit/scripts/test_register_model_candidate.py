"""Tests for operator model candidate registration CLI."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from src.learning.retraining import RetrainingSecurityError
from src.models.db.retraining import ModelRegistryEntry, ModelTrainingRun

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

candidate_cli = importlib.import_module("scripts.register_model_candidate")


class _FakeSession:
    """Fake async session for model candidate registration tests."""

    def __init__(self, training_run: ModelTrainingRun | None) -> None:
        """Initialize captured reads and writes.

        Args:
            training_run: Training run returned by ``get``.
        """
        self.training_run = training_run
        self.added_rows: list[ModelRegistryEntry] = []
        self.commit_count = 0

    async def get(self, model_type: type[object], row_id: UUID) -> object | None:
        """Return a fake training run when requested.

        Args:
            model_type: SQLAlchemy model type.
            row_id: Requested row id.

        Returns:
            Fake row or None.
        """
        if (
            model_type is ModelTrainingRun
            and self.training_run is not None
            and self.training_run.id == row_id
        ):
            return self.training_run
        return None

    def add(self, row: ModelRegistryEntry) -> None:
        """Capture one added row.

        Args:
            row: Model registry row.
        """
        self.added_rows.append(row)

    async def commit(self) -> None:
        """Record a fake commit call."""
        self.commit_count += 1


class _FakeSessionContext:
    """Fake async session context manager."""

    def __init__(self, session: _FakeSession) -> None:
        """Initialize context session.

        Args:
            session: Fake session.
        """
        self.session = session

    async def __aenter__(self) -> _FakeSession:
        """Return the fake session."""
        return self.session

    async def __aexit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        """Close the fake context."""
        _ = (exc_type, exc, traceback)


def _training_run(
    *,
    model_family: str = "paddleocr_rec",
    status: str = "succeeded",
    artifact_ref: str | None = "models/supplement-ocr-rec/2026-05-27",
) -> ModelTrainingRun:
    """Build a fake persisted training run.

    Args:
        model_family: Training run model family.
        status: Training lifecycle status.
        artifact_ref: Private artifact reference.

    Returns:
        Fake model training run.
    """
    return ModelTrainingRun(
        id=uuid4(),
        model_family=model_family,
        base_model="PP-OCRv5-rec",
        dataset_version_id=uuid4(),
        hyperparam_snapshot={},
        metrics_snapshot={},
        artifact_ref=artifact_ref,
        status=status,
    )


def _patch_sessionmaker(monkeypatch: pytest.MonkeyPatch, session: _FakeSession) -> None:
    """Patch the script DB session factory.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        session: Fake session.
    """
    monkeypatch.setattr(
        candidate_cli,
        "get_sessionmaker",
        lambda: lambda: _FakeSessionContext(session),
    )


@pytest.mark.asyncio
async def test_register_model_candidate_persists_sanitized_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify candidate registration stores private refs but prints redacted status."""
    training_run = _training_run()
    session = _FakeSession(training_run)
    _patch_sessionmaker(monkeypatch, session)

    summary = await candidate_cli.register_model_candidate(
        training_run_id=training_run.id,
        task_type="supplement_ocr_recognition",
        model_version="paddleocr-rec-2026.05.27",
        artifact_ref=None,
    )

    assert session.commit_count == 1
    assert len(session.added_rows) == 1
    row = session.added_rows[0]
    assert row.training_run_id == training_run.id
    assert row.artifact_ref == training_run.artifact_ref
    assert row.deployment_status == "candidate"
    assert row.metric_gate_snapshot == {}
    assert summary["artifact_ref_registered"] is True
    assert summary["artifact_ref_printed"] is False
    serialized = json.dumps(summary, ensure_ascii=False)
    assert str(training_run.artifact_ref) not in serialized


@pytest.mark.asyncio
async def test_register_model_candidate_rejects_task_family_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify candidates cannot cross model-family task boundaries."""
    training_run = _training_run(model_family="paddleocr_det")
    session = _FakeSession(training_run)
    _patch_sessionmaker(monkeypatch, session)

    with pytest.raises(ValueError, match="Task type does not match"):
        await candidate_cli.register_model_candidate(
            training_run_id=training_run.id,
            task_type="supplement_ocr_recognition",
            model_version="paddleocr-rec-2026.05.27",
            artifact_ref=None,
        )

    assert session.added_rows == []
    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_register_model_candidate_rejects_unsucceeded_training_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify only succeeded training runs can become deployable candidates."""
    training_run = _training_run(status="running")
    session = _FakeSession(training_run)
    _patch_sessionmaker(monkeypatch, session)

    with pytest.raises(ValueError, match="must be succeeded"):
        await candidate_cli.register_model_candidate(
            training_run_id=training_run.id,
            task_type="supplement_ocr_recognition",
            model_version="paddleocr-rec-2026.05.27",
            artifact_ref=None,
        )

    assert session.added_rows == []
    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_register_model_candidate_rejects_public_artifact_ref(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify model artifact refs cannot be public URLs or absolute paths."""
    training_run = _training_run()
    session = _FakeSession(training_run)
    _patch_sessionmaker(monkeypatch, session)

    with pytest.raises(RetrainingSecurityError, match="private relative reference"):
        await candidate_cli.register_model_candidate(
            training_run_id=training_run.id,
            task_type="supplement_ocr_recognition",
            model_version="paddleocr-rec-2026.05.27",
            artifact_ref="https://example.com/model",
        )

    assert session.added_rows == []
    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_run_cli_prints_sanitized_success(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI stdout excludes artifact refs and metric snapshots."""
    training_run = _training_run(model_family="yolo", artifact_ref="models/yolo/2026-05-27")
    session = _FakeSession(training_run)
    _patch_sessionmaker(monkeypatch, session)

    exit_code = await candidate_cli.run_cli(
        [
            "--training-run-id",
            str(training_run.id),
            "--task-type",
            "supplement_roi_detection",
            "--model-version",
            "yolo-2026.05.27",
        ]
    )

    stdout = capsys.readouterr().out
    assert exit_code == 0
    assert "artifact_ref_registered" in stdout
    assert "models/yolo/2026-05-27" not in stdout
    assert "metric_gate_snapshot" not in stdout


def test_validate_model_version_rejects_path_like_value() -> None:
    """Verify model version labels cannot carry paths or URL-like text."""
    with pytest.raises(RetrainingSecurityError, match="safe tag"):
        candidate_cli._validate_model_version("../candidate")
