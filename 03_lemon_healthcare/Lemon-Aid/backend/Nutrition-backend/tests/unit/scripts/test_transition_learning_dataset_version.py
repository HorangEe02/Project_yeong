"""Tests for operator learning dataset lifecycle transition CLI."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from src.models.db.retraining import LearningDatasetVersion

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

transition_cli = importlib.import_module("scripts.transition_learning_dataset_version")


class _FakeSession:
    """Fake async session for dataset transition tests."""

    def __init__(self, dataset_version: LearningDatasetVersion | None) -> None:
        """Initialize fake dataset row.

        Args:
            dataset_version: Dataset version returned by ``get``.
        """
        self.dataset_version = dataset_version
        self.commit_count = 0

    async def get(self, model_type: type[object], row_id: UUID) -> object | None:
        """Return a fake dataset version when requested.

        Args:
            model_type: SQLAlchemy model type.
            row_id: Requested row id.

        Returns:
            Fake dataset version or None.
        """
        if (
            model_type is LearningDatasetVersion
            and self.dataset_version is not None
            and self.dataset_version.id == row_id
        ):
            return self.dataset_version
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


def _dataset_version(
    *,
    status: str = "draft",
    privacy_review_status: str = "pending",
    manifest_hash: str | None = None,
) -> LearningDatasetVersion:
    """Build a fake dataset version.

    Args:
        status: Dataset lifecycle status.
        privacy_review_status: Privacy review lifecycle status.
        manifest_hash: Optional sanitized manifest hash.

    Returns:
        Fake dataset version.
    """
    return LearningDatasetVersion(
        id=uuid4(),
        dataset_key="supplement_ocr_recognition",
        version="2026-05-27.1",
        status=status,
        train_count=10,
        val_count=2,
        test_count=1,
        privacy_review_status=privacy_review_status,
        manifest_hash=manifest_hash,
        created_by_hash="a" * 64,
    )


def _patch_sessionmaker(monkeypatch: pytest.MonkeyPatch, session: _FakeSession) -> None:
    """Patch the script DB session factory.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        session: Fake session.
    """
    monkeypatch.setattr(
        transition_cli,
        "get_sessionmaker",
        lambda: lambda: _FakeSessionContext(session),
    )


@pytest.mark.asyncio
async def test_transition_dataset_freezes_after_privacy_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify draft datasets can freeze only with privacy approval."""
    dataset_version = _dataset_version(status="draft", privacy_review_status="pending")
    session = _FakeSession(dataset_version)
    _patch_sessionmaker(monkeypatch, session)

    summary = await transition_cli.transition_learning_dataset_version(
        dataset_version_id=dataset_version.id,
        target_status="frozen",
        privacy_review_status="approved",
        manifest_hash=None,
        apply=True,
    )

    assert summary["allowed"] is True
    assert summary["applied"] is True
    assert dataset_version.status == "frozen"
    assert dataset_version.privacy_review_status == "approved"
    assert dataset_version.frozen_at is not None
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_transition_dataset_training_requires_manifest_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify training cannot start without a sanitized manifest hash."""
    dataset_version = _dataset_version(status="frozen", privacy_review_status="approved")
    session = _FakeSession(dataset_version)
    _patch_sessionmaker(monkeypatch, session)

    summary = await transition_cli.transition_learning_dataset_version(
        dataset_version_id=dataset_version.id,
        target_status="training",
        privacy_review_status=None,
        manifest_hash=None,
        apply=True,
    )

    assert summary["allowed"] is False
    assert summary["reason"] == "manifest_hash_required"
    assert dataset_version.status == "frozen"
    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_transition_dataset_training_stores_manifest_hash_without_printing_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify manifest hash can be stored while stdout stays redacted."""
    manifest_hash = "b" * 64
    dataset_version = _dataset_version(status="frozen", privacy_review_status="approved")
    session = _FakeSession(dataset_version)
    _patch_sessionmaker(monkeypatch, session)

    summary = await transition_cli.transition_learning_dataset_version(
        dataset_version_id=dataset_version.id,
        target_status="training",
        privacy_review_status=None,
        manifest_hash=manifest_hash,
        apply=True,
    )

    assert summary["allowed"] is True
    assert summary["manifest_hash_present"] is True
    assert dataset_version.status == "training"
    assert dataset_version.manifest_hash == manifest_hash
    assert session.commit_count == 1
    serialized = json.dumps(summary, ensure_ascii=False)
    assert manifest_hash not in serialized
    assert str(dataset_version.created_by_hash) not in serialized


@pytest.mark.asyncio
async def test_transition_dataset_rejects_invalid_status_jump(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify lifecycle jumps cannot skip required review states."""
    dataset_version = _dataset_version(status="draft", privacy_review_status="approved")
    session = _FakeSession(dataset_version)
    _patch_sessionmaker(monkeypatch, session)

    summary = await transition_cli.transition_learning_dataset_version(
        dataset_version_id=dataset_version.id,
        target_status="approved",
        privacy_review_status=None,
        manifest_hash="c" * 64,
        apply=True,
    )

    assert summary["allowed"] is False
    assert summary["reason"] == "transition_not_allowed"
    assert dataset_version.status == "draft"
    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_transition_dataset_retires_without_manifest_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify retirement can stop an unsafe dataset without a manifest hash."""
    dataset_version = _dataset_version(status="draft", privacy_review_status="rejected")
    session = _FakeSession(dataset_version)
    _patch_sessionmaker(monkeypatch, session)

    summary = await transition_cli.transition_learning_dataset_version(
        dataset_version_id=dataset_version.id,
        target_status="retired",
        privacy_review_status="rejected",
        manifest_hash=None,
        apply=True,
    )

    assert summary["allowed"] is True
    assert dataset_version.status == "retired"
    assert dataset_version.privacy_review_status == "rejected"
    assert session.commit_count == 1


def test_validate_static_inputs_rejects_non_sha256_manifest_hash() -> None:
    """Verify manifest hashes must be lowercase SHA-256 hex."""
    with pytest.raises(ValueError, match="SHA-256"):
        transition_cli._validate_static_inputs(
            target_status="training",
            privacy_review_status=None,
            manifest_hash="not-a-hash",
        )


@pytest.mark.asyncio
async def test_run_cli_prints_sanitized_success(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI stdout excludes manifest hash and operator hash."""
    manifest_hash = "d" * 64
    dataset_version = _dataset_version(status="frozen", privacy_review_status="approved")
    session = _FakeSession(dataset_version)
    _patch_sessionmaker(monkeypatch, session)

    exit_code = await transition_cli.run_cli(
        [
            "--dataset-version-id",
            str(dataset_version.id),
            "--target-status",
            "training",
            "--manifest-hash",
            manifest_hash,
            "--apply",
        ]
    )

    stdout = capsys.readouterr().out
    assert exit_code == 0
    assert "manifest_hash_present" in stdout
    assert manifest_hash not in stdout
    assert str(dataset_version.created_by_hash) not in stdout
