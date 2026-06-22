"""Tests for operator model training run registration CLI."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from src.learning.retraining import RetrainingSecurityError
from src.models.db.retraining import ModelTrainingRun

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

registration_cli = importlib.import_module("scripts.register_model_training_run")


class _FakeSession:
    """Fake async session for training run registration tests."""

    def __init__(self) -> None:
        """Initialize captured writes."""
        self.added_rows: list[ModelTrainingRun] = []
        self.commit_count = 0

    def add(self, row: ModelTrainingRun) -> None:
        """Capture one added row.

        Args:
            row: Training run row.
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


def _patch_sessionmaker(monkeypatch: pytest.MonkeyPatch, session: _FakeSession) -> None:
    """Patch the script DB session factory.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        session: Fake session.
    """
    monkeypatch.setattr(
        registration_cli,
        "get_sessionmaker",
        lambda: lambda: _FakeSessionContext(session),
    )


@pytest.mark.asyncio
async def test_register_model_training_run_persists_sanitized_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify registration stores private refs but prints only redacted counts."""
    session = _FakeSession()
    dataset_version_id = uuid4()
    artifact_ref = "models/supplement-ocr-rec/2026-05-27"
    _patch_sessionmaker(monkeypatch, session)

    summary = await registration_cli.register_model_training_run(
        model_family="paddleocr_rec",
        base_model="PP-OCRv5-rec",
        dataset_version_id=dataset_version_id,
        hyperparam_snapshot={"epochs": 5, "image_size": 640},
        metrics_snapshot={"cer": 0.081},
        artifact_ref=artifact_ref,
        status="succeeded",
    )

    assert session.commit_count == 1
    assert len(session.added_rows) == 1
    row = session.added_rows[0]
    assert row.dataset_version_id == dataset_version_id
    assert row.artifact_ref == artifact_ref
    assert row.hyperparam_snapshot == {"epochs": 5, "image_size": 640}
    assert row.metrics_snapshot == {"cer": 0.081}
    assert summary["artifact_ref_registered"] is True
    serialized = json.dumps(summary, ensure_ascii=False)
    assert artifact_ref not in serialized
    assert "epochs" not in serialized
    assert "cer" not in serialized


@pytest.mark.asyncio
async def test_register_model_training_run_rejects_secret_like_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify unsafe hyperparam keys and values fail before DB writes."""
    session = _FakeSession()
    _patch_sessionmaker(monkeypatch, session)

    with pytest.raises(RetrainingSecurityError, match="Forbidden label snapshot key"):
        await registration_cli.register_model_training_run(
            model_family="yolo",
            base_model="yolov8n",
            dataset_version_id=uuid4(),
            hyperparam_snapshot={"raw_ocr_text": "unreviewed"},
            metrics_snapshot={},
            artifact_ref=None,
            status="queued",
        )

    assert session.added_rows == []
    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_register_model_training_run_rejects_public_artifact_ref(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify artifact refs cannot be public URLs or absolute paths."""
    session = _FakeSession()
    _patch_sessionmaker(monkeypatch, session)

    with pytest.raises(RetrainingSecurityError, match="private relative reference"):
        await registration_cli.register_model_training_run(
            model_family="paddleocr_det",
            base_model="PP-OCRv5-det",
            dataset_version_id=uuid4(),
            hyperparam_snapshot={},
            metrics_snapshot={"hmean": 0.91},
            artifact_ref="https://example.com/model",
            status="succeeded",
        )

    assert session.added_rows == []
    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_run_cli_prints_sanitized_success(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI stdout excludes artifact ref, hyperparams, and metric names."""
    session = _FakeSession()
    dataset_version_id = uuid4()
    artifact_ref = "models/supplement-roi/2026-05-27"
    _patch_sessionmaker(monkeypatch, session)

    exit_code = await registration_cli.run_cli(
        [
            "--model-family",
            "yolo",
            "--base-model",
            "yolov8n",
            "--dataset-version-id",
            str(dataset_version_id),
            "--hyperparams-json",
            '{"epochs": 10}',
            "--metrics-json",
            '{"mAP50": 0.9}',
            "--artifact-ref",
            artifact_ref,
            "--status",
            "succeeded",
        ]
    )

    stdout = capsys.readouterr().out
    assert exit_code == 0
    assert "artifact_ref_registered" in stdout
    assert artifact_ref not in stdout
    assert "epochs" not in stdout
    assert "mAP50" not in stdout


def test_parse_json_object_rejects_non_object() -> None:
    """Verify JSON args must be objects."""
    with pytest.raises(ValueError, match="JSON object"):
        registration_cli._parse_json_object("[]", "hyperparams-json")
