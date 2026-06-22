"""Tests for operator model evaluation result registration CLI."""

from __future__ import annotations

import importlib
import json
import sys
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from src.learning.retraining import RetrainingSecurityError
from src.models.db.retraining import ModelEvalResult, ModelRegistryEntry

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

eval_cli = importlib.import_module("scripts.register_model_eval_results")


class _FakeSession:
    """Fake async session for model eval registration tests."""

    def __init__(self, model: ModelRegistryEntry | None) -> None:
        """Initialize captured reads and writes.

        Args:
            model: Model registry row returned by ``get``.
        """
        self.model = model
        self.added_rows: list[ModelEvalResult] = []
        self.commit_count = 0

    async def get(self, model_type: type[object], row_id: UUID) -> object | None:
        """Return a fake model registry row when requested.

        Args:
            model_type: SQLAlchemy model type.
            row_id: Requested row id.

        Returns:
            Fake row or None.
        """
        if model_type is ModelRegistryEntry and self.model is not None and self.model.id == row_id:
            return self.model
        return None

    def add(self, row: ModelEvalResult) -> None:
        """Capture one added row.

        Args:
            row: Model eval result row.
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


def _model() -> ModelRegistryEntry:
    """Build a fake model registry entry.

    Returns:
        Fake model registry entry.
    """
    return ModelRegistryEntry(
        id=uuid4(),
        task_type="supplement_ocr_recognition",
        model_version="paddleocr-rec-2026.05.27",
        training_run_id=uuid4(),
        artifact_ref="models/supplement-ocr-rec/2026-05-27",
        deployment_status="candidate",
        metric_gate_snapshot={},
    )


def _patch_sessionmaker(monkeypatch: pytest.MonkeyPatch, session: _FakeSession) -> None:
    """Patch the script DB session factory.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        session: Fake session.
    """
    monkeypatch.setattr(
        eval_cli,
        "get_sessionmaker",
        lambda: lambda: _FakeSessionContext(session),
    )


@pytest.mark.asyncio
async def test_register_model_eval_results_persists_metric_rows_without_stdout_leak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify metric values are stored but not returned in the summary."""
    model = _model()
    session = _FakeSession(model)
    eval_dataset_version_id = uuid4()
    _patch_sessionmaker(monkeypatch, session)

    summary = await eval_cli.register_model_eval_results(
        model_id=model.id,
        eval_dataset_version_id=eval_dataset_version_id,
        metrics={"cer": Decimal("0.081"), "wer": Decimal("0.120")},
        subgroup_key="holdout:label",
        failure_bucket="low_contrast",
    )

    assert session.commit_count == 1
    assert len(session.added_rows) == 2
    assert {row.metric_name for row in session.added_rows} == {"cer", "wer"}
    assert {row.metric_value for row in session.added_rows} == {
        Decimal("0.081"),
        Decimal("0.120"),
    }
    assert summary["eval_result_count"] == 2
    assert summary["metric_names_printed"] is False
    assert summary["metric_values_printed"] is False
    serialized = json.dumps(summary, ensure_ascii=False)
    assert "cer" not in serialized
    assert "0.081" not in serialized
    assert "low_contrast" not in serialized


@pytest.mark.asyncio
async def test_register_model_eval_results_rejects_missing_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify a missing model row fails before metric rows are written."""
    session = _FakeSession(None)
    _patch_sessionmaker(monkeypatch, session)

    with pytest.raises(ValueError, match="Model registry entry"):
        await eval_cli.register_model_eval_results(
            model_id=uuid4(),
            eval_dataset_version_id=uuid4(),
            metrics={"cer": Decimal("0.081")},
        )

    assert session.added_rows == []
    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_register_model_eval_results_rejects_negative_metric(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify negative metrics fail before DB writes."""
    model = _model()
    session = _FakeSession(model)
    _patch_sessionmaker(monkeypatch, session)

    with pytest.raises(RetrainingSecurityError, match="finite and nonnegative"):
        await eval_cli.register_model_eval_results(
            model_id=model.id,
            eval_dataset_version_id=uuid4(),
            metrics={"cer": Decimal("-0.1")},
        )

    assert session.added_rows == []
    assert session.commit_count == 0


def test_parse_metric_pairs_rejects_duplicate_metric_names() -> None:
    """Verify duplicate metric rows are rejected."""
    with pytest.raises(ValueError, match="Duplicate metric"):
        eval_cli._parse_metric_pairs([["cer", "0.1"], ["cer", "0.2"]])


def test_validate_metric_name_rejects_path_like_value() -> None:
    """Verify metric names cannot carry paths, URLs, or traversal text."""
    with pytest.raises(RetrainingSecurityError, match="stable safe"):
        eval_cli._validate_metric_name("../cer")


@pytest.mark.asyncio
async def test_run_cli_prints_sanitized_success(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI stdout excludes metric names, values, and bucket labels."""
    model = _model()
    session = _FakeSession(model)
    eval_dataset_version_id = uuid4()
    _patch_sessionmaker(monkeypatch, session)

    exit_code = await eval_cli.run_cli(
        [
            "--model-id",
            str(model.id),
            "--eval-dataset-version-id",
            str(eval_dataset_version_id),
            "--metric",
            "cer",
            "0.081",
            "--failure-bucket",
            "low_contrast",
        ]
    )

    stdout = capsys.readouterr().out
    assert exit_code == 0
    assert "eval_result_count" in stdout
    assert "cer" not in stdout
    assert "0.081" not in stdout
    assert "low_contrast" not in stdout
