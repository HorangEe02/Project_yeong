"""Tests for the hard-case PaddleOCR line dataset builder."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

builder = importlib.import_module("scripts.build_paddleocr_hardcase_line_dataset")


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    """Write a JSON fixture."""
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> Path:
    """Write a JSONL fixture."""
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    return path


def test_holdout_hardcase_requires_explicit_acknowledgement(tmp_path: Path) -> None:
    """Verify holdout-derived hardcase data cannot be built silently."""
    manifest = _write_json(
        tmp_path / "hardcases.json",
        {
            "eval_split": "holdout",
            "fixture_ids": {"ingredient_all_missed": ["fixture-1"]},
        },
    )
    gt = _write_jsonl(tmp_path / "gt.jsonl", [])

    try:
        builder.build_hardcase_line_dataset(
            hardcase_manifest_path=manifest,
            ground_truth_jsonl_path=gt,
            output_dir=tmp_path / "dataset",
            repeat_per_label=1,
            val_ratio=0.1,
            seed=1,
            acknowledge_holdout_leakage=False,
        )
    except builder.HardcaseDatasetError as exc:
        assert "holdout/test" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("expected holdout leakage guard")


def test_require_train_source_rejects_holdout_even_with_acknowledgement(tmp_path: Path) -> None:
    """Verify train-only stage datasets cannot be built from holdout manifests."""
    manifest = _write_json(
        tmp_path / "hardcases.json",
        {
            "eval_split": "holdout",
            "fixture_ids": {"ingredient_all_missed": ["fixture-1"]},
        },
    )
    gt = _write_jsonl(tmp_path / "gt.jsonl", [])

    try:
        builder.build_hardcase_line_dataset(
            hardcase_manifest_path=manifest,
            ground_truth_jsonl_path=gt,
            output_dir=tmp_path / "dataset",
            repeat_per_label=1,
            val_ratio=0.1,
            seed=1,
            acknowledge_holdout_leakage=True,
            require_train_source=True,
        )
    except builder.HardcaseDatasetError as exc:
        assert "eval_split=train" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("expected train-source guard")


def test_builds_dataset_without_printing_labels(tmp_path: Path) -> None:
    """Verify the builder writes PaddleOCR files and a safe count summary."""
    manifest = _write_json(
        tmp_path / "hardcases.json",
        {
            "eval_split": "holdout",
            "fixture_ids": {"ingredient_all_missed": ["fixture-1"]},
        },
    )
    gt = _write_jsonl(
        tmp_path / "gt.jsonl",
        [
            {
                "fixture_id": "fixture-1",
                "expected": {
                    "product_name": "제품A",
                    "ingredients": [
                        {
                            "display_name": "마그네슘",
                            "original_name": "Magnesium",
                            "amount": "100",
                            "unit": "mg",
                        }
                    ],
                },
            }
        ],
    )

    summary = builder.build_hardcase_line_dataset(
        hardcase_manifest_path=manifest,
        ground_truth_jsonl_path=gt,
        output_dir=tmp_path / "dataset",
        repeat_per_label=2,
        val_ratio=0.25,
        seed=1,
        acknowledge_holdout_leakage=True,
    )

    assert summary["production_gate_eligible"] is False
    assert summary["label_text_printed"] is False
    assert summary["matched_fixture_count"] == 1
    assert (tmp_path / "dataset" / "rec" / "rec_gt_train.txt").is_file()
    assert (tmp_path / "dataset" / "rec" / "rec_gt_val.txt").is_file()
    assert (tmp_path / "dataset" / "dict.txt").is_file()


def test_builds_train_source_dataset_as_production_candidate_input(tmp_path: Path) -> None:
    """Verify train split hardcases can be built with the stricter guard."""
    manifest = _write_json(
        tmp_path / "hardcases.json",
        {
            "eval_split": "train",
            "fixture_ids": {"ingredient_all_missed": ["fixture-1"]},
        },
    )
    gt = _write_jsonl(
        tmp_path / "gt.jsonl",
        [
            {
                "fixture_id": "fixture-1",
                "expected": {
                    "ingredients": [
                        {
                            "display_name": "Vitamin C",
                            "amount": "100",
                            "unit": "mg",
                        }
                    ],
                },
            }
        ],
    )

    summary = builder.build_hardcase_line_dataset(
        hardcase_manifest_path=manifest,
        ground_truth_jsonl_path=gt,
        output_dir=tmp_path / "dataset-train",
        repeat_per_label=1,
        val_ratio=0.5,
        seed=1,
        acknowledge_holdout_leakage=False,
        require_train_source=True,
    )

    assert summary["train_source_required"] is True
    assert summary["production_gate_eligible"] is True
    assert summary["source_eval_split"] == "train"
