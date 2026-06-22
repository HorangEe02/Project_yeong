"""Tests for operator model retirement CLI."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from src.learning.retraining import RetrainingSecurityError
from src.models.db.retraining import ModelRegistryEntry

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

retirement_cli = importlib.import_module("scripts.retire_model_version")


class _FakeSession:
    """Fake async session for model retirement tests."""

    def __init__(self, models: list[ModelRegistryEntry]) -> None:
        """Initialize fake model rows.

        Args:
            models: Model registry rows addressable by id.
        """
        self.models = {model.id: model for model in models}
        self.commit_count = 0

    async def get(self, model_type: type[object], row_id: UUID) -> object | None:
        """Return a fake model registry row when requested.

        Args:
            model_type: SQLAlchemy model type.
            row_id: Requested row id.

        Returns:
            Fake model registry row or None.
        """
        if model_type is ModelRegistryEntry:
            return self.models.get(row_id)
        return None

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


def _model(
    *,
    task_type: str = "supplement_ocr_recognition",
    status: str = "staging",
) -> ModelRegistryEntry:
    """Build a fake model registry row.

    Args:
        task_type: Deployable task type.
        status: Deployment lifecycle status.

    Returns:
        Fake model registry entry.
    """
    return ModelRegistryEntry(
        id=uuid4(),
        task_type=task_type,
        model_version="paddleocr-rec-2026.05.27",
        training_run_id=uuid4(),
        artifact_ref="models/supplement-ocr-rec/2026-05-27",
        deployment_status=status,
        metric_gate_snapshot={"schema_version": "learning-model-promotion-gate-v1"},
    )


def _patch_sessionmaker(monkeypatch: pytest.MonkeyPatch, session: _FakeSession) -> None:
    """Patch the script DB session factory.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        session: Fake session.
    """
    monkeypatch.setattr(
        retirement_cli,
        "get_sessionmaker",
        lambda: lambda: _FakeSessionContext(session),
    )


@pytest.mark.asyncio
async def test_retire_model_version_dry_run_does_not_mutate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify dry-run reports readiness without DB writes."""
    model = _model(status="staging")
    session = _FakeSession([model])
    _patch_sessionmaker(monkeypatch, session)

    summary = await retirement_cli.retire_model_version(
        model_id=model.id,
        reason_code="low_holdout_quality",
        rollback_model_id=None,
        apply=False,
    )

    assert summary["allowed"] is True
    assert summary["applied"] is False
    assert summary["dry_run"] is True
    assert model.deployment_status == "staging"
    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_retire_model_version_apply_records_sanitized_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify applying retirement stores only sanitized metadata."""
    model = _model(status="staging")
    session = _FakeSession([model])
    _patch_sessionmaker(monkeypatch, session)

    summary = await retirement_cli.retire_model_version(
        model_id=model.id,
        reason_code="low_holdout_quality",
        rollback_model_id=None,
        apply=True,
    )

    assert session.commit_count == 1
    assert model.deployment_status == "retired"
    assert model.metric_gate_snapshot["retirement"] == {
        "schema_version": "model-retirement-snapshot-v1",
        "reason_code": "low_holdout_quality",
        "previous_deployment_status": "staging",
        "rollback_model_id": None,
    }
    assert summary["applied"] is True
    serialized = json.dumps(summary, ensure_ascii=False)
    assert str(model.artifact_ref) not in serialized
    assert "low_holdout_quality" not in serialized


@pytest.mark.asyncio
async def test_retire_production_model_requires_rollback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify production retirement fails closed without a rollback target."""
    model = _model(status="production")
    session = _FakeSession([model])
    _patch_sessionmaker(monkeypatch, session)

    summary = await retirement_cli.retire_model_version(
        model_id=model.id,
        reason_code="bad_release",
        rollback_model_id=None,
        apply=True,
    )

    assert summary["allowed"] is False
    assert summary["reason"] == "production_requires_rollback"
    assert model.deployment_status == "production"
    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_retire_production_model_accepts_same_task_rollback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify production retirement can point to a same-task rollback model."""
    model = _model(status="production")
    rollback_model = _model(status="staging")
    session = _FakeSession([model, rollback_model])
    _patch_sessionmaker(monkeypatch, session)

    summary = await retirement_cli.retire_model_version(
        model_id=model.id,
        reason_code="bad_release",
        rollback_model_id=rollback_model.id,
        apply=True,
    )

    assert summary["allowed"] is True
    assert summary["applied"] is True
    assert model.deployment_status == "retired"
    assert model.rollback_model_id == rollback_model.id
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_retire_model_rejects_cross_task_rollback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify rollback targets cannot cross task boundaries."""
    model = _model(status="production")
    rollback_model = _model(task_type="supplement_roi_detection", status="staging")
    session = _FakeSession([model, rollback_model])
    _patch_sessionmaker(monkeypatch, session)

    with pytest.raises(ValueError, match="task type"):
        await retirement_cli.retire_model_version(
            model_id=model.id,
            reason_code="bad_release",
            rollback_model_id=rollback_model.id,
            apply=True,
        )

    assert model.deployment_status == "production"
    assert session.commit_count == 0


def test_validate_reason_code_rejects_unsafe_value() -> None:
    """Verify reason codes cannot carry paths, URLs, or free text."""
    with pytest.raises(RetrainingSecurityError, match="stable safe"):
        retirement_cli._validate_reason_code("../bad-release")


@pytest.mark.asyncio
async def test_run_cli_prints_sanitized_success(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI stdout excludes artifact refs and operator reason codes."""
    model = _model(status="staging")
    session = _FakeSession([model])
    _patch_sessionmaker(monkeypatch, session)

    exit_code = await retirement_cli.run_cli(
        [
            "--model-id",
            str(model.id),
            "--reason-code",
            "low_holdout_quality",
            "--apply",
        ]
    )

    stdout = capsys.readouterr().out
    assert exit_code == 0
    assert "artifact_ref_printed" in stdout
    assert str(model.artifact_ref) not in stdout
    assert "low_holdout_quality" not in stdout
