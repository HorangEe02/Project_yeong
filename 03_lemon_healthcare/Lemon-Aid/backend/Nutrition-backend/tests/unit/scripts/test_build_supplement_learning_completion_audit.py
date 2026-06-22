"""Tests for supplement learning requirement-level completion audit."""

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

audit = importlib.import_module("scripts.build_supplement_learning_completion_audit")


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


def _stage(
    stage_key: str,
    status: str,
    *,
    blocker_codes: list[str] | None = None,
) -> dict[str, Any]:
    """Build a readiness stage fixture.

    Args:
        stage_key: Stable stage key.
        status: Stage readiness status.
        blocker_codes: Optional blocker codes.

    Returns:
        Readiness stage payload.
    """
    return {
        "stage_key": stage_key,
        "phase": "test_phase",
        "status": status,
        "blocker_codes": blocker_codes or [],
        "next_operator_action": f"next_action_for_{stage_key}",
    }


def _readiness_payload(stage_statuses: dict[str, str]) -> dict[str, Any]:
    """Build a readiness report fixture.

    Args:
        stage_statuses: Stage status by stage key.

    Returns:
        Readiness report payload.
    """
    return {
        "schema_version": audit.READINESS_SCHEMA,
        "overall_status": "fixture",
        "stage_count": len(stage_statuses),
        "stages": [
            _stage(
                stage_key,
                status,
                blocker_codes=[f"{stage_key}_missing"] if status.startswith("blocked") else [],
            )
            for stage_key, status in stage_statuses.items()
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


def _progress_payload(*, total_blank_row_count: int = 808) -> dict[str, Any]:
    """Build an operator batch-progress fixture.

    Args:
        total_blank_row_count: Total blank operator rows.

    Returns:
        Batch-progress payload.
    """
    blank_batches = [
        {
            "queue_key": "brand_product_review",
            "batch_key": "brand_product_review:001",
            "batch_status": "pending" if total_blank_row_count else "complete",
            "blank_row_count": 388 if total_blank_row_count else 0,
        },
        {
            "queue_key": "review_pii_screening",
            "batch_key": "review_pii_screening:001",
            "batch_status": "pending" if total_blank_row_count else "complete",
            "blank_row_count": 215 if total_blank_row_count else 0,
        },
        {
            "queue_key": "yolo_section_annotation",
            "batch_key": "yolo_section_annotation:001",
            "batch_status": "pending" if total_blank_row_count else "complete",
            "blank_row_count": 205 if total_blank_row_count else 0,
        },
    ]
    return {
        "schema_version": audit.BATCH_PROGRESS_SCHEMA,
        "batch_count": 18,
        "complete_batch_count": 0 if total_blank_row_count else 18,
        "pending_batch_count": 18 if total_blank_row_count else 0,
        "invalid_batch_count": 0,
        "all_batches_complete": total_blank_row_count == 0,
        "next_incomplete_batch_key": "brand_product_review:001" if total_blank_row_count else "",
        "total_expected_row_count": 808,
        "total_valid_row_count": 0 if total_blank_row_count else 808,
        "total_blank_row_count": total_blank_row_count,
        "total_pending_row_count": 0,
        "total_invalid_row_count": 0,
        "total_missing_row_count": 0,
        "batches": blank_batches,
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "source_image_read_performed": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }


def _work_order_payload(*, blank_row_count: int = 50) -> dict[str, Any]:
    """Build a next work-order fixture.

    Args:
        blank_row_count: Blank row count in the current batch.

    Returns:
        Next work-order payload.
    """
    return {
        "schema_version": audit.WORK_ORDER_SCHEMA,
        "status": "pending_operator_review" if blank_row_count else "complete",
        "batch_key": "brand_product_review:001" if blank_row_count else "",
        "queue_key": "brand_product_review" if blank_row_count else "",
        "batch_status": "pending" if blank_row_count else "complete",
        "blank_row_count": blank_row_count,
        "pending_row_count": 0,
        "invalid_row_count": 0,
        "missing_row_count": 0,
        "stage_next_operator_action": (
            "complete_brand_product_human_review"
            if blank_row_count
            else "no_operator_action_required"
        ),
        "operator_next_action": (
            "complete_brand_product_human_review"
            if blank_row_count
            else "no_operator_action_required"
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
    }


def _post_plan_payload(*, allowed: bool = False) -> dict[str, Any]:
    """Build a post-completion command-plan fixture.

    Args:
        allowed: Whether post-completion execution is allowed.

    Returns:
        Post-completion command-plan payload.
    """
    steps = [
        {
            "order": 10,
            "script_key": "build_supplement_ocr_benchmark_manifest",
            "input_roles": ["teacher_safe_ocr_candidates", "human_reviewed_ground_truth"],
            "output_roles": ["ocr_benchmark_manifest", "ocr_benchmark_manifest_summary"],
            "gate_policy": "pii_cleared_human_gt_only",
        },
        {
            "order": 11,
            "script_key": "assign_paddleocr_benchmark_splits",
            "input_roles": ["ocr_benchmark_manifest"],
            "output_roles": ["ocr_benchmark_split_manifest", "benchmark_split_summary"],
            "gate_policy": "must_pass_before_provider_observations",
        },
        {
            "order": 12,
            "script_key": "gate_supplement_ocr_benchmark",
            "input_roles": [
                "pii_decision_preflight_summary",
                "gt_bundle_summary",
                "ground_truth_preflight_summary",
                "benchmark_summary",
                "benchmark_split_summary",
            ],
            "output_roles": ["ocr_benchmark_gate_summary"],
            "gate_policy": "must_pass_before_teacher_ocr_eval",
        },
        {
            "order": 13,
            "script_key": "collect_supplement_ocr_observations",
            "input_roles": ["ocr_benchmark_split_manifest"],
            "output_roles": ["redacted_provider_observations"],
            "gate_policy": "external_ocr_requires_explicit_env_opt_in",
        },
    ]
    return {
        "schema_version": audit.POST_COMPLETION_SCHEMA,
        "batch_key": "" if allowed else "brand_product_review:001",
        "queue_key": "" if allowed else "brand_product_review",
        "batch_status": "complete" if allowed else "pending",
        "post_completion_execution_allowed": allowed,
        "blocked_reason_codes": [] if allowed else ["batch_not_complete", "blank_rows_remaining"],
        "step_count": len(steps),
        "steps": steps,
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


def _command_checklist_payload() -> dict[str, Any]:
    """Build a command checklist fixture with fail-closed teacher OCR commands.

    Returns:
        Command checklist payload.
    """
    return {
        "schema_version": audit.COMMAND_CHECKLIST_SCHEMA,
        "queue_key": "review_pii_screening",
        "batch_key": "review_pii_screening:001",
        "commands": [
            {
                "order": 11,
                "script_key": "build_supplement_ocr_benchmark_manifest",
                "gate_policy": "pii_cleared_human_gt_only",
                "command": "backend/.venv/bin/python backend/scripts/build_supplement_ocr_benchmark_manifest.py",
            },
            {
                "order": 12,
                "script_key": "assign_paddleocr_benchmark_splits",
                "gate_policy": "must_pass_before_provider_observations",
                "command": "backend/.venv/bin/python backend/scripts/assign_paddleocr_benchmark_splits.py",
            },
            {
                "order": 13,
                "script_key": "gate_supplement_ocr_benchmark",
                "gate_policy": "must_pass_before_teacher_ocr_eval",
                "command": (
                    "backend/.venv/bin/python backend/scripts/gate_supplement_ocr_benchmark.py "
                    "--pii-preflight pii.json "
                    "--ground-truth-bundle-summary summary.json "
                    "--ground-truth-preflight gt-preflight.json "
                    "--benchmark-summary benchmark-summary.json "
                    "--benchmark-split-summary split-summary.json "
                    "--require-ready-for-teacher-ocr-eval"
                ),
            },
            {
                "order": 14,
                "script_key": "collect_supplement_ocr_observations",
                "gate_policy": "external_ocr_requires_explicit_env_opt_in",
                "command": "backend/.venv/bin/python backend/scripts/collect_supplement_ocr_observations.py",
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


def _taxonomy_audit_payload() -> dict[str, Any]:
    """Build a redacted taxonomy audit fixture.

    Returns:
        Taxonomy audit payload.
    """
    return {
        "schema_version": audit.TAXONOMY_AUDIT_SCHEMA,
        "category_count": 43,
        "product_candidate_count": 388,
        "review_image_count": 132520,
        "detail_page_image_count": 5289,
        "db_write_performed": False,
        "source_image_read_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }


def _taxonomy_staging_payload() -> dict[str, Any]:
    """Build a redacted taxonomy staging fixture.

    Returns:
        Taxonomy staging payload.
    """
    return {
        "schema_version": audit.TAXONOMY_STAGING_SCHEMA,
        "row_count": 431,
        "category_seed_count": 43,
        "brand_candidate_count": 388,
        "db_write_performed": False,
        "source_image_read_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }


def _write_audit_inputs(
    tmp_path: Path,
    *,
    readiness: dict[str, Any],
    progress: dict[str, Any] | None = None,
    work_order: dict[str, Any] | None = None,
    post_plan: dict[str, Any] | None = None,
    command_checklist: dict[str, Any] | None = None,
) -> dict[str, Path]:
    """Write all completion audit input fixtures.

    Args:
        tmp_path: Temporary directory.
        readiness: Readiness report payload.
        progress: Optional progress payload.
        work_order: Optional work-order payload.
        post_plan: Optional post-completion plan payload.
        command_checklist: Optional command checklist payload.

    Returns:
        Input path mapping.
    """
    return {
        "readiness": _write_json(tmp_path / "readiness.json", readiness),
        "batch_progress": _write_json(
            tmp_path / "progress.json",
            progress or _progress_payload(),
        ),
        "next_work_order": _write_json(
            tmp_path / "work-order.json",
            work_order or _work_order_payload(),
        ),
        "post_completion_plan": _write_json(
            tmp_path / "post-plan.json",
            post_plan or _post_plan_payload(),
        ),
        "next_command_checklist": _write_json(
            tmp_path / "command-checklist.json",
            command_checklist or _command_checklist_payload(),
        ),
        "taxonomy_audit": _write_json(tmp_path / "taxonomy-audit.json", _taxonomy_audit_payload()),
        "taxonomy_staging": _write_json(
            tmp_path / "taxonomy-staging.json",
            _taxonomy_staging_payload(),
        ),
    }


def _current_blocked_stage_statuses() -> dict[str, str]:
    """Return a fixture matching the current incomplete operator state.

    Returns:
        Stage status mapping.
    """
    return {
        "taxonomy_structure_audit": "verified",
        "taxonomy_db_staging": "verified",
        "brand_product_review": "pending_operator_review",
        "category_seed_db_apply_preflight": "verified",
        "category_seed_db_verification": "verified",
        "taxonomy_db_import_verification": "blocked_missing_artifact",
        "learning_candidate_split": "verified",
        "private_image_tracking_check": "verified",
        "review_pii_screening": "pending_operator_review",
        "manual_ocr_ground_truth": "blocked_missing_artifact",
        "teacher_ocr_comparison": "blocked_missing_artifact",
        "yolo_section_annotation": "pending_operator_review",
        "yolo_section_dataset": "blocked_missing_artifact",
        "paddleocr_improvement_triage": "blocked_missing_artifact",
        "paddleocr_text_target_chain_preflight": "blocked_invalid_artifact",
        "paddleocr_annotation_tasks": "blocked_missing_artifact",
        "paddleocr_finetune_plan": "blocked_missing_artifact",
        "paddleocr_metric_gate": "blocked_missing_artifact",
        "paddleocr_promotion_runbook": "blocked_missing_artifact",
    }


def _all_required_verified_stage_statuses() -> dict[str, str]:
    """Return verified statuses for every required audit stage.

    Returns:
        Stage status mapping.
    """
    stage_keys = {
        stage_key for spec in audit.REQUIREMENT_SPECS for stage_key in spec.get("stage_keys", ())
    }
    return dict.fromkeys(sorted(stage_keys), "verified")


def test_completion_audit_reports_current_blockers_without_paths(tmp_path: Path) -> None:
    """Verify the current evidence shape blocks objective completion."""
    input_paths = _write_audit_inputs(
        tmp_path,
        readiness=_readiness_payload(_current_blocked_stage_statuses()),
    )

    payload = audit.build_completion_audit(input_paths=input_paths)
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    requirements_by_key = {row["requirement_key"]: row for row in payload["requirements"]}

    assert payload["objective_completion_allowed"] is False
    assert payload["overall_status"] == "in_progress_blocked_by_missing_evidence"
    assert payload["operator_next_action"] == "complete_brand_product_human_review"
    assert payload["verified_requirement_count"] == 6
    assert payload["pending_requirement_count"] == 3
    assert payload["blocked_requirement_count"] == 5
    assert payload["operator_review_completion_gate"] == {
        "all_batches_complete": False,
        "blocker_codes": [
            "batch_not_complete",
            "blank_rows_remaining",
            "operator_batches_not_complete",
            "operator_blank_rows_remaining",
        ],
        "completion_allowed": False,
        "next_action": "complete_all_operator_review_batches_before_completion",
        "post_completion_execution_allowed": False,
        "status": "blocked_operator_review_incomplete",
        "total_blank_row_count": 808,
        "total_invalid_row_count": 0,
        "total_missing_row_count": 0,
        "total_pending_row_count": 0,
    }
    assert all(
        value.startswith("fp-") and len(value) == 15
        for value in payload["input_path_hashes"].values()
    )
    assert requirements_by_key["source_structure_audited"]["status"] == "verified"
    assert requirements_by_key["category_seed_db_apply_preflight_ready"]["status"] == "verified"
    assert requirements_by_key["category_seed_db_verified"]["status"] == "verified"
    assert requirements_by_key["private_image_tracking_guard"]["status"] == "verified"
    assert requirements_by_key["brand_product_db_import"]["status"] == "pending_operator_review"
    assert (
        "queue=brand_product_review" in requirements_by_key["brand_product_db_import"]["evidence"]
    )
    assert (
        "queue_next_batch=brand_product_review:001"
        in requirements_by_key["brand_product_db_import"]["evidence"]
    )
    assert "queue_blank_rows=388" in requirements_by_key["brand_product_db_import"]["evidence"]
    assert (
        "queue=review_pii_screening"
        in requirements_by_key["review_image_ground_truth_privacy_gate"]["evidence"]
    )
    assert (
        "queue_next_batch=review_pii_screening:001"
        in requirements_by_key["review_image_ground_truth_privacy_gate"]["evidence"]
    )
    assert (
        "queue_blank_rows=215"
        in requirements_by_key["review_image_ground_truth_privacy_gate"]["evidence"]
    )
    assert (
        "queue=yolo_section_annotation"
        in requirements_by_key["detail_page_yolo_bbox_annotation"]["evidence"]
    )
    assert (
        "queue_next_batch=yolo_section_annotation:001"
        in requirements_by_key["detail_page_yolo_bbox_annotation"]["evidence"]
    )
    assert (
        "queue_blank_rows=205"
        in requirements_by_key["detail_page_yolo_bbox_annotation"]["evidence"]
    )
    assert requirements_by_key["manual_ocr_ground_truth"]["status"] == "blocked_missing_artifact"
    assert (
        requirements_by_key["paddleocr_training_loop_ready"]["status"] == "blocked_missing_artifact"
    )
    assert (
        "paddleocr_text_target_chain_preflight_missing"
        in requirements_by_key["paddleocr_training_loop_ready"]["blocker_codes"]
    )
    assert requirements_by_key["privacy_security_controls"]["status"] == "verified"
    assert (
        "teacher_ocr_plan_sequence=verified"
        in requirements_by_key["privacy_security_controls"]["evidence"]
    )
    assert (
        "teacher_ocr_command_ready_required=true"
        in requirements_by_key["privacy_security_controls"]["evidence"]
    )
    assert str(tmp_path) not in serialized
    assert "/Volumes/" not in serialized
    assert "/Users/" not in serialized
    assert "file://" not in serialized


def test_completion_audit_accepts_paddleocr_95_stop_gate_without_training_stages(
    tmp_path: Path,
) -> None:
    """Verify a verified 95 percent gate stops only the PaddleOCR training loop."""
    readiness = _readiness_payload(_current_blocked_stage_statuses())
    readiness["artifact_summaries"] = [
        {
            "role": "paddleocr_accuracy_stop_gate",
            "human_ground_truth_compared": True,
            "privacy_review_cleared": True,
            "text_extraction_accuracy_meets_95_percent": True,
            "minimum_required_accuracy": "0.95",
            "training_loop_stop_allowed": True,
            "metric_values_printed": False,
        }
    ]
    input_paths = _write_audit_inputs(tmp_path, readiness=readiness)

    payload = audit.build_completion_audit(input_paths=input_paths)
    requirements_by_key = {row["requirement_key"]: row for row in payload["requirements"]}
    paddleocr_requirement = requirements_by_key["paddleocr_training_loop_ready"]

    assert payload["objective_completion_allowed"] is False
    assert paddleocr_requirement["status"] == "verified"
    assert paddleocr_requirement["evidence"] == [
        "paddleocr_accuracy_stop_gate:verified",
        "human_ground_truth_compared=true",
        "text_extraction_accuracy_ge_95=true",
        "training_loop_stop_allowed=true",
    ]
    assert paddleocr_requirement["next_action"] == (
        "stop_paddleocr_training_loop_after_operator_completion"
    )


def test_completion_audit_keeps_paddleocr_training_blocked_for_failed_stop_gate(
    tmp_path: Path,
) -> None:
    """Verify a failed 95 percent gate does not complete PaddleOCR training."""
    readiness = _readiness_payload(_current_blocked_stage_statuses())
    readiness["artifact_summaries"] = [
        {
            "role": "paddleocr_accuracy_stop_gate",
            "human_ground_truth_compared": True,
            "privacy_review_cleared": True,
            "text_extraction_accuracy_meets_95_percent": False,
            "minimum_required_accuracy": "0.95",
            "training_loop_stop_allowed": False,
            "metric_values_printed": False,
        }
    ]
    input_paths = _write_audit_inputs(tmp_path, readiness=readiness)

    payload = audit.build_completion_audit(input_paths=input_paths)
    paddleocr_requirement = {row["requirement_key"]: row for row in payload["requirements"]}[
        "paddleocr_training_loop_ready"
    ]

    assert paddleocr_requirement["status"] == "blocked_missing_artifact"
    assert "paddleocr_accuracy_stop_gate:not_allowed" in paddleocr_requirement["blocker_codes"]
    assert "text_extraction_accuracy_ge_95=false" in paddleocr_requirement["evidence"]


def test_completion_audit_all_verified_allows_completion(tmp_path: Path) -> None:
    """Verify complete readiness permits objective completion."""
    input_paths = _write_audit_inputs(
        tmp_path,
        readiness=_readiness_payload(_all_required_verified_stage_statuses()),
        progress=_progress_payload(total_blank_row_count=0),
        work_order=_work_order_payload(blank_row_count=0),
        post_plan=_post_plan_payload(allowed=True),
    )

    payload = audit.build_completion_audit(input_paths=input_paths)

    assert payload["objective_completion_allowed"] is True
    assert payload["overall_status"] == "complete_verified"
    assert payload["verified_requirement_count"] == payload["requirement_count"]
    assert payload["pending_requirement_count"] == 0
    assert payload["blocked_requirement_count"] == 0
    assert payload["incomplete_requirement_keys"] == []
    assert payload["operator_review_completion_gate"]["status"] == "verified"
    assert payload["operator_review_completion_gate"]["completion_allowed"] is True


def test_completion_audit_blocks_verified_stages_with_blank_operator_rows(
    tmp_path: Path,
) -> None:
    """Verify unresolved operator rows block completion even if stages are verified."""
    input_paths = _write_audit_inputs(
        tmp_path,
        readiness=_readiness_payload(_all_required_verified_stage_statuses()),
        progress=_progress_payload(total_blank_row_count=808),
        work_order=_work_order_payload(blank_row_count=50),
        post_plan=_post_plan_payload(allowed=False),
    )

    payload = audit.build_completion_audit(input_paths=input_paths)

    assert payload["objective_completion_allowed"] is False
    assert payload["overall_status"] == "in_progress_blocked_by_operator_review_gate"
    assert payload["verified_requirement_count"] == payload["requirement_count"]
    assert payload["incomplete_requirement_keys"] == []
    assert payload["operator_review_completion_gate"]["status"] == (
        "blocked_operator_review_incomplete"
    )
    assert payload["operator_review_completion_gate"]["total_blank_row_count"] == 808
    assert (
        "operator_blank_rows_remaining"
        in payload["operator_review_completion_gate"]["blocker_codes"]
    )


def test_completion_audit_blocks_unsafe_teacher_ocr_command_order(
    tmp_path: Path,
) -> None:
    """Verify provider OCR cannot be marked safe without a ready-required gate."""
    command_checklist = _command_checklist_payload()
    gate_command = next(
        row
        for row in command_checklist["commands"]
        if row["script_key"] == "gate_supplement_ocr_benchmark"
    )
    gate_command["command"] = gate_command["command"].replace(
        " --require-ready-for-teacher-ocr-eval",
        "",
    )
    input_paths = _write_audit_inputs(
        tmp_path,
        readiness=_readiness_payload(_current_blocked_stage_statuses()),
        command_checklist=command_checklist,
    )

    payload = audit.build_completion_audit(input_paths=input_paths)
    privacy_requirement = {row["requirement_key"]: row for row in payload["requirements"]}[
        "privacy_security_controls"
    ]

    assert privacy_requirement["status"] == "blocked_invalid_artifact"
    assert "teacher_ocr_command_gate_flag_missing_require-ready-for-teacher-ocr-eval" in (
        privacy_requirement["blocker_codes"]
    )
    assert "teacher_ocr_command_ready_required=false" in privacy_requirement["evidence"]


def test_completion_audit_rejects_unsafe_payload(tmp_path: Path) -> None:
    """Verify unsafe side-effect flags cannot enter the audit."""
    readiness = _readiness_payload(_current_blocked_stage_statuses())
    readiness["source_rows_read"] = True
    input_paths = _write_audit_inputs(tmp_path, readiness=readiness)

    with pytest.raises(audit.CompletionAuditError, match="Unsafe side-effect flag"):
        audit.build_completion_audit(input_paths=input_paths)


def test_cli_writes_json_and_markdown_without_paths(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify the CLI writes redacted JSON and Markdown outputs."""
    input_paths = _write_audit_inputs(
        tmp_path,
        readiness=_readiness_payload(_current_blocked_stage_statuses()),
    )
    output_path = tmp_path / "completion-audit.json"
    markdown_path = tmp_path / "completion-audit.md"

    audit.main(
        [
            "--readiness",
            str(input_paths["readiness"]),
            "--batch-progress",
            str(input_paths["batch_progress"]),
            "--next-work-order",
            str(input_paths["next_work_order"]),
            "--post-completion-plan",
            str(input_paths["post_completion_plan"]),
            "--next-command-checklist",
            str(input_paths["next_command_checklist"]),
            "--taxonomy-audit",
            str(input_paths["taxonomy_audit"]),
            "--taxonomy-staging",
            str(input_paths["taxonomy_staging"]),
            "--output",
            str(output_path),
            "--markdown-output",
            str(markdown_path),
        ]
    )

    stdout = capsys.readouterr().out
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")

    assert payload["schema_version"] == audit.SCHEMA_VERSION
    assert payload["objective_completion_allowed"] is False
    assert "# Supplement Learning Completion Audit" in markdown
    assert "Current blocker batch" in markdown
    assert payload["raw_ocr_text_stored"] is False
    for redacted_output in (stdout, markdown):
        assert str(tmp_path) not in redacted_output
        assert "/Volumes/" not in redacted_output
        assert "/Users/" not in redacted_output
        assert "file://" not in redacted_output
        assert "raw_ocr_text" not in redacted_output
    serialized_payload = json.dumps(payload, ensure_ascii=False)
    assert str(tmp_path) not in serialized_payload
    assert "/Volumes/" not in serialized_payload
    assert "/Users/" not in serialized_payload
    assert "file://" not in serialized_payload
