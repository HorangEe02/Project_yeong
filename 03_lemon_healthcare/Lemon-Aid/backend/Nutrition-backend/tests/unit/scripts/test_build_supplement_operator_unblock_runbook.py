"""Tests for supplement operator unblock runbook generation."""

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

runbook = importlib.import_module("scripts.build_supplement_operator_unblock_runbook")


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


def _batch(
    queue_key: str,
    batch_key: str,
    *,
    blank: int,
    valid: int = 0,
    reason_key: str = "blank_decision",
) -> dict[str, Any]:
    """Build one batch progress row.

    Args:
        queue_key: Review queue key.
        batch_key: Batch key.
        blank: Blank row count.
        valid: Valid row count.
        reason_key: Reason-count key.

    Returns:
        Batch progress row.
    """
    return {
        "queue_key": queue_key,
        "batch_key": batch_key,
        "batch_status": "complete" if blank == 0 else "pending",
        "expected_row_count": blank + valid,
        "blank_row_count": blank,
        "valid_row_count": valid,
        "invalid_row_count": 0,
        "missing_row_count": 0,
        "reason_counts": {reason_key: blank} if blank else {},
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


def _progress_payload(*, complete: bool = False) -> dict[str, Any]:
    """Build batch-progress fixture.

    Args:
        complete: Whether all queues are complete.

    Returns:
        Batch-progress payload.
    """
    if complete:
        batches = [
            _batch("brand_product_review", "brand_product_review:001", blank=0, valid=50),
            _batch("review_pii_screening", "review_pii_screening:001", blank=0, valid=50),
            _batch(
                "yolo_section_annotation",
                "yolo_section_annotation:001",
                blank=0,
                valid=50,
                reason_key="blank_boxes",
            ),
        ]
    else:
        batches = [
            _batch("brand_product_review", "brand_product_review:001", blank=50),
            _batch("brand_product_review", "brand_product_review:002", blank=38),
            _batch("review_pii_screening", "review_pii_screening:001", blank=50),
            _batch(
                "yolo_section_annotation",
                "yolo_section_annotation:001",
                blank=50,
                reason_key="blank_boxes",
            ),
        ]
    return {
        "schema_version": runbook.BATCH_PROGRESS_SCHEMA,
        "batch_count": len(batches),
        "complete_batch_count": len(batches) if complete else 0,
        "pending_batch_count": 0 if complete else len(batches),
        "invalid_batch_count": 0,
        "all_batches_complete": complete,
        "next_incomplete_batch_key": "" if complete else "brand_product_review:001",
        "total_expected_row_count": sum(row["expected_row_count"] for row in batches),
        "total_valid_row_count": sum(row["valid_row_count"] for row in batches),
        "total_blank_row_count": sum(row["blank_row_count"] for row in batches),
        "total_pending_row_count": 0,
        "total_invalid_row_count": 0,
        "total_missing_row_count": 0,
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
        "source_doc_urls": ["https://docs.ultralytics.com/tasks/detect/"],
    }


def _work_order_payload(*, complete: bool = False) -> dict[str, Any]:
    """Build next work-order fixture.

    Args:
        complete: Whether no next batch remains.

    Returns:
        Work-order payload.
    """
    return {
        "schema_version": runbook.WORK_ORDER_SCHEMA,
        "status": "complete" if complete else "pending_operator_review",
        "batch_key": "" if complete else "brand_product_review:001",
        "queue_key": "" if complete else "brand_product_review",
        "batch_file_name": "" if complete else "brand_product_review-001.jsonl",
        "source_editable_file_name": "decisions.todo.jsonl",
        "blank_row_count": 0 if complete else 50,
        "stage_next_operator_action": "" if complete else "complete_brand_product_human_review",
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


def _post_plan_payload(*, allowed: bool = False) -> dict[str, Any]:
    """Build post-completion plan fixture.

    Args:
        allowed: Whether post-completion execution is allowed.

    Returns:
        Post-completion plan payload.
    """
    return {
        "schema_version": runbook.POST_COMPLETION_SCHEMA,
        "post_completion_execution_allowed": allowed,
        "blocked_reason_codes": [] if allowed else ["batch_not_complete", "blank_rows_remaining"],
        "steps": [
            {
                "order": 1,
                "script_key": "preflight_supplement_brand_review_contact_sheet",
                "gate_policy": "must_pass_before_csv_apply",
                "purpose": "confirm csv and contact sheet row alignment",
            },
            {
                "order": 2,
                "script_key": "build_supplement_brand_review_batch_triage",
                "gate_policy": "operator_review_helper_no_decision",
                "purpose": "summarize csv review priority without decisions",
            },
            {
                "order": 3,
                "script_key": "apply_supplement_brand_batch_review_csv_decisions",
                "gate_policy": "require_all_reviewed_no_source_overwrite",
                "purpose": "copy fully reviewed csv fields into a batch jsonl copy",
            },
            {
                "order": 4,
                "script_key": "preflight_supplement_operator_review_batch_file",
                "gate_policy": "must_pass_before_reconcile",
                "purpose": "confirm operator local batch is complete",
            },
            {
                "order": 5,
                "script_key": "reconcile_supplement_operator_review_batch_files",
                "gate_policy": "no_source_overwrite",
                "purpose": "merge completed batch into reconciled queue copies",
            },
        ],
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


def _completion_audit_payload(*, complete: bool = False) -> dict[str, Any]:
    """Build completion audit fixture.

    Args:
        complete: Whether the objective is complete.

    Returns:
        Completion audit payload.
    """
    requirements = [
        {
            "requirement_key": "brand_product_db_import",
            "status": "verified" if complete else "pending_operator_review",
        },
        {
            "requirement_key": "review_image_ground_truth_privacy_gate",
            "status": "verified" if complete else "pending_operator_review",
        },
        {
            "requirement_key": "detail_page_yolo_bbox_annotation",
            "status": "verified" if complete else "pending_operator_review",
        },
    ]
    return {
        "schema_version": runbook.COMPLETION_AUDIT_SCHEMA,
        "overall_status": (
            "complete_verified" if complete else "in_progress_blocked_by_missing_evidence"
        ),
        "objective_completion_allowed": complete,
        "verified_requirement_count": 12 if complete else 4,
        "pending_requirement_count": 0 if complete else 3,
        "blocked_requirement_count": 0 if complete else 5,
        "incomplete_requirement_keys": (
            []
            if complete
            else [
                "brand_product_db_import",
                "review_image_ground_truth_privacy_gate",
                "detail_page_yolo_bbox_annotation",
            ]
        ),
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
        "requirements": requirements,
        "source_doc_urls": ["https://docs.sqlalchemy.org/en/21/orm/queryguide/select.html"],
    }


def _gate_payload(gate_key: str) -> dict[str, Any]:
    """Build a downstream gate fixture.

    Args:
        gate_key: Optional gate key from the runbook input mapping.

    Returns:
        Gate payload fixture.
    """
    base = {
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
        "source_image_read_performed": False,
        "source_rows_read": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
        "source_doc_urls": ["https://docs.ultralytics.com/tasks/detect/"],
    }
    if gate_key == "brand_db_import_gate":
        return {
            **base,
            "schema_version": runbook.OPTIONAL_GATE_SCHEMAS[gate_key],
            "status": "blocked_by_operator_review",
            "blank_decision_count": 88,
            "approved_decision_count": 0,
            "product_import_manifest_allowed": False,
            "db_import_apply_allowed_now": False,
            "next_steps": ["complete_operator_brand_review"],
        }
    if gate_key == "ocr_benchmark_gate":
        return {
            **base,
            "schema_version": runbook.OPTIONAL_GATE_SCHEMAS[gate_key],
            "status": "blocked_by_pii_screening",
            "pii_blank_decision_count": 50,
            "cleared_no_personal_data_count": 0,
            "teacher_ocr_benchmark_allowed": False,
            "external_teacher_ocr_eval_allowed": False,
            "paddleocr_training_allowed_now": False,
            "next_steps": ["complete_review_image_pii_screening"],
        }
    return {
        **base,
        "schema_version": runbook.OPTIONAL_GATE_SCHEMAS[gate_key],
        "status": "blocked_by_annotation_review",
        "blank_box_row_count": 50,
        "reviewed_box_row_count": 0,
        "dataset_materialization_ready": False,
        "section_yolo_training_allowed_now": False,
        "model_promotion_allowed_now": False,
        "next_steps": ["complete_supplement_section_bbox_review"],
    }


def _triage_payload(triage_key: str) -> dict[str, Any]:
    """Build a current-batch triage fixture.

    Args:
        triage_key: Optional triage key from the runbook input mapping.

    Returns:
        Triage payload fixture.
    """
    base = {
        "automatic_decision_performed": False,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
        "source_image_read_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
        "source_doc_urls": ["https://docs.python.org/3/library/json.html"],
    }
    if triage_key == "brand_product_review_triage":
        return {
            **base,
            "schema_version": runbook.OPTIONAL_TRIAGE_SCHEMAS[triage_key],
            "batch_review_csv_name": "brand_product_review-001.review.csv",
            "row_count": 50,
            "blank_decision_row_count": 50,
            "reviewed_row_count": 0,
            "priority_counts": {"p1_evidence_check": 2, "p2_duplicate_candidate_review": 48},
            "reason_counts": {"blank_decision": 50, "duplicate_candidate_in_batch": 48},
            "row_hints": [
                {
                    "row_index": 2,
                    "priority": "p1_evidence_check",
                    "reason_codes": ["blank_decision"],
                }
            ],
            "operator_next_steps": ["complete_blank_decisions_in_review_csv"],
        }
    queue_key = triage_key.removesuffix("_triage")
    reason_key = "blank_boxes" if queue_key == "yolo_section_annotation" else "blank_decision"
    priority_key = (
        "p2_bbox_annotation_required"
        if queue_key == "yolo_section_annotation"
        else "p2_privacy_screening_required"
    )
    return {
        **base,
        "schema_version": runbook.OPTIONAL_TRIAGE_SCHEMAS[triage_key],
        "queue_key": queue_key,
        "batch_file_name": f"{queue_key}-001.jsonl",
        "row_count": 50,
        "blank_row_count": 50,
        "valid_row_count": 0,
        "pending_row_count": 0,
        "invalid_row_count": 0,
        "priority_counts": {priority_key: 50},
        "reason_counts": {reason_key: 50},
        "row_hints": [{"row_index": 1, "priority": priority_key, "reason_code": reason_key}],
        "operator_next_steps": ["complete_operator_review"],
    }


def _write_inputs(
    tmp_path: Path,
    *,
    complete: bool = False,
    include_gates: bool = False,
    include_triage: bool = False,
) -> dict[str, Path]:
    """Write all runbook input fixtures.

    Args:
        tmp_path: Temporary directory.
        complete: Whether fixtures represent complete state.
        include_gates: Whether optional downstream gate fixtures are included.
        include_triage: Whether optional current-batch triage fixtures are included.

    Returns:
        Input path mapping.
    """
    inputs = {
        "batch_progress": _write_json(
            tmp_path / "progress.json", _progress_payload(complete=complete)
        ),
        "next_work_order": _write_json(
            tmp_path / "work-order.json",
            _work_order_payload(complete=complete),
        ),
        "post_completion_plan": _write_json(
            tmp_path / "post-plan.json",
            _post_plan_payload(allowed=complete),
        ),
        "completion_audit": _write_json(
            tmp_path / "completion-audit.json",
            _completion_audit_payload(complete=complete),
        ),
    }
    if include_gates:
        for gate_key in runbook.OPTIONAL_GATE_SCHEMAS:
            inputs[gate_key] = _write_json(
                tmp_path / f"{gate_key}.json",
                _gate_payload(gate_key),
            )
    if include_triage:
        for triage_key in runbook.OPTIONAL_TRIAGE_SCHEMAS:
            inputs[triage_key] = _write_json(
                tmp_path / f"{triage_key}.json",
                _triage_payload(triage_key),
            )
    return inputs


def test_unblock_runbook_summarizes_pending_queues_without_paths(tmp_path: Path) -> None:
    """Verify pending queue summary and sequence are redacted."""
    input_paths = _write_inputs(tmp_path, include_gates=True, include_triage=True)

    payload = runbook.build_operator_unblock_runbook(input_paths=input_paths)
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    queue_by_key = {row["queue_key"]: row for row in payload["queue_summaries"]}
    gate_by_key = {row["gate_key"]: row for row in payload["gate_summaries"]}
    triage_by_key = {row["queue_key"]: row for row in payload["triage_summaries"]}

    assert payload["status"] == "blocked_by_operator_review"
    assert payload["objective_completion_allowed"] is False
    assert "input_path_hashes" not in payload
    assert all(
        value.startswith("fp-") and len(value) == 11
        for value in payload["input_path_fingerprints"].values()
    )
    assert payload["current_next_batch_key"] == "brand_product_review:001"
    assert payload["current_blocker_batch_key"] == "brand_product_review:001"
    assert payload["current_blocker_queue_key"] == "brand_product_review"
    assert payload["current_blocker_blank_row_count"] == 50
    assert payload["operator_next_action"] == "complete_brand_product_human_review"
    assert payload["total_blank_row_count"] == 188
    assert queue_by_key["brand_product_review"]["blank_row_count"] == 88
    assert queue_by_key["review_pii_screening"]["next_batch_key"] == "review_pii_screening:001"
    assert queue_by_key["yolo_section_annotation"]["reason_counts"] == {"blank_boxes": 50}
    assert gate_by_key["ocr_benchmark_gate"]["status"] == "blocked_by_pii_screening"
    assert gate_by_key["yolo_section_dataset_gate"]["key_counts"] == {
        "blank_box_row_count": 50,
        "reviewed_box_row_count": 0,
    }
    assert gate_by_key["brand_db_import_gate"]["allowed_flags"] == {
        "db_import_apply_allowed_now": False,
        "product_import_manifest_allowed": False,
    }
    assert triage_by_key["brand_product_review"]["priority_counts"] == {
        "p1_evidence_check": 2,
        "p2_duplicate_candidate_review": 48,
    }
    assert triage_by_key["review_pii_screening"]["blank_row_count"] == 50
    assert triage_by_key["yolo_section_annotation"]["reason_counts"] == {"blank_boxes": 50}
    assert triage_by_key["brand_product_review"]["row_hints"] == [
        {
            "row_index": 2,
            "priority": "p1_evidence_check",
            "reason_codes": ["blank_decision"],
        }
    ]
    assert payload["operator_sequence"][0]["next_action"] == "complete_brand_product_human_review"
    assert payload["current_post_completion_steps"][0]["script_key"] == (
        "preflight_supplement_brand_review_contact_sheet"
    )
    assert payload["current_post_completion_steps"][2]["gate_policy"] == (
        "require_all_reviewed_no_source_overwrite"
    )
    assert str(tmp_path) not in serialized
    assert "/Volumes/" not in serialized
    assert "/Users/" not in serialized
    assert "file://" not in serialized


def test_unblock_runbook_all_complete_allows_completion(tmp_path: Path) -> None:
    """Verify all-complete fixtures produce a complete runbook."""
    input_paths = _write_inputs(tmp_path, complete=True)

    payload = runbook.build_operator_unblock_runbook(input_paths=input_paths)

    assert payload["status"] == "complete_verified"
    assert payload["objective_completion_allowed"] is True
    assert payload["total_blank_row_count"] == 0
    assert all(row["status"] == "complete" for row in payload["queue_summaries"])
    assert payload["current_post_completion_execution_allowed"] is True


def test_unblock_runbook_marks_stale_optional_brand_artifacts(
    tmp_path: Path,
) -> None:
    """Verify stale optional brand artifacts are marked without blocking output."""
    input_paths = _write_inputs(tmp_path, include_gates=True, include_triage=True)
    progress = _progress_payload()
    for batch in progress["batches"]:
        if batch["queue_key"] == "brand_product_review":
            batch["valid_row_count"] += batch["blank_row_count"]
            batch["blank_row_count"] = 0
            batch["reason_counts"] = {}
            batch["batch_status"] = "complete"
    progress["total_valid_row_count"] = sum(row["valid_row_count"] for row in progress["batches"])
    progress["total_blank_row_count"] = sum(row["blank_row_count"] for row in progress["batches"])
    _write_json(input_paths["batch_progress"], progress)
    completion_audit = _completion_audit_payload()
    completion_audit["requirements"][0]["status"] = "verified"
    _write_json(input_paths["completion_audit"], completion_audit)

    payload = runbook.build_operator_unblock_runbook(input_paths=input_paths)
    brand_gate = {row["gate_key"]: row for row in payload["gate_summaries"]}["brand_db_import_gate"]
    brand_triage = {row["queue_key"]: row for row in payload["triage_summaries"]}[
        "brand_product_review"
    ]

    assert brand_gate["consistency_status"] == "stale_optional_artifact"
    assert brand_gate["consistency_warnings"] == [
        "brand_gate_contradicts_verified_requirement",
        "brand_gate_contradicts_complete_queue",
    ]
    assert brand_triage["consistency_status"] == "stale_optional_artifact"
    assert brand_triage["consistency_warnings"] == ["triage_contradicts_complete_queue"]


def test_unblock_runbook_rejects_unsafe_payload(tmp_path: Path) -> None:
    """Verify unsafe side-effect flags are rejected."""
    input_paths = _write_inputs(tmp_path)
    progress = json.loads(input_paths["batch_progress"].read_text(encoding="utf-8"))
    progress["source_image_read_performed"] = True
    _write_json(input_paths["batch_progress"], progress)

    with pytest.raises(runbook.OperatorUnblockRunbookError, match="Unsafe side-effect flag"):
        runbook.build_operator_unblock_runbook(input_paths=input_paths)


def test_unblock_runbook_cli_writes_json_and_markdown(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI writes redacted JSON and Markdown."""
    input_paths = _write_inputs(tmp_path, include_gates=True, include_triage=True)
    output_path = tmp_path / "runbook.json"
    markdown_path = tmp_path / "runbook.md"

    runbook.main(
        [
            "--batch-progress",
            str(input_paths["batch_progress"]),
            "--next-work-order",
            str(input_paths["next_work_order"]),
            "--post-completion-plan",
            str(input_paths["post_completion_plan"]),
            "--completion-audit",
            str(input_paths["completion_audit"]),
            "--brand-db-import-gate",
            str(input_paths["brand_db_import_gate"]),
            "--ocr-benchmark-gate",
            str(input_paths["ocr_benchmark_gate"]),
            "--yolo-section-dataset-gate",
            str(input_paths["yolo_section_dataset_gate"]),
            "--brand-product-review-triage",
            str(input_paths["brand_product_review_triage"]),
            "--review-pii-screening-triage",
            str(input_paths["review_pii_screening_triage"]),
            "--yolo-section-annotation-triage",
            str(input_paths["yolo_section_annotation_triage"]),
            "--output",
            str(output_path),
            "--markdown-output",
            str(markdown_path),
        ]
    )

    stdout = capsys.readouterr().out
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")

    assert payload["schema_version"] == runbook.SCHEMA_VERSION
    assert "# Supplement Operator Unblock Runbook" in markdown
    assert "Current blocker" in markdown
    assert "Operator next action" in markdown
    assert "Queue Summary" in markdown
    assert "Gate Summary" in markdown
    assert "Consistency" in markdown
    assert "Batch Triage Summary" in markdown
    assert "preflight_supplement_brand_review_contact_sheet" in markdown
    assert "require_all_reviewed_no_source_overwrite" in markdown
    assert "p2_bbox_annotation_required" in markdown
    assert "blocked_by_pii_screening" in markdown
    assert all(row["consistency_status"] == "consistent" for row in payload["gate_summaries"])
    assert all(row["consistency_status"] == "consistent" for row in payload["triage_summaries"])
    assert payload["raw_ocr_text_stored"] is False
    for redacted_output in (stdout, json.dumps(payload, ensure_ascii=False), markdown):
        assert str(tmp_path) not in redacted_output
        assert "/Volumes/" not in redacted_output
        assert "/Users/" not in redacted_output
        assert "file://" not in redacted_output
