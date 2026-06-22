"""Tests for PaddleOCR fine-tune run registration from plan."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from src.models.db.retraining import ModelTrainingRun

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

registration_from_plan = importlib.import_module(
    "scripts.register_paddleocr_finetune_run_from_plan"
)


class _FakeSession:
    """Fake async session for model training registration tests."""

    def __init__(self) -> None:
        """Initialize captured rows."""
        self.added_rows: list[ModelTrainingRun] = []
        self.commit_count = 0

    def add(self, row: ModelTrainingRun) -> None:
        """Capture one added row.

        Args:
            row: Model training run row.
        """
        self.added_rows.append(row)

    async def commit(self) -> None:
        """Record one fake commit."""
        self.commit_count += 1


class _FakeSessionContext:
    """Fake async session context manager."""

    def __init__(self, session: _FakeSession) -> None:
        """Initialize context.

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
        """Close fake context."""
        _ = (exc_type, exc, traceback)


def _patch_sessionmaker(monkeypatch: pytest.MonkeyPatch, session: _FakeSession) -> None:
    """Patch delegated model training registration DB session factory.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        session: Fake session.
    """
    monkeypatch.setattr(
        registration_from_plan.training_registration,
        "get_sessionmaker",
        lambda: lambda: _FakeSessionContext(session),
    )


def _plan(
    *,
    dataset_version_id: str | None = None,
    task: str = "recognition",
    inconsistent_artifact: bool = False,
) -> dict[str, object]:
    """Build a sanitized plan fixture.

    Args:
        dataset_version_id: Optional dataset version id.
        task: PaddleOCR task.
        inconsistent_artifact: Whether to make registration artifact drift.

    Returns:
        Plan payload.
    """
    dataset_id = dataset_version_id or str(uuid4())
    model_family = "paddleocr_rec" if task == "recognition" else "paddleocr_det"
    base_model = "PP-OCRv5-rec" if task == "recognition" else "PP-OCRv5-det"
    save_model_ref = "models/paddleocr/supplement-labels"
    return {
        "schema_version": "paddleocr-finetune-run-plan-v1",
        "training_execution_performed": False,
        "dataset_version_id": dataset_id,
        "task": task,
        "model_family": model_family,
        "base_model": base_model,
        "paddleocr": {
            "config_ref": "configs/rec/supplement_rec.yml",
            "pretrained_model_ref": "pretrain_models/ppocr/best_accuracy",
            "save_model_ref": save_model_ref,
        },
        "hyperparams": {
            "epochs": 3,
            "learning_rate": 0.0001,
            "batch_size_per_card": 8,
            "gpus": "0",
        },
        "register_model_training_run": {
            "model_family": model_family,
            "base_model": base_model,
            "dataset_version_id": dataset_id,
            "artifact_ref": "models/paddleocr/drifted" if inconsistent_artifact else save_model_ref,
        },
    }


def _write_plan(path: Path, payload: dict[str, object]) -> Path:
    """Write a plan fixture.

    Args:
        path: Destination path.
        payload: Plan payload.

    Returns:
        Plan path.
    """
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.mark.asyncio
async def test_register_succeeded_finetune_run_from_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify a succeeded plan registration persists sanitized row data."""
    session = _FakeSession()
    plan_payload = _plan()
    plan_path = _write_plan(tmp_path / "plan.json", plan_payload)
    _patch_sessionmaker(monkeypatch, session)

    summary = await registration_from_plan.register_paddleocr_finetune_run_from_plan(
        plan_path=plan_path,
        metrics_snapshot={"cer": 0.08, "precision": 0.92},
        status="succeeded",
    )

    assert session.commit_count == 1
    assert len(session.added_rows) == 1
    row = session.added_rows[0]
    assert row.model_family == "paddleocr_rec"
    assert row.base_model == "PP-OCRv5-rec"
    assert row.artifact_ref == "models/paddleocr/supplement-labels"
    assert row.status == "succeeded"
    assert row.metrics_snapshot == {"cer": 0.08, "precision": 0.92}
    assert row.hyperparam_snapshot["config_ref"] == "configs/rec/supplement_rec.yml"
    assert summary["registered_from_plan"] is True
    serialized_summary = json.dumps(summary, ensure_ascii=False)
    assert "cer" not in serialized_summary
    assert "precision" not in serialized_summary
    assert "models/paddleocr" not in serialized_summary
    assert str(tmp_path) not in serialized_summary


@pytest.mark.asyncio
async def test_register_failed_finetune_run_without_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify failed runs can be tracked without registering an artifact ref."""
    session = _FakeSession()
    plan_path = _write_plan(tmp_path / "plan.json", _plan())
    _patch_sessionmaker(monkeypatch, session)

    summary = await registration_from_plan.register_paddleocr_finetune_run_from_plan(
        plan_path=plan_path,
        metrics_snapshot={},
        status="failed",
    )

    row = session.added_rows[0]
    assert row.status == "failed"
    assert row.artifact_ref is None
    assert summary["artifact_ref_registered"] is False


@pytest.mark.asyncio
async def test_succeeded_registration_requires_metrics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify successful runs must provide verified metrics."""
    session = _FakeSession()
    plan_path = _write_plan(tmp_path / "plan.json", _plan())
    _patch_sessionmaker(monkeypatch, session)

    with pytest.raises(ValueError, match="require verified metrics"):
        await registration_from_plan.register_paddleocr_finetune_run_from_plan(
            plan_path=plan_path,
            metrics_snapshot={},
            status="succeeded",
        )

    assert session.added_rows == []
    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_inconsistent_plan_registration_block_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify drift between plan and registration block fails closed."""
    session = _FakeSession()
    plan_path = _write_plan(tmp_path / "plan.json", _plan(inconsistent_artifact=True))
    _patch_sessionmaker(monkeypatch, session)

    with pytest.raises(
        registration_from_plan.PaddleOCRFinetuneRegistrationError,
        match="artifact ref is inconsistent",
    ):
        await registration_from_plan.register_paddleocr_finetune_run_from_plan(
            plan_path=plan_path,
            metrics_snapshot={"cer": 0.08},
            status="succeeded",
        )

    assert session.added_rows == []
    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_cli_prints_only_redacted_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI output hides metrics, artifact refs, and local paths."""
    session = _FakeSession()
    plan_path = _write_plan(tmp_path / "plan.json", _plan())
    _patch_sessionmaker(monkeypatch, session)

    exit_code = await registration_from_plan.run_cli(
        [
            "--plan",
            str(plan_path),
            "--metrics-json",
            '{"cer": 0.08}',
            "--status",
            "succeeded",
        ]
    )

    stdout = capsys.readouterr().out
    assert exit_code == 0
    assert "registered_from_plan" in stdout
    assert "cer" not in stdout
    assert "0.08" not in stdout
    assert "models/paddleocr" not in stdout
    assert str(tmp_path) not in stdout
