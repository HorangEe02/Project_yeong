"""Tests for supplement learning dependency audit reports."""

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

audit = importlib.import_module("scripts.build_supplement_learning_dependency_audit")


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


def _progress(*, complete_pii: bool = False) -> dict[str, Any]:
    """Return a batch progress fixture.

    Args:
        complete_pii: Whether the PII queue has no incomplete batch.

    Returns:
        Batch progress payload.
    """
    pii_status = "complete" if complete_pii else "pending"
    pii_blank = 0 if complete_pii else 50
    batches = [
        _batch("brand_product_review:001", "brand_product_review", "pending", 50, 1, 50),
        _batch("review_pii_screening:001", "review_pii_screening", pii_status, pii_blank, 1, 50),
        _batch("yolo_section_annotation:001", "yolo_section_annotation", "pending", 50, 1, 50),
    ]
    complete_count = sum(1 for row in batches if row["batch_status"] == "complete")
    pending_count = len(batches) - complete_count
    return {
        "schema_version": "supplement-operator-review-batch-progress-preflight-v1",
        "batch_count": len(batches),
        "complete_batch_count": complete_count,
        "pending_batch_count": pending_count,
        "invalid_batch_count": 0,
        "all_batches_complete": False,
        "next_incomplete_batch_key": "brand_product_review:001",
        "total_expected_row_count": 150,
        "total_valid_row_count": 0,
        "total_blank_row_count": sum(row["blank_row_count"] for row in batches),
        "total_pending_row_count": 0,
        "total_invalid_row_count": 0,
        "total_missing_row_count": 0,
        "aggregate_reason_counts": {"blank_decision": 100},
        "batches": batches,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "source_image_read_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }


def _batch(
    batch_key: str,
    queue_key: str,
    status: str,
    blank_count: int,
    row_start: int,
    row_end: int,
) -> dict[str, Any]:
    """Return a batch progress row.

    Args:
        batch_key: Batch key.
        queue_key: Queue key.
        status: Batch status.
        blank_count: Blank row count.
        row_start: First row index.
        row_end: Last row index.

    Returns:
        Batch row.
    """
    expected_count = row_end - row_start + 1
    valid_count = expected_count if status == "complete" else 0
    return {
        "batch_key": batch_key,
        "queue_key": queue_key,
        "batch_status": status,
        "row_index_start": row_start,
        "row_index_end": row_end,
        "expected_row_count": expected_count,
        "valid_row_count": valid_count,
        "blank_row_count": blank_count,
        "pending_row_count": 0,
        "invalid_row_count": 0,
        "missing_row_count": 0,
        "reason_counts": {"blank_decision": blank_count} if blank_count else {},
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "source_image_read_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }


def _workpack() -> dict[str, Any]:
    """Return a workpack summary fixture.

    Returns:
        Workpack payload.
    """
    return {
        "schema_version": "supplement-operator-review-workpack-v1",
        "status": "ok",
        "batch_count": 3,
        "workpack_file_count": 4,
        "next_batch_key": "brand_product_review:001",
        "batch_workpacks": [
            _workpack_row("brand_product_review:001", "brand_product_review"),
            _workpack_row("review_pii_screening:001", "review_pii_screening"),
            _workpack_row("yolo_section_annotation:001", "yolo_section_annotation"),
        ],
        "source_rows_read": False,
        "source_image_read_performed": False,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }


def _workpack_row(batch_key: str, queue_key: str) -> dict[str, Any]:
    """Return a workpack row.

    Args:
        batch_key: Batch key.
        queue_key: Queue key.

    Returns:
        Workpack row.
    """
    filename = batch_key.replace(":", "-")
    return {
        "batch_key": batch_key,
        "queue_key": queue_key,
        "workpack_file_name": f"{filename}.md",
        "batch_file_name": f"{filename}.jsonl",
        "source_editable_file_name": "decisions.todo.jsonl",
        "row_index_start": 1,
        "row_index_end": 50,
        "pending_row_count": 50,
        "bundle_file_names": ["decisions.todo.jsonl", "README.md"],
        "operator_checklist": ["complete_operator_review"],
        "source_rows_read": False,
        "source_image_read_performed": False,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }


def _brand_gate(*, ready: bool = False) -> dict[str, Any]:
    """Return a brand DB import gate fixture.

    Args:
        ready: Whether product import manifest is allowed.

    Returns:
        Gate payload.
    """
    return {
        "schema_version": "supplement-brand-db-import-gate-v1",
        "status": "ready_for_product_import_manifest" if ready else "blocked_by_operator_review",
        "brand_candidate_count": 388,
        "blank_decision_count": 0 if ready else 388,
        "product_import_manifest_allowed": ready,
        "db_import_apply_allowed_now": False,
        "next_steps": ["run_apply_supplement_brand_review_decisions_require_all_reviewed"],
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
        "source_rows_read": False,
        "source_image_read_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }


def _ocr_gate(*, ready: bool = False) -> dict[str, Any]:
    """Return an OCR benchmark gate fixture.

    Args:
        ready: Whether teacher OCR benchmark is allowed.

    Returns:
        Gate payload.
    """
    return {
        "schema_version": "supplement-ocr-benchmark-gate-v1",
        "status": "ready_for_teacher_ocr_eval" if ready else "blocked_by_pii_screening",
        "candidate_row_count": 215,
        "cleared_no_personal_data_count": 215 if ready else 0,
        "pii_blank_decision_count": 0 if ready else 215,
        "teacher_ocr_benchmark_allowed": ready,
        "external_teacher_ocr_eval_allowed": ready,
        "paddleocr_training_allowed_now": False,
        "next_steps": ["run_clova_google_vision_paddleocr_eval_on_benchmark_manifest"],
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
        "source_rows_read": False,
        "source_image_read_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }


def _yolo_gate(*, ready: bool = False) -> dict[str, Any]:
    """Return a YOLO section dataset gate fixture.

    Args:
        ready: Whether section YOLO training dataset is allowed.

    Returns:
        Gate payload.
    """
    return {
        "schema_version": "supplement-yolo-section-dataset-gate-v1",
        "status": (
            "ready_for_section_yolo_training_dataset" if ready else "blocked_by_annotation_review"
        ),
        "template_row_count": 205,
        "valid_accepted_row_count": 205 if ready else 0,
        "pending_operator_action_count": 0 if ready else 205,
        "promoted_item_count": 205 if ready else 0,
        "materialized_item_count": 205 if ready else 0,
        "image_count": 205 if ready else 0,
        "label_count": 205 if ready else 0,
        "train_split_count": 180 if ready else 0,
        "val_split_count": 25 if ready else 0,
        "test_split_count": 0,
        "strict_annotation_ready": ready,
        "template_promotion_ready": ready,
        "dataset_materialization_ready": ready,
        "dataset_validation_ready": ready,
        "section_yolo_training_allowed_now": ready,
        "model_promotion_allowed_now": False,
        "next_steps": ["run_yolo26_section_training_with_materialized_dataset"],
        "db_write_performed": False,
        "database_connection_opened": False,
        "source_rows_read": False,
        "source_image_read_performed": False,
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }


def _input_paths(
    tmp_path: Path,
    *,
    ready_ocr: bool = False,
    complete_pii: bool = False,
    ready_yolo: bool | None = None,
) -> dict[str, Path]:
    """Write default input fixtures.

    Args:
        tmp_path: Temporary directory.
        ready_ocr: Whether OCR gate is ready.
        complete_pii: Whether PII queue is complete.
        ready_yolo: Optional YOLO gate readiness. ``None`` omits the gate.

    Returns:
        Input path mapping.
    """
    paths = {
        "batch_progress": _write_json(
            tmp_path / "progress.json",
            _progress(complete_pii=complete_pii),
        ),
        "workpack_summary": _write_json(tmp_path / "workpack.json", _workpack()),
        "brand_db_import_gate": _write_json(tmp_path / "brand-gate.json", _brand_gate()),
        "ocr_benchmark_gate": _write_json(tmp_path / "ocr-gate.json", _ocr_gate(ready=ready_ocr)),
    }
    if ready_yolo is not None:
        paths["yolo_section_dataset_gate"] = _write_json(
            tmp_path / "yolo-gate.json",
            _yolo_gate(ready=ready_yolo),
        )
    return paths


def test_dependency_audit_links_each_outcome_to_its_next_batch(tmp_path: Path) -> None:
    """Verify outcome blockers are mapped to queue-specific next batches."""
    summary = audit.build_dependency_audit(input_paths=_input_paths(tmp_path))
    markdown = audit.build_markdown(summary)
    dumped = json.dumps(summary, ensure_ascii=False) + markdown

    assert summary["schema_version"] == "supplement-learning-dependency-audit-v1"
    assert summary["status"] == "blocked_by_operator_review"
    assert summary["blocked_outcomes"] == [
        "product_catalog_db_import",
        "ocr_teacher_benchmark",
        "yolo_section_dataset",
    ]
    assert summary["recommended_operator_sequence"] == [
        "brand_product_review:001",
        "review_pii_screening:001",
        "yolo_section_annotation:001",
    ]
    by_key = {row["outcome_key"]: row for row in summary["outcomes"]}
    assert (
        by_key["product_catalog_db_import"]["next_batch"]["batch_key"] == "brand_product_review:001"
    )
    assert by_key["ocr_teacher_benchmark"]["next_batch"]["batch_key"] == "review_pii_screening:001"
    assert (
        by_key["yolo_section_dataset"]["next_batch"]["batch_key"] == "yolo_section_annotation:001"
    )
    assert by_key["yolo_section_dataset"]["gate_status"] == (
        "blocked_by_missing_yolo_section_dataset_gate"
    )
    assert "Supplement Learning Dependency Audit" in markdown
    assert str(tmp_path) not in dumped
    assert "/Volumes/" not in dumped


def test_dependency_audit_ready_ocr_gate_has_no_pii_next_batch(tmp_path: Path) -> None:
    """Verify ready OCR gate does not point at a completed PII queue batch."""
    summary = audit.build_dependency_audit(
        input_paths=_input_paths(tmp_path, ready_ocr=True, complete_pii=True)
    )

    by_key = {row["outcome_key"]: row for row in summary["outcomes"]}
    assert by_key["ocr_teacher_benchmark"]["allowed_now"] is True
    assert by_key["ocr_teacher_benchmark"]["blocking_queue_key"] == "none"
    assert by_key["ocr_teacher_benchmark"]["next_batch"] is None
    assert "ocr_teacher_benchmark" not in summary["blocked_outcomes"]
    assert "review_pii_screening:001" not in summary["recommended_operator_sequence"]


def test_dependency_audit_ready_yolo_gate_removes_yolo_blocker(tmp_path: Path) -> None:
    """Verify ready YOLO gate removes the YOLO outcome blocker."""
    summary = audit.build_dependency_audit(input_paths=_input_paths(tmp_path, ready_yolo=True))

    by_key = {row["outcome_key"]: row for row in summary["outcomes"]}
    assert by_key["yolo_section_dataset"]["allowed_now"] is True
    assert by_key["yolo_section_dataset"]["gate_status"] == (
        "ready_for_section_yolo_training_dataset"
    )
    assert "yolo_section_dataset" not in summary["blocked_outcomes"]


def test_dependency_audit_rejects_unsafe_payload(tmp_path: Path) -> None:
    """Verify raw OCR/provider payload keys fail closed."""
    paths = _input_paths(tmp_path)
    payload = _ocr_gate()
    payload["raw_ocr_text"] = "unsafe"
    _write_json(paths["ocr_benchmark_gate"], payload)

    with pytest.raises(audit.DependencyAuditError, match="raw key"):
        audit.build_dependency_audit(input_paths=paths)


def test_dependency_audit_cli_writes_json_and_markdown(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI writes redacted JSON and Markdown."""
    paths = _input_paths(tmp_path)
    output_path = tmp_path / "audit.json"
    markdown_path = tmp_path / "audit.md"

    audit.main(
        [
            "--batch-progress",
            str(paths["batch_progress"]),
            "--workpack-summary",
            str(paths["workpack_summary"]),
            "--brand-db-import-gate",
            str(paths["brand_db_import_gate"]),
            "--ocr-benchmark-gate",
            str(paths["ocr_benchmark_gate"]),
            "--yolo-section-dataset-gate",
            str(_write_json(tmp_path / "yolo-gate.json", _yolo_gate())),
            "--output",
            str(output_path),
            "--markdown-output",
            str(markdown_path),
        ]
    )

    stdout = capsys.readouterr().out
    summary = json.loads(output_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert summary["status"] == "blocked_by_operator_review"
    assert "brand_product_review:001" in markdown
    assert '"pending_batch_count": 3' in stdout
    assert str(tmp_path) not in stdout
