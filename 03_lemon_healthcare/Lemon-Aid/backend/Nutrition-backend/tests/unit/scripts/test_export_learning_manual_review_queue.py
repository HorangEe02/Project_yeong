"""Tests for sanitized learning manual-review queue export."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

queue_exporter = importlib.import_module("scripts.export_learning_manual_review_queue")


class _FakeScalarResult:
    """Fake SQLAlchemy scalar result."""

    def __init__(self, rows: list[object]) -> None:
        """Initialize result rows.

        Args:
            rows: Rows returned by ``all``.
        """
        self._rows = rows

    def all(self) -> list[object]:
        """Return all fake rows."""
        return self._rows


class _FakeSession:
    """Fake async session for queue export tests."""

    def __init__(self, rows: list[object]) -> None:
        """Initialize session rows.

        Args:
            rows: Rows returned by ``scalars``.
        """
        self.rows = rows

    async def scalars(self, _statement: object) -> _FakeScalarResult:
        """Return fake scalar rows."""
        return _FakeScalarResult(self.rows)


class _FakeSessionContext:
    """Fake async session context manager."""

    def __init__(self, rows: list[object]) -> None:
        """Initialize context rows.

        Args:
            rows: Rows returned by the fake session.
        """
        self.session = _FakeSession(rows)

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


def _pending_image_object(**overrides: object) -> SimpleNamespace:
    """Return a fake pending learning image object.

    Args:
        **overrides: Attribute overrides.

    Returns:
        Fake image object.
    """
    now = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
    values: dict[str, object] = {
        "id": uuid4(),
        "analysis_id": uuid4(),
        "status": "pending_manual_review",
        "object_storage_provider": "supabase_s3",
        "image_mime_type": "image/png",
        "image_size_bytes": 12345,
        "retained_until": now + timedelta(days=30),
        "created_at": now,
        "review_metadata_snapshot": {
            "display_name": "Private User Supplement",
            "manufacturer": "Internal Label",
            "ingredients": [{"display_name": "Vitamin C"}],
            "source_analysis_run_id": str(uuid4()),
        },
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_export_manual_review_queue_omits_private_storage_and_metadata_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify queue export gives review IDs without object URIs or metadata values."""
    image_object = _pending_image_object()
    monkeypatch.setattr(
        queue_exporter,
        "get_sessionmaker",
        lambda: lambda: _FakeSessionContext([image_object]),
    )

    rows, summary = await queue_exporter.export_manual_review_queue(limit=10)

    assert summary["row_count"] == 1
    assert rows[0]["image_object_id"] == str(image_object.id)
    assert rows[0]["metadata_summary"] == {
        "top_level_keys": [
            "display_name",
            "ingredients",
            "manufacturer",
            "source_analysis_run_id",
        ],
        "top_level_key_count": 4,
        "ingredient_count": 1,
        "has_display_name": True,
        "has_manufacturer": True,
        "has_source_analysis_run_id": True,
        "has_matched_product_id": False,
    }
    serialized_rows = json.dumps(rows, ensure_ascii=False)
    assert "Private User Supplement" not in serialized_rows
    assert "Internal Label" not in serialized_rows
    assert "Vitamin C" not in serialized_rows
    assert "object_uri" not in serialized_rows
    assert "owner_subject_hash" not in serialized_rows
    assert "s3://" not in serialized_rows


def test_main_writes_queue_and_summary_without_printing_private_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI output is a redacted summary and artifacts are JSON-safe."""
    image_object = _pending_image_object()
    output_path = tmp_path / "queue.jsonl"
    monkeypatch.setattr(
        queue_exporter,
        "get_sessionmaker",
        lambda: lambda: _FakeSessionContext([image_object]),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "export_learning_manual_review_queue.py",
            "--output",
            str(output_path),
            "--limit",
            "10",
        ],
    )

    queue_exporter.main()

    stdout = capsys.readouterr().out
    assert "row_count" in stdout
    assert str(tmp_path) not in stdout
    assert "/private/" not in stdout
    assert output_path.exists()
    assert output_path.with_suffix(".jsonl.summary.json").exists()
    serialized_output = output_path.read_text(encoding="utf-8")
    assert "Private User Supplement" not in serialized_output
    assert "object_uri" not in serialized_output
    assert "s3://" not in serialized_output


def test_reject_unsafe_output_blocks_raw_metadata_key_name() -> None:
    """Verify forbidden raw key names cannot leak through metadata key summaries."""
    for key in ("raw_ocr_text", "rawOcrText", "raw-ocr-text", "providerPayload"):
        with pytest.raises(ValueError, match="Unsafe manual review queue output"):
            queue_exporter._reject_unsafe_output({"top_level_keys": [key]})


def test_bounded_limit_rejects_unbounded_queue_export() -> None:
    """Verify manual-review queue exports stay bounded."""
    with pytest.raises(argparse.ArgumentTypeError):
        queue_exporter._bounded_limit("0")
    with pytest.raises(argparse.ArgumentTypeError):
        queue_exporter._bounded_limit("501")
