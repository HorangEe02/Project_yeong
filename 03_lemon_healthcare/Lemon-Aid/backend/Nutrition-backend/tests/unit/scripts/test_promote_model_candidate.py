"""Tests for operator model promotion gate CLI."""

from __future__ import annotations

import importlib
import json
import sys
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from src.learning.retraining import MetricGateRule
from src.models.db.retraining import ModelEvalResult, ModelRegistryEntry, ModelTrainingRun

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

promotion_cli = importlib.import_module("scripts.promote_model_candidate")


class _FakeScalarResult:
    """Fake SQLAlchemy scalar result."""

    def __init__(self, rows: list[ModelEvalResult]) -> None:
        """Initialize result rows.

        Args:
            rows: Rows returned by ``all``.
        """
        self._rows = rows

    def all(self) -> list[ModelEvalResult]:
        """Return all fake rows."""
        return self._rows


class _FakeSession:
    """Fake async session for model promotion tests."""

    def __init__(
        self,
        *,
        training_run: ModelTrainingRun | None,
        model: ModelRegistryEntry | None,
        eval_results: list[ModelEvalResult],
    ) -> None:
        """Initialize fake rows.

        Args:
            training_run: Fake training run.
            model: Fake model registry entry.
            eval_results: Fake eval result rows.
        """
        self.training_run = training_run
        self.model = model
        self.eval_results = eval_results
        self.commit_count = 0

    async def get(self, model_type: object, row_id: UUID) -> object | None:
        """Return fake rows by ORM type and id.

        Args:
            model_type: ORM model class.
            row_id: Requested row id.

        Returns:
            Fake row or None.
        """
        if model_type is ModelTrainingRun and self.training_run is not None:
            return self.training_run if self.training_run.id == row_id else None
        if model_type is ModelRegistryEntry and self.model is not None:
            return self.model if self.model.id == row_id else None
        return None

    async def scalars(self, _statement: object) -> _FakeScalarResult:
        """Return fake eval result rows."""
        return _FakeScalarResult(self.eval_results)

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
    training_run_id: UUID | None = None,
    dataset_version_id: UUID | None = None,
    status: str = "succeeded",
) -> ModelTrainingRun:
    """Build a training run fixture.

    Args:
        training_run_id: Optional training run id.
        dataset_version_id: Optional dataset version id.
        status: Training run lifecycle status.

    Returns:
        Model training run fixture.
    """
    return ModelTrainingRun(
        id=training_run_id or uuid4(),
        model_family="paddleocr_rec",
        base_model="PP-OCRv5-rec",
        dataset_version_id=dataset_version_id or uuid4(),
        hyperparam_snapshot={"epochs": 5},
        metrics_snapshot={},
        status=status,
    )


def _model(
    *,
    model_id: UUID | None = None,
    training_run_id: UUID,
    status: str = "candidate",
) -> ModelRegistryEntry:
    """Build a model registry fixture.

    Args:
        model_id: Optional model id.
        training_run_id: Source training run id.
        status: Deployment status.

    Returns:
        Model registry fixture.
    """
    return ModelRegistryEntry(
        id=model_id or uuid4(),
        task_type="supplement_ocr_recognition",
        model_version="ocr-rec-2026-05-27.2",
        training_run_id=training_run_id,
        artifact_ref="models/supplement-ocr-rec/2026-05-27",
        deployment_status=status,
        metric_gate_snapshot={},
    )


def _eval_result(
    *,
    model_id: UUID,
    dataset_version_id: UUID,
    metric_name: str = "cer",
    value: Decimal = Decimal("0.081"),
) -> ModelEvalResult:
    """Build an eval result fixture.

    Args:
        model_id: Model registry id.
        dataset_version_id: Eval dataset id.
        metric_name: Metric key.
        value: Metric value.

    Returns:
        Model eval result fixture.
    """
    return ModelEvalResult(
        id=uuid4(),
        model_id=model_id,
        eval_dataset_version_id=dataset_version_id,
        metric_name=metric_name,
        metric_value=value,
    )


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    """Write a JSON fixture.

    Args:
        path: Destination path.
        payload: JSON payload.

    Returns:
        Written path.
    """
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _patch_sessionmaker(monkeypatch: pytest.MonkeyPatch, session: _FakeSession) -> None:
    """Patch the script DB session factory.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        session: Fake session.
    """
    monkeypatch.setattr(
        promotion_cli,
        "get_sessionmaker",
        lambda: lambda: _FakeSessionContext(session),
    )


@pytest.mark.asyncio
async def test_promote_model_candidate_dry_run_prints_sanitized_allowed_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify dry-run promotion evaluates metrics without mutating rows."""
    training_run = _training_run()
    model = _model(training_run_id=training_run.id)
    eval_result = _eval_result(
        model_id=model.id, dataset_version_id=training_run.dataset_version_id
    )
    session = _FakeSession(training_run=training_run, model=model, eval_results=[eval_result])
    _patch_sessionmaker(monkeypatch, session)

    summary = await promotion_cli.promote_model_candidate(
        training_run_id=training_run.id,
        model_id=model.id,
        metric_rules=[MetricGateRule("cer", "<=", Decimal("0.10"))],
        apply=False,
    )

    assert summary["allowed"] is True
    assert summary["applied"] is False
    assert model.deployment_status == "candidate"
    assert training_run.status == "succeeded"
    assert session.commit_count == 0
    serialized = json.dumps(summary, ensure_ascii=False)
    assert model.artifact_ref not in serialized
    assert "c" * 64 not in serialized


@pytest.mark.asyncio
async def test_promote_model_candidate_apply_updates_status_after_gate_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify apply persists staging promotion only after the gate passes."""
    training_run = _training_run()
    model = _model(training_run_id=training_run.id)
    eval_result = _eval_result(
        model_id=model.id, dataset_version_id=training_run.dataset_version_id
    )
    session = _FakeSession(training_run=training_run, model=model, eval_results=[eval_result])
    _patch_sessionmaker(monkeypatch, session)

    summary = await promotion_cli.promote_model_candidate(
        training_run_id=training_run.id,
        model_id=model.id,
        metric_rules=[MetricGateRule("cer", "<=", Decimal("0.10"))],
        apply=True,
        approved_by_hash="c" * 64,
    )

    assert summary["allowed"] is True
    assert summary["applied"] is True
    assert model.deployment_status == "staging"
    assert model.approved_by_hash == "c" * 64
    assert model.approved_at is not None
    assert training_run.status == "approved_for_deploy"
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_promote_model_candidate_rejects_missing_metric_without_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify missing persisted metric rows block promotion."""
    training_run = _training_run()
    model = _model(training_run_id=training_run.id)
    session = _FakeSession(training_run=training_run, model=model, eval_results=[])
    _patch_sessionmaker(monkeypatch, session)

    summary = await promotion_cli.promote_model_candidate(
        training_run_id=training_run.id,
        model_id=model.id,
        metric_rules=[MetricGateRule("cer", "<=", Decimal("0.10"))],
        apply=True,
    )

    assert summary["allowed"] is False
    assert summary["reason"] == "missing_metric:cer"
    assert summary["applied"] is False
    assert model.deployment_status == "candidate"
    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_run_cli_returns_nonzero_without_leaking_artifact_ref(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify denied CLI output is sanitized and exits nonzero."""
    training_run = _training_run()
    model = _model(training_run_id=training_run.id)
    session = _FakeSession(training_run=training_run, model=model, eval_results=[])
    _patch_sessionmaker(monkeypatch, session)

    exit_code = await promotion_cli.run_cli(
        [
            "--training-run-id",
            str(training_run.id),
            "--model-id",
            str(model.id),
            "--metric-rule",
            "cer",
            "<=",
            "0.10",
            "--apply",
        ]
    )

    stdout = capsys.readouterr().out
    assert exit_code == 1
    assert "missing_metric:cer" in stdout
    assert model.artifact_ref not in stdout
    assert "approved_by_hash" not in stdout
    assert "raw_eval_payload_stored" in stdout


@pytest.mark.asyncio
async def test_run_cli_accepts_baseline_gate_metric_rules_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify baseline gate promotion rules can drive the existing promotion CLI."""
    training_run = _training_run()
    model = _model(training_run_id=training_run.id)
    eval_results = [
        _eval_result(
            model_id=model.id,
            dataset_version_id=training_run.dataset_version_id,
            metric_name="acc",
            value=Decimal("0.93"),
        ),
        _eval_result(
            model_id=model.id,
            dataset_version_id=training_run.dataset_version_id,
            metric_name="norm_edit_dis",
            value=Decimal("0.91"),
        ),
    ]
    session = _FakeSession(training_run=training_run, model=model, eval_results=eval_results)
    _patch_sessionmaker(monkeypatch, session)
    rules_path = _write_json(
        tmp_path / "promotion-rules.json",
        {
            "schema_version": "paddleocr-promotion-metric-rules-v1",
            "allowed_by_baseline_gate": True,
            "metric_rules": [
                {"metric_name": "acc", "comparator": ">=", "threshold": "0.92"},
                {
                    "metric_name": "norm_edit_dis",
                    "comparator": ">=",
                    "threshold": "0.90",
                },
            ],
        },
    )

    exit_code = await promotion_cli.run_cli(
        [
            "--training-run-id",
            str(training_run.id),
            "--model-id",
            str(model.id),
            "--metric-rules-json",
            str(rules_path),
        ]
    )

    stdout = capsys.readouterr().out
    assert exit_code == 0
    assert '"allowed": true' in stdout
    assert '"rule_count": 2' in stdout
    assert model.artifact_ref not in stdout
    assert str(tmp_path) not in stdout


@pytest.mark.asyncio
async def test_run_cli_rejects_metric_rules_json_denied_by_baseline_gate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify denied baseline comparison artifacts cannot promote a model."""
    training_run = _training_run()
    model = _model(training_run_id=training_run.id)
    session = _FakeSession(training_run=training_run, model=model, eval_results=[])
    _patch_sessionmaker(monkeypatch, session)
    rules_path = _write_json(
        tmp_path / "promotion-rules.json",
        {
            "schema_version": "paddleocr-promotion-metric-rules-v1",
            "allowed_by_baseline_gate": False,
            "metric_rules": [
                {"metric_name": "acc", "comparator": ">=", "threshold": "0.92"},
            ],
        },
    )

    exit_code = await promotion_cli.run_cli(
        [
            "--training-run-id",
            str(training_run.id),
            "--model-id",
            str(model.id),
            "--metric-rules-json",
            str(rules_path),
            "--apply",
        ]
    )

    stdout = capsys.readouterr().out
    assert exit_code == 1
    assert "ValueError" in stdout
    assert "acc" not in stdout
    assert str(tmp_path) not in stdout
    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_run_cli_rejects_mixed_manual_and_json_metric_rules(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify operators cannot accidentally combine two gate rule sources."""
    training_run = _training_run()
    model = _model(training_run_id=training_run.id)
    session = _FakeSession(training_run=training_run, model=model, eval_results=[])
    _patch_sessionmaker(monkeypatch, session)
    rules_path = _write_json(
        tmp_path / "promotion-rules.json",
        {
            "schema_version": "paddleocr-promotion-metric-rules-v1",
            "allowed_by_baseline_gate": True,
            "metric_rules": [
                {"metric_name": "acc", "comparator": ">=", "threshold": "0.92"},
            ],
        },
    )

    exit_code = await promotion_cli.run_cli(
        [
            "--training-run-id",
            str(training_run.id),
            "--model-id",
            str(model.id),
            "--metric-rule",
            "cer",
            "<=",
            "0.10",
            "--metric-rules-json",
            str(rules_path),
        ]
    )

    stdout = capsys.readouterr().out
    assert exit_code == 1
    assert "ValueError" in stdout
    assert "cer" not in stdout
    assert str(tmp_path) not in stdout


@pytest.mark.asyncio
async def test_run_cli_rejects_unsafe_metric_names_from_rules_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify JSON metric rules cannot smuggle path-like metric keys."""
    training_run = _training_run()
    model = _model(training_run_id=training_run.id)
    session = _FakeSession(training_run=training_run, model=model, eval_results=[])
    _patch_sessionmaker(monkeypatch, session)
    rules_path = _write_json(
        tmp_path / "promotion-rules.json",
        {
            "schema_version": "paddleocr-promotion-metric-rules-v1",
            "allowed_by_baseline_gate": True,
            "metric_rules": [
                {"metric_name": "../acc", "comparator": ">=", "threshold": "0.92"},
            ],
        },
    )

    exit_code = await promotion_cli.run_cli(
        [
            "--training-run-id",
            str(training_run.id),
            "--model-id",
            str(model.id),
            "--metric-rules-json",
            str(rules_path),
        ]
    )

    stdout = capsys.readouterr().out
    assert exit_code == 1
    assert "ValueError" in stdout
    assert "../acc" not in stdout
    assert str(tmp_path) not in stdout
