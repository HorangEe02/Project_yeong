"""Tests for the PaddleOCR rec dataset count gate."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

validator = importlib.import_module("scripts.validate_paddleocr_rec_dataset_counts")


def _write_dataset(dataset_dir: Path, *, train: int, val: int, dict_rows: int) -> None:
    """Write a minimal private-shape dataset with placeholder rows.

    Args:
        dataset_dir: Dataset root.
        train: Train row count.
        val: Validation row count.
        dict_rows: Dictionary row count.
    """
    rec_dir = dataset_dir / "rec"
    rec_dir.mkdir(parents=True)
    (rec_dir / "rec_gt_train.txt").write_text("x\tplaceholder\n" * train, encoding="utf-8")
    (rec_dir / "rec_gt_val.txt").write_text("x\tplaceholder\n" * val, encoding="utf-8")
    (dataset_dir / "dict.txt").write_text("x\n" * dict_rows, encoding="utf-8")


def test_count_gate_passes_with_expected_counts(tmp_path: Path) -> None:
    """Verify expected train/val/dict counts pass without exposing labels."""
    dataset_dir = tmp_path / "dataset"
    _write_dataset(dataset_dir, train=2, val=1, dict_rows=3)

    summary = validator.validate_paddleocr_rec_dataset_counts(
        dataset_dir=dataset_dir,
        expected_train_rows=2,
        expected_val_rows=1,
        expected_dict_rows=3,
    )
    serialized = json.dumps(summary, ensure_ascii=False, sort_keys=True)

    assert summary["passed"] is True
    assert summary["actual"] == {"train": 2, "val": 1, "dict": 3}
    assert summary["label_text_printed"] is False
    assert summary["crop_paths_printed"] is False
    assert "placeholder" not in serialized
    assert str(dataset_dir) not in serialized


def test_count_gate_fails_with_count_mismatch(tmp_path: Path) -> None:
    """Verify a count mismatch fails with count-only details."""
    dataset_dir = tmp_path / "dataset"
    _write_dataset(dataset_dir, train=2, val=1, dict_rows=3)

    with pytest.raises(validator.DatasetCountValidationError) as exc_info:
        validator.validate_paddleocr_rec_dataset_counts(
            dataset_dir=dataset_dir,
            expected_train_rows=3,
            expected_val_rows=1,
            expected_dict_rows=3,
        )

    summary = json.loads(str(exc_info.value))
    serialized = json.dumps(summary, ensure_ascii=False, sort_keys=True)
    assert summary["passed"] is False
    assert summary["mismatches"] == {"train": {"expected": 3, "actual": 2}}
    assert "placeholder" not in serialized
    assert str(dataset_dir) not in serialized


def test_count_gate_reports_missing_files_without_paths(tmp_path: Path) -> None:
    """Verify missing files fail without leaking local paths."""
    dataset_dir = tmp_path / "dataset"
    (dataset_dir / "rec").mkdir(parents=True)

    with pytest.raises(validator.DatasetCountValidationError) as exc_info:
        validator.validate_paddleocr_rec_dataset_counts(dataset_dir=dataset_dir)

    summary = json.loads(str(exc_info.value))
    serialized = json.dumps(summary, ensure_ascii=False, sort_keys=True)
    assert summary["passed"] is False
    assert summary["missing_files"] == ["train", "val", "dict"]
    assert str(dataset_dir) not in serialized
