"""Tests for supplement operator post-completion command planning."""

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

planner = importlib.import_module("scripts.build_supplement_operator_post_completion_command_plan")


def _write_work_order(path: Path, payload: dict[str, Any]) -> Path:
    """Write a work-order fixture.

    Args:
        path: Destination path.
        payload: JSON payload.

    Returns:
        Written path.
    """
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _work_order_payload(
    *,
    queue_key: str = "brand_product_review",
    batch_status: str = "pending",
    blank_row_count: int = 50,
    pending_row_count: int = 0,
    invalid_row_count: int = 0,
    missing_row_count: int = 0,
) -> dict[str, Any]:
    """Build a minimal safe next-batch work-order payload.

    Args:
        queue_key: Operator review queue key.
        batch_status: Current batch status.
        blank_row_count: Blank row count.
        pending_row_count: Pending row count.
        invalid_row_count: Invalid row count.
        missing_row_count: Missing row count.

    Returns:
        Work-order payload.
    """
    return {
        "schema_version": planner.WORK_ORDER_SCHEMA_VERSION,
        "batch_key": f"{queue_key}:001",
        "queue_key": queue_key,
        "batch_status": batch_status,
        "blank_row_count": blank_row_count,
        "pending_row_count": pending_row_count,
        "invalid_row_count": invalid_row_count,
        "missing_row_count": missing_row_count,
    }


def test_plan_blocks_pending_brand_batch_and_lists_brand_gates(tmp_path: Path) -> None:
    """Verify pending brand review batches expose only blocked post-completion steps."""
    work_order_path = _write_work_order(tmp_path / "work-order.json", _work_order_payload())

    plan = planner.build_post_completion_command_plan(input_paths={"work_order": work_order_path})

    assert plan["post_completion_execution_allowed"] is False
    assert plan["operator_required_before_execution"] is True
    assert plan["blocked_reason_codes"] == [
        "batch_not_complete",
        "blank_rows_remaining",
    ]
    script_keys = [step["script_key"] for step in plan["steps"]]
    assert script_keys[:3] == [
        "preflight_supplement_brand_review_contact_sheet",
        "build_supplement_brand_review_batch_triage",
        "apply_supplement_brand_batch_review_csv_decisions",
    ]
    assert plan["steps"][2]["gate_policy"] == "require_all_reviewed_no_source_overwrite"
    assert script_keys[3:6] == [
        "preflight_supplement_operator_review_batch_file",
        "reconcile_supplement_operator_review_batch_files",
        "preflight_supplement_operator_review_batch_progress",
    ]
    assert plan["step_count"] == 13
    assert "apply_supplement_brand_review_decisions" in script_keys
    assert "gate_supplement_product_db_apply" in script_keys
    assert (
        "brand_csv_apply_requires_contact_sheet_preflight_and_all_rows_reviewed"
        in plan["common_safety_rules"]
    )
    assert plan["db_write_performed"] is False
    assert plan["external_provider_call_performed"] is False
    assert plan["source_rows_read"] is False


def test_plan_allows_complete_pii_batch_without_teacher_ocr_call(tmp_path: Path) -> None:
    """Verify complete PII batches can proceed to gate steps without provider calls."""
    work_order_path = _write_work_order(
        tmp_path / "work-order.json",
        _work_order_payload(
            queue_key="review_pii_screening",
            batch_status="complete",
            blank_row_count=0,
        ),
    )

    plan = planner.build_post_completion_command_plan(input_paths={"work_order": work_order_path})

    assert plan["post_completion_execution_allowed"] is True
    assert plan["operator_required_before_execution"] is False
    assert plan["blocked_reason_codes"] == []
    script_keys = [step["script_key"] for step in plan["steps"]]
    assert plan["step_count"] == 17
    assert "apply_supplement_review_pii_screening_decisions" in script_keys
    assert "export_supplement_ocr_ground_truth_template" in script_keys
    assert "build_supplement_ocr_ground_truth_review_bundle" in script_keys
    assert "preflight_supplement_ocr_ground_truth_manifest" in script_keys
    assert "gate_supplement_ocr_benchmark" in script_keys
    assert "build_supplement_ocr_benchmark_manifest" in script_keys
    assert "assign_paddleocr_benchmark_splits" in script_keys
    assert "collect_supplement_ocr_observations" in script_keys
    assert "merge_paddleocr_text_observations_into_benchmark" in script_keys
    assert "preflight_paddleocr_text_target_chain" in script_keys
    assert "build_paddleocr_text_extraction_eval_summary" in script_keys
    assert "gate_paddleocr_text_extraction_target" in script_keys
    assert script_keys.index("export_supplement_ocr_ground_truth_template") < script_keys.index(
        "build_supplement_ocr_ground_truth_review_bundle"
    )
    assert script_keys.index("build_supplement_ocr_ground_truth_review_bundle") < script_keys.index(
        "preflight_supplement_ocr_ground_truth_manifest"
    )
    assert script_keys.index("preflight_supplement_ocr_ground_truth_manifest") < script_keys.index(
        "build_supplement_ocr_benchmark_manifest"
    )
    assert script_keys.index("build_supplement_ocr_benchmark_manifest") < script_keys.index(
        "assign_paddleocr_benchmark_splits"
    )
    assert script_keys.index("assign_paddleocr_benchmark_splits") < script_keys.index(
        "gate_supplement_ocr_benchmark"
    )
    assert script_keys.index("gate_supplement_ocr_benchmark") < script_keys.index(
        "collect_supplement_ocr_observations"
    )
    assert script_keys.index("collect_supplement_ocr_observations") < script_keys.index(
        "merge_paddleocr_text_observations_into_benchmark"
    )
    assert script_keys.index(
        "merge_paddleocr_text_observations_into_benchmark"
    ) < script_keys.index("preflight_paddleocr_text_target_chain")
    assert script_keys.index("preflight_paddleocr_text_target_chain") < script_keys.index(
        "build_paddleocr_text_extraction_eval_summary"
    )
    assert script_keys.index("build_paddleocr_text_extraction_eval_summary") < script_keys.index(
        "gate_paddleocr_text_extraction_target"
    )
    template_step = next(
        step
        for step in plan["steps"]
        if step["script_key"] == "export_supplement_ocr_ground_truth_template"
    )
    bundle_step = next(
        step
        for step in plan["steps"]
        if step["script_key"] == "build_supplement_ocr_ground_truth_review_bundle"
    )
    gate_step = next(
        step for step in plan["steps"] if step["script_key"] == "gate_supplement_ocr_benchmark"
    )
    target_gate_step = next(
        step
        for step in plan["steps"]
        if step["script_key"] == "gate_paddleocr_text_extraction_target"
    )
    assert "teacher_safe_ocr_candidates" in template_step["input_roles"]
    assert "private_ground_truth_image_fixtures" in template_step["output_roles"]
    assert "human_reviewed_ground_truth" in bundle_step["output_roles"]
    assert "ground_truth_preflight_summary" in gate_step["input_roles"]
    assert target_gate_step["gate_policy"] == "stop_training_only_if_95_percent_target_reached"
    assert (
        "brand_csv_apply_requires_contact_sheet_preflight_and_all_rows_reviewed"
        not in plan["common_safety_rules"]
    )
    assert "never_apply_or_promote_until_strict_gate_passes" in plan["common_safety_rules"]
    assert plan["external_provider_call_performed"] is False
    assert plan["training_execution_performed_by_script"] is False


def test_plan_rejects_raw_or_path_like_work_order_payload(tmp_path: Path) -> None:
    """Verify unsafe raw keys and paths cannot enter command-plan artifacts."""
    payload = {
        **_work_order_payload(batch_status="complete", blank_row_count=0),
        "raw_ocr_text": "do not expose",
    }
    work_order_path = _write_work_order(tmp_path / "work-order.json", payload)

    with pytest.raises(planner.PostCompletionPlanError, match="Unsafe key"):
        planner.build_post_completion_command_plan(input_paths={"work_order": work_order_path})


def test_post_completion_plan_cli_writes_json_and_markdown(tmp_path: Path) -> None:
    """Verify CLI writes redacted JSON and Markdown artifacts."""
    work_order_path = _write_work_order(
        tmp_path / "work-order.json",
        _work_order_payload(
            queue_key="yolo_section_annotation",
            batch_status="complete",
            blank_row_count=0,
        ),
    )
    output_path = tmp_path / "plan.json"
    markdown_path = tmp_path / "plan.md"

    planner.main(
        [
            "--work-order",
            str(work_order_path),
            "--output",
            str(output_path),
            "--markdown-output",
            str(markdown_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")

    assert payload["schema_version"] == planner.SCHEMA_VERSION
    assert payload["post_completion_execution_allowed"] is True
    assert "promote_supplement_yolo_annotation_template" in markdown
    assert "/Users/" not in markdown
    assert "/Volumes/" not in markdown
    assert "raw_ocr_text" not in markdown
