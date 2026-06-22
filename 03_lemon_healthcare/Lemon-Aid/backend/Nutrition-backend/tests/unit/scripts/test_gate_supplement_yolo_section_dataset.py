"""Tests for supplement YOLO section dataset readiness gate."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

gate = importlib.import_module("scripts.gate_supplement_yolo_section_dataset")


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    """Write a JSON fixture.

    Args:
        path: Destination path.
        payload: JSON payload.

    Returns:
        Written path.
    """
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return path


def _annotation(*, ready: bool = False) -> dict[str, Any]:
    """Return an annotation preflight fixture.

    Args:
        ready: Whether strict annotation review is complete.

    Returns:
        Annotation preflight payload.
    """
    return {
        "schema_version": "supplement-yolo-annotation-decision-preflight-v1",
        "template_row_count": 2,
        "valid_accepted_row_count": 2 if ready else 0,
        "pending_review_row_count": 0 if ready else 2,
        "reviewed_box_row_count": 2 if ready else 0,
        "blank_box_row_count": 0 if ready else 2,
        "invalid_row_count": 0,
        "unpromotable_accepted_row_count": 0,
        "pending_operator_action_count": 0 if ready else 2,
        "require_all_reviewed": True,
        "ready_for_strict_promotion": ready,
        "ready_for_requested_promotion": ready,
        "db_write_performed": False,
        "training_performed": False,
        "source_image_read_performed": True,
        "source_image_read_purpose": "fixture_sha256_integrity_check_only",
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
        "source_ref_printed": False,
        "image_path_printed": False,
        "labels_printed": False,
        "source_doc_urls": [
            "https://docs.ultralytics.com/datasets/detect/",
            "https://docs.ultralytics.com/tasks/detect/",
        ],
    }


def _promotion(*, ready: bool = True, skip_count: int = 0) -> dict[str, Any]:
    """Return a template promotion summary fixture.

    Args:
        ready: Whether export and source-map writes succeeded.
        skip_count: Skipped-row count.

    Returns:
        Promotion summary payload.
    """
    return {
        "schema_version": "supplement-yolo-template-promotion-summary-v1",
        "template_row_count": 2,
        "promoted_item_count": 2,
        "limit": 500,
        "split_counts": {"train": 1, "val": 1, "test": 0, "holdout": 0},
        "skip_reason_counts": {"not_accepted_for_training": skip_count} if skip_count else {},
        "db_write_performed": False,
        "training_performed": False,
        "source_map_written": ready,
        "export_artifact_written": ready,
        "source_ref_printed": False,
        "image_path_printed": False,
        "labels_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "source_doc_urls": [
            "https://docs.ultralytics.com/datasets/detect/",
            "https://docs.ultralytics.com/tasks/detect/",
        ],
    }


def _materialized(*, ready: bool = True, val_count: int = 1) -> dict[str, Any]:
    """Return a dataset materialization summary fixture.

    Args:
        ready: Whether materialization status is ok.
        val_count: Val split count.

    Returns:
        Materialization summary payload.
    """
    item_count = 1 + val_count
    return {
        "schema_version": "supplement-section-yolo-materialize-summary-v1",
        "status": "ok" if ready else "failed",
        "dataset_yaml": "dataset.yaml",
        "item_count": item_count,
        "image_count": item_count,
        "label_count": item_count,
        "split_counts": {"train": 1, "val": val_count, "test": 0},
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "source_ref_printed": False,
        "source_path_printed": False,
    }


def _validation(*, image_count: int = 2, label_count: int = 2) -> dict[str, Any]:
    """Return a dataset validation summary fixture.

    Args:
        image_count: Validated image count.
        label_count: Validated label count.

    Returns:
        Validator CLI payload.
    """
    return {
        "ok": True,
        "dataset_yaml": "dataset.yaml",
        "required_sections": [
            "product_identity",
            "supplement_facts",
            "ingredient_amounts",
            "precautions",
            "allergen_warning",
            "intake_method",
            "other_ingredients",
            "functional_claims",
        ],
        "names": [
            "product_identity",
            "supplement_facts",
            "ingredient_amounts",
            "precautions",
            "allergen_warning",
            "intake_method",
            "other_ingredients",
            "functional_claims",
        ],
        "require_files": True,
        "image_count": image_count,
        "label_count": label_count,
    }


def test_yolo_section_dataset_gate_blocks_pending_annotation_review(tmp_path: Path) -> None:
    """Verify blank bbox review blocks YOLO dataset readiness."""
    annotation_path = _write_json(tmp_path / "annotation.json", _annotation())

    summary = gate.build_yolo_section_dataset_gate(annotation_preflight_path=annotation_path)
    markdown = gate.build_markdown(summary)
    dumped = json.dumps(summary, ensure_ascii=False) + markdown

    assert summary["schema_version"] == "supplement-yolo-section-dataset-gate-v1"
    assert summary["status"] == "blocked_by_annotation_review"
    assert summary["strict_annotation_ready"] is False
    assert summary["section_yolo_training_allowed_now"] is False
    assert summary["model_promotion_allowed_now"] is False
    assert summary["official_yolo26_detect_reference_verified"] is True
    assert summary["yolo26_pretrained_checkpoint_allowed_for_initialization"] is True
    assert summary["coco_pretrained_allowed_for_final_section_labels"] is False
    assert summary["custom_supplement_section_dataset_required"] is True
    assert summary["section_predictions_review_required_until_metric_gate"] is True
    assert summary["model_promotion_requires_separate_metric_gate"] is True
    assert summary["input_path_hashes"]["annotation_preflight"].startswith("fp-")
    assert len(summary["input_path_hashes"]["annotation_preflight"]) == 15
    assert "COCO pretrained allowed for final section labels: `false`" in markdown
    assert str(tmp_path) not in dumped
    assert "/Volumes/" not in dumped


def test_yolo_section_dataset_gate_blocks_until_template_promotion(tmp_path: Path) -> None:
    """Verify strict annotations still require template promotion."""
    annotation_path = _write_json(tmp_path / "annotation.json", _annotation(ready=True))

    summary = gate.build_yolo_section_dataset_gate(annotation_preflight_path=annotation_path)

    assert summary["status"] == "blocked_by_template_promotion"
    assert summary["strict_annotation_ready"] is True
    assert summary["template_promotion_ready"] is False


def test_yolo_section_dataset_gate_blocks_until_materialized_dataset(tmp_path: Path) -> None:
    """Verify promoted annotations still require materialized YOLO files."""
    annotation_path = _write_json(tmp_path / "annotation.json", _annotation(ready=True))
    promotion_path = _write_json(tmp_path / "promotion.json", _promotion())

    summary = gate.build_yolo_section_dataset_gate(
        annotation_preflight_path=annotation_path,
        template_promotion_summary_path=promotion_path,
    )

    assert summary["status"] == "blocked_by_dataset_materialization"
    assert summary["template_promotion_ready"] is True
    assert summary["dataset_materialization_ready"] is False


def test_yolo_section_dataset_gate_blocks_dataset_without_val_split(tmp_path: Path) -> None:
    """Verify train-only datasets cannot pass the YOLO training gate."""
    annotation_path = _write_json(tmp_path / "annotation.json", _annotation(ready=True))
    promotion = _promotion()
    promotion["split_counts"] = {"train": 2, "val": 0, "test": 0, "holdout": 0}
    promotion_path = _write_json(tmp_path / "promotion.json", promotion)
    materialized_path = _write_json(tmp_path / "materialized.json", _materialized(val_count=0))

    summary = gate.build_yolo_section_dataset_gate(
        annotation_preflight_path=annotation_path,
        template_promotion_summary_path=promotion_path,
        dataset_materialize_summary_path=materialized_path,
    )

    assert summary["status"] == "blocked_by_template_promotion"
    assert summary["section_yolo_training_allowed_now"] is False
    assert summary["promotion_val_split_count"] == 0


def test_yolo_section_dataset_gate_requires_dataset_validation_summary(
    tmp_path: Path,
) -> None:
    """Verify materialized datasets still need require-files validation."""
    annotation_path = _write_json(tmp_path / "annotation.json", _annotation(ready=True))
    promotion_path = _write_json(tmp_path / "promotion.json", _promotion())
    materialized_path = _write_json(tmp_path / "materialized.json", _materialized())

    summary = gate.build_yolo_section_dataset_gate(
        annotation_preflight_path=annotation_path,
        template_promotion_summary_path=promotion_path,
        dataset_materialize_summary_path=materialized_path,
    )

    assert summary["status"] == "blocked_by_dataset_validation"
    assert summary["dataset_materialization_ready"] is True
    assert summary["dataset_validation_ready"] is False
    assert summary["validation_summary_provided"] is False
    assert summary["section_yolo_training_allowed_now"] is False
    assert summary["missing_required_section_labels"] == list(gate.REQUIRED_SECTION_LABELS)


def test_yolo_section_dataset_gate_blocks_mismatched_validation_summary(tmp_path: Path) -> None:
    """Verify require-files validation must match materialized counts."""
    annotation_path = _write_json(tmp_path / "annotation.json", _annotation(ready=True))
    promotion_path = _write_json(tmp_path / "promotion.json", _promotion())
    materialized_path = _write_json(tmp_path / "materialized.json", _materialized())
    validation_path = _write_json(tmp_path / "validation.json", _validation(image_count=1))

    summary = gate.build_yolo_section_dataset_gate(
        annotation_preflight_path=annotation_path,
        template_promotion_summary_path=promotion_path,
        dataset_materialize_summary_path=materialized_path,
        dataset_validation_summary_path=validation_path,
    )

    assert summary["status"] == "blocked_by_dataset_validation"
    assert summary["dataset_materialization_ready"] is True
    assert summary["dataset_validation_ready"] is False


def test_yolo_section_dataset_gate_blocks_validation_missing_allergen_class(
    tmp_path: Path,
) -> None:
    """Verify allergen-warning bbox class is required before YOLO training."""
    annotation_path = _write_json(tmp_path / "annotation.json", _annotation(ready=True))
    promotion_path = _write_json(tmp_path / "promotion.json", _promotion())
    materialized_path = _write_json(tmp_path / "materialized.json", _materialized())
    validation = _validation()
    validation["required_sections"] = [
        "product_identity",
        "supplement_facts",
        "ingredient_amounts",
        "precautions",
        "intake_method",
        "other_ingredients",
        "functional_claims",
    ]
    validation["names"] = list(validation["required_sections"])
    validation_path = _write_json(tmp_path / "validation.json", validation)

    summary = gate.build_yolo_section_dataset_gate(
        annotation_preflight_path=annotation_path,
        template_promotion_summary_path=promotion_path,
        dataset_materialize_summary_path=materialized_path,
        dataset_validation_summary_path=validation_path,
    )

    assert summary["status"] == "blocked_by_dataset_validation"
    assert summary["dataset_validation_ready"] is False
    assert summary["missing_required_section_labels"] == ["allergen_warning"]


def test_yolo_section_dataset_gate_allows_training_dataset_after_all_checks(
    tmp_path: Path,
) -> None:
    """Verify complete summaries allow YOLO training but not model promotion."""
    annotation_path = _write_json(tmp_path / "annotation.json", _annotation(ready=True))
    promotion_path = _write_json(tmp_path / "promotion.json", _promotion())
    materialized_path = _write_json(tmp_path / "materialized.json", _materialized())
    validation_path = _write_json(tmp_path / "validation.json", _validation())

    summary = gate.build_yolo_section_dataset_gate(
        annotation_preflight_path=annotation_path,
        template_promotion_summary_path=promotion_path,
        dataset_materialize_summary_path=materialized_path,
        dataset_validation_summary_path=validation_path,
    )

    assert summary["status"] == "ready_for_section_yolo_training_dataset"
    assert summary["strict_annotation_ready"] is True
    assert summary["template_promotion_ready"] is True
    assert summary["dataset_materialization_ready"] is True
    assert summary["dataset_validation_ready"] is True
    assert summary["section_yolo_training_allowed_now"] is True
    assert summary["model_promotion_allowed_now"] is False
    assert summary["missing_required_section_labels"] == []
    assert "allergen_warning" in summary["required_section_labels"]
    assert summary["official_yolo26_detect_reference_verified"] is True
    assert summary["yolo26_pretrained_checkpoint_allowed_for_initialization"] is True
    assert summary["coco_pretrained_allowed_for_final_section_labels"] is False
    assert summary["custom_supplement_section_dataset_required"] is True
    assert summary["section_predictions_review_required_until_metric_gate"] is True
    assert summary["model_promotion_requires_separate_metric_gate"] is True


def test_yolo_section_dataset_gate_rejects_unsafe_payload(tmp_path: Path) -> None:
    """Verify raw/provider payload keys fail closed."""
    annotation = _annotation(ready=True)
    annotation["raw_ocr_text"] = "unsafe"
    annotation_path = _write_json(tmp_path / "annotation.json", annotation)

    with pytest.raises(gate.YoloSectionDatasetGateError, match="unsafe raw key"):
        gate.build_yolo_section_dataset_gate(annotation_preflight_path=annotation_path)


def test_yolo_section_dataset_gate_cli_writes_redacted_outputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI writes JSON and Markdown without local paths."""
    annotation_path = _write_json(tmp_path / "annotation.json", _annotation(ready=True))
    promotion_path = _write_json(tmp_path / "promotion.json", _promotion())
    materialized_path = _write_json(tmp_path / "materialized.json", _materialized())
    validation_path = _write_json(tmp_path / "validation.json", _validation())
    output_path = tmp_path / "gate.json"
    markdown_path = tmp_path / "gate.md"

    gate.main(
        [
            "--annotation-preflight",
            str(annotation_path),
            "--template-promotion-summary",
            str(promotion_path),
            "--dataset-materialize-summary",
            str(materialized_path),
            "--dataset-validation-summary",
            str(validation_path),
            "--output",
            str(output_path),
            "--markdown-output",
            str(markdown_path),
        ]
    )

    stdout = capsys.readouterr().out
    summary = json.loads(output_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert summary["status"] == "ready_for_section_yolo_training_dataset"
    assert "Supplement YOLO Section Dataset Gate" in markdown
    assert "## YOLO26 Policy" in markdown
    assert "COCO pretrained allowed for final section labels: `false`" in markdown
    assert '"coco_pretrained_allowed_for_final_section_labels": false' in stdout
    assert '"custom_supplement_section_dataset_required": true' in stdout
    assert '"image_count": 2' in stdout
    assert str(tmp_path) not in stdout + markdown + json.dumps(summary, ensure_ascii=False)
