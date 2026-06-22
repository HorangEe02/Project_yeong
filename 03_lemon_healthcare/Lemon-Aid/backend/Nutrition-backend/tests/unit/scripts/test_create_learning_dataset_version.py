"""Tests for operator learning dataset version creation CLI."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from src.models.db.retraining import LearningDatasetVersion

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

dataset_cli = importlib.import_module("scripts.create_learning_dataset_version")


class _FakeSession:
    """Fake async session for dataset version creation tests."""

    def __init__(self) -> None:
        """Initialize captured writes."""
        self.added_rows: list[LearningDatasetVersion] = []
        self.commit_count = 0

    def add(self, row: LearningDatasetVersion) -> None:
        """Capture one added row.

        Args:
            row: Dataset version row.
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
        dataset_cli,
        "get_sessionmaker",
        lambda: lambda: _FakeSessionContext(session),
    )


@pytest.mark.asyncio
async def test_create_learning_dataset_version_persists_row_without_operator_hash_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify creation stores operator hash but excludes it from summary."""
    session = _FakeSession()
    created_by_hash = "d" * 64
    start = datetime(2026, 5, 1, tzinfo=UTC)
    end = datetime(2026, 5, 27, tzinfo=UTC)
    _patch_sessionmaker(monkeypatch, session)

    summary = await dataset_cli.create_learning_dataset_version(
        dataset_key="supplement_ocr_recognition",
        version="2026-05-27.3",
        status="frozen",
        privacy_review_status="approved",
        train_count=10,
        val_count=2,
        test_count=1,
        source_window_start=start,
        source_window_end=end,
        created_by_hash=created_by_hash,
    )

    assert session.commit_count == 1
    assert len(session.added_rows) == 1
    row = session.added_rows[0]
    assert row.dataset_key == "supplement_ocr_recognition"
    assert row.created_by_hash == created_by_hash
    assert row.frozen_at is not None
    assert summary["source_window_registered"] is True
    serialized = json.dumps(summary, ensure_ascii=False)
    assert created_by_hash not in serialized
    assert "raw_label" in serialized


@pytest.mark.asyncio
async def test_create_learning_dataset_version_rejects_reversed_source_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify invalid windows fail before DB writes."""
    session = _FakeSession()
    _patch_sessionmaker(monkeypatch, session)

    with pytest.raises(ValueError, match="Source window end"):
        await dataset_cli.create_learning_dataset_version(
            dataset_key="supplement_roi_detection",
            version="2026-05-27.3",
            status="draft",
            privacy_review_status="pending",
            train_count=0,
            val_count=0,
            test_count=0,
            source_window_start=datetime(2026, 5, 27, tzinfo=UTC),
            source_window_end=datetime(2026, 5, 1, tzinfo=UTC),
            created_by_hash=None,
        )

    assert session.added_rows == []
    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_run_cli_prints_sanitized_success(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI output excludes operator hash and source labels."""
    session = _FakeSession()
    created_by_hash = "e" * 64
    _patch_sessionmaker(monkeypatch, session)

    exit_code = await dataset_cli.run_cli(
        [
            "--dataset-key",
            "supplement_roi_detection",
            "--version",
            "2026-05-27.4",
            "--status",
            "frozen",
            "--privacy-review-status",
            "approved",
            "--train-count",
            "3",
            "--created-by-hash",
            created_by_hash,
        ]
    )

    stdout = capsys.readouterr().out
    assert exit_code == 0
    assert "supplement_roi_detection" in stdout
    assert created_by_hash not in stdout
    assert "operator_hash_printed" in stdout


def test_parse_datetime_requires_timezone() -> None:
    """Verify source window CLI datetimes must include timezone."""
    with pytest.raises(ValueError, match="timezone"):
        dataset_cli._parse_datetime("2026-05-27T00:00:00")


def test_nonnegative_int_rejects_negative_count() -> None:
    """Verify split counts cannot be negative."""
    with pytest.raises(argparse.ArgumentTypeError):
        dataset_cli._nonnegative_int("-1")
