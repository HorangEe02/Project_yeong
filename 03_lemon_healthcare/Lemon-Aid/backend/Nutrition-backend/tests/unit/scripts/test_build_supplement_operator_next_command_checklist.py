"""Tests for supplement operator next command checklist generation."""

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

checklist = importlib.import_module("scripts.build_supplement_operator_next_command_checklist")


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    """Write a JSON fixture.

    Args:
        path: Destination path.
        payload: JSON payload.

    Returns:
        Written path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return path


def _work_order_payload() -> dict[str, Any]:
    """Build next work-order fixture.

    Returns:
        Work-order payload.
    """
    return {
        "schema_version": checklist.WORK_ORDER_SCHEMA,
        "status": "pending_operator_review",
        "batch_key": "brand_product_review:001",
        "queue_key": "brand_product_review",
        "batch_file_name": "brand_product_review-001.jsonl",
        "batch_review_file_name": "brand_product_review-001.review.csv",
        "source_editable_file_name": "decisions.todo.jsonl",
        "blank_row_count": 50,
        "stage_next_operator_action": "complete_brand_product_human_review",
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


def _post_plan_payload() -> dict[str, Any]:
    """Build post-completion plan fixture.

    Returns:
        Post-completion plan payload.
    """
    return {
        "schema_version": checklist.POST_COMPLETION_SCHEMA,
        "post_completion_execution_allowed": False,
        "blocked_reason_codes": ["batch_not_complete", "blank_rows_remaining"],
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
        "source_doc_urls": ["https://docs.python.org/3/library/json.html"],
    }


def _prepare_repo(tmp_path: Path) -> dict[str, Path]:
    """Create minimal repo-like paths for checklist tests.

    Args:
        tmp_path: Temporary directory.

    Returns:
        Important fixture paths.
    """
    repo_root = tmp_path / "repo"
    operator_dir = repo_root / "outputs/generated/supplement-learning/2026-06-04/operator-review"
    todo_dir = repo_root / "outputs/todo-list/2026-06-04"
    input_dir = repo_root / "inputs"
    return {
        "repo_root": repo_root,
        "operator_dir": operator_dir,
        "todo_dir": todo_dir,
        "next_work_order": _write_json(input_dir / "work-order.json", _work_order_payload()),
        "post_completion_plan": _write_json(input_dir / "post-plan.json", _post_plan_payload()),
    }


def _assert_pii_execution_states(payload: dict[str, Any]) -> None:
    """Assert PII/OCR/Paddle commands remain blocked until their gates pass.

    Args:
        payload: Generated command checklist payload.
    """
    assert payload["commands"][0]["execution_state"] == "runnable_now"
    assert payload["commands"][1]["execution_state"] == "blocked_until_operator_edits"
    assert payload["commands"][5]["execution_state"] == "blocked_until_all_pii_rows_reviewed"
    assert payload["commands"][9]["execution_state"] == "blocked_until_manual_gt_edits"
    assert payload["commands"][13]["execution_state"] == "blocked_until_teacher_ocr_gate"
    assert payload["commands"][13]["blocked_by"] == [
        "ocr_benchmark_gate_passed",
        "explicit_external_ocr_opt_in",
    ]
    assert payload["commands"][13]["requires_external_opt_in"] is True
    assert payload["commands"][-1]["execution_state"] == "blocked_until_holdout_eval_summary"


def _assert_pii_ocr_command_chain(commands: list[str]) -> None:
    """Assert PII queue OCR/Paddle command wiring.

    Args:
        commands: Generated shell commands.
    """
    assert "backend/scripts/build_supplement_ocr_benchmark_manifest.py" in commands[10]
    assert (
        "--ground-truth outputs/generated/supplement-learning/2026-06-04/operator-review/ocr-ground-truth-review-bundle/ground-truth.todo.jsonl"
        in commands[10]
    )
    assert "backend/scripts/assign_paddleocr_benchmark_splits.py" in commands[11]
    assert "backend/scripts/gate_supplement_ocr_benchmark.py" in commands[12]
    assert (
        "--ground-truth-bundle-summary outputs/generated/supplement-learning/2026-06-04/operator-review/ocr-ground-truth-review-bundle/summary.json"
        in commands[12]
    )
    assert (
        "--ground-truth-preflight outputs/generated/supplement-learning/2026-06-04/operator-review/reconciled/ocr-ground-truth-preflight.json"
        in commands[12]
    )
    assert (
        "--benchmark-summary outputs/generated/supplement-learning/2026-06-04/operator-review/reconciled/ocr-benchmark-manifest.summary.json"
        in commands[12]
    )
    assert (
        "--benchmark-split-summary outputs/generated/supplement-learning/2026-06-04/operator-review/reconciled/ocr-benchmark-manifest.split.summary.json"
        in commands[12]
    )
    assert "--require-ready-for-teacher-ocr-eval" in commands[12]
    assert "backend/scripts/collect_supplement_ocr_observations.py" in commands[13]
    assert "--providers clova_ocr,google_vision_document,paddleocr_local" in commands[13]
    assert "backend/scripts/merge_paddleocr_text_observations_into_benchmark.py" in commands[14]
    assert "backend/scripts/preflight_paddleocr_text_target_chain.py" in commands[15]
    assert "backend/scripts/build_paddleocr_text_extraction_eval_summary.py" in commands[16]
    assert "--privacy-review-cleared" in commands[16]
    assert "backend/scripts/gate_paddleocr_text_extraction_target.py" in commands[-1]
    assert (
        "--eval-summary outputs/generated/supplement-learning/2026-06-04/operator-review/reconciled/paddleocr-text-extraction-eval-summary.json"
        in commands[-1]
    )


def test_command_checklist_generates_repo_relative_brand_commands(tmp_path: Path) -> None:
    """Verify brand commands are concrete and repo-relative."""
    paths = _prepare_repo(tmp_path)

    payload = checklist.build_command_checklist(
        repo_root=paths["repo_root"],
        operator_dir=paths["operator_dir"],
        todo_dir=paths["todo_dir"],
        input_paths={
            "next_work_order": paths["next_work_order"],
            "post_completion_plan": paths["post_completion_plan"],
        },
    )
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    commands = [row["command"] for row in payload["commands"]]

    assert payload["schema_version"] == checklist.SCHEMA_VERSION
    assert payload["queue_key"] == "brand_product_review"
    assert payload["batch_key"] == "brand_product_review:001"
    assert payload["current_blocker_queue_key"] == "brand_product_review"
    assert payload["current_blocker_batch_key"] == "brand_product_review:001"
    assert payload["current_blocker_blank_row_count"] == 50
    assert payload["operator_next_action"] == "complete_brand_product_human_review"
    assert payload["batch_review_file_name"] == "brand_product_review-001.review.csv"
    assert payload["command_count"] == 10
    assert payload["blocked_until"] == [
        "operator_edits_current_batch",
        "contact_sheet_preflight_ready_for_csv_apply",
        "all_brand_review_csv_rows_reviewed",
        "applied_batch_file_preflight_ready_for_reconcile",
        "batch_file_preflight_ready_for_reconcile",
        "strict_brand_review_complete_before_product_import",
    ]
    assert commands[0].startswith(
        "backend/.venv/bin/python backend/scripts/preflight_supplement_brand_review_contact_sheet.py"
    )
    assert (
        "--batch-review-csv outputs/generated/supplement-learning/2026-06-04/operator-review/batches/brand_product_review-001.review.csv"
        in commands[0]
    )
    assert (
        "--contact-sheet-summary outputs/generated/supplement-learning/2026-06-04/operator-review/brand-detail-contact-sheet-001/brand-detail-contact-sheet.summary.json"
        in commands[0]
    )
    assert (
        "--output outputs/generated/supplement-learning/2026-06-04/operator-review/brand_product_review-001.contact-sheet-preflight.json"
        in commands[0]
    )
    assert (
        "--markdown-output outputs/generated/supplement-learning/2026-06-04/operator-review/brand_product_review-001.contact-sheet-preflight.md"
        in commands[0]
    )
    assert "--require-all-rows-with-thumbnails" in commands[0]
    assert commands[1].startswith(
        "backend/.venv/bin/python backend/scripts/build_supplement_brand_review_batch_triage.py"
    )
    assert (
        "--batch-review-csv outputs/generated/supplement-learning/2026-06-04/operator-review/batches/brand_product_review-001.review.csv"
        in commands[1]
    )
    assert (
        "--output outputs/generated/supplement-learning/2026-06-04/operator-review/brand_product_review-001.triage.json"
        in commands[1]
    )
    assert (
        "--markdown-output outputs/generated/supplement-learning/2026-06-04/operator-review/brand_product_review-001.triage.md"
        in commands[1]
    )
    assert commands[2].startswith(
        "backend/.venv/bin/python backend/scripts/apply_supplement_brand_batch_review_csv_decisions.py"
    )
    assert (
        "--batch-review-csv outputs/generated/supplement-learning/2026-06-04/operator-review/batches/brand_product_review-001.review.csv"
        in commands[2]
    )
    assert (
        "--output outputs/generated/supplement-learning/2026-06-04/operator-review/batches-applied/brand_product_review-001.jsonl"
        in commands[2]
    )
    assert "--require-all-reviewed" in commands[2]
    assert payload["commands"][2]["gate_policy"] == "require_all_reviewed_no_source_overwrite"
    assert payload["commands"][0]["execution_state"] == "runnable_now"
    assert payload["commands"][0]["blocked_by"] == []
    assert payload["commands"][2]["execution_state"] == "blocked_until_operator_edits"
    assert payload["commands"][2]["blocked_by"] == ["all_brand_review_csv_rows_reviewed"]
    assert payload["commands"][2]["requires_operator_input"] is True
    assert payload["commands"][-1]["execution_state"] == "blocked_until_brand_import_gate"
    assert commands[3].startswith(
        "backend/.venv/bin/python backend/scripts/preflight_supplement_operator_review_batch_file.py"
    )
    assert "--batch-key brand_product_review:001" in commands[3]
    assert (
        "--batch-file outputs/generated/supplement-learning/2026-06-04/operator-review/batches-applied/brand_product_review-001.jsonl"
        in commands[3]
    )
    assert (
        "--batch-review-csv outputs/generated/supplement-learning/2026-06-04/operator-review/batches/brand_product_review-001.review.csv"
        in commands[3]
    )
    assert (
        "--batch-file-override brand_product_review:001 outputs/generated/supplement-learning/2026-06-04/operator-review/batches-applied/brand_product_review-001.jsonl"
        in commands[4]
    )
    assert "backend/scripts/apply_supplement_brand_review_decisions.py" in commands[-1]
    assert str(tmp_path) not in serialized
    assert "/Volumes/" not in serialized
    assert "/Users/" not in serialized
    assert "file://" not in serialized
    assert payload["raw_ocr_text_stored"] is False


def test_command_checklist_uses_latest_existing_taxonomy_staging(
    tmp_path: Path,
) -> None:
    """Verify fallback brand commands do not point to a missing current-date staging."""
    paths = _prepare_repo(tmp_path)
    latest_todo_dir = paths["repo_root"] / "outputs/todo-list/2026-06-05"
    prior_staging = (
        paths["repo_root"]
        / "outputs/todo-list/2026-06-04/2026-06-04-supplement-taxonomy-db-staging.jsonl"
    )
    prior_staging.parent.mkdir(parents=True, exist_ok=True)
    prior_staging.write_text("", encoding="utf-8")

    payload = checklist.build_command_checklist(
        repo_root=paths["repo_root"],
        operator_dir=paths["operator_dir"],
        todo_dir=latest_todo_dir,
        input_paths={
            "next_work_order": paths["next_work_order"],
            "post_completion_plan": paths["post_completion_plan"],
        },
    )
    commands = [row["command"] for row in payload["commands"]]

    command_blob = "\n".join(commands)
    assert (
        "outputs/todo-list/2026-06-04/2026-06-04-supplement-taxonomy-db-staging.jsonl"
        in command_blob
    )
    assert (
        "outputs/todo-list/2026-06-05/2026-06-05-supplement-taxonomy-db-staging.jsonl"
        not in command_blob
    )


def test_command_checklist_explicit_taxonomy_staging_overrides_todo_fallback(
    tmp_path: Path,
) -> None:
    """Verify explicit taxonomy staging keeps product import commands current."""
    paths = _prepare_repo(tmp_path)
    latest_todo_dir = paths["repo_root"] / "outputs/todo-list/2026-06-05"
    stale_staging = (
        paths["repo_root"]
        / "outputs/todo-list/2026-06-04/2026-06-04-supplement-taxonomy-db-staging.jsonl"
    )
    current_staging = (
        paths["repo_root"]
        / "outputs/generated/supplement-learning/2026-06-05/supplement-taxonomy-db-staging.jsonl"
    )
    stale_staging.parent.mkdir(parents=True, exist_ok=True)
    current_staging.parent.mkdir(parents=True, exist_ok=True)
    stale_staging.write_text("", encoding="utf-8")
    current_staging.write_text("", encoding="utf-8")

    payload = checklist.build_command_checklist(
        repo_root=paths["repo_root"],
        operator_dir=paths["operator_dir"],
        todo_dir=latest_todo_dir,
        input_paths={
            "next_work_order": paths["next_work_order"],
            "post_completion_plan": paths["post_completion_plan"],
        },
        taxonomy_staging=current_staging,
    )
    command_blob = "\n".join(row["command"] for row in payload["commands"])

    assert (
        "outputs/generated/supplement-learning/2026-06-05/supplement-taxonomy-db-staging.jsonl"
        in command_blob
    )
    assert (
        "outputs/todo-list/2026-06-04/2026-06-04-supplement-taxonomy-db-staging.jsonl"
        not in command_blob
    )


def test_command_checklist_generates_repo_relative_pii_commands(tmp_path: Path) -> None:
    """Verify PII-review commands are concrete and repo-relative."""
    paths = _prepare_repo(tmp_path)
    work_order = _work_order_payload()
    work_order.update(
        {
            "batch_key": "review_pii_screening:001",
            "queue_key": "review_pii_screening",
            "batch_file_name": "review_pii_screening-001.jsonl",
            "operator_next_action": "complete_blank_privacy_decisions",
        }
    )
    _write_json(paths["next_work_order"], work_order)

    payload = checklist.build_command_checklist(
        repo_root=paths["repo_root"],
        operator_dir=paths["operator_dir"],
        todo_dir=paths["todo_dir"],
        input_paths={
            "next_work_order": paths["next_work_order"],
            "post_completion_plan": paths["post_completion_plan"],
        },
    )
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    commands = [row["command"] for row in payload["commands"]]

    assert payload["queue_key"] == "review_pii_screening"
    assert payload["operator_next_action"] == "complete_blank_privacy_decisions"
    assert payload["command_count"] == 18
    assert "ocr_ground_truth_review_bundle_ready_before_manual_gt" in payload["blocked_until"]
    assert "manual_ocr_ground_truth_preflight_ready_before_benchmark" in payload["blocked_until"]
    assert "ocr_benchmark_manifest_ready_before_provider_observations" in payload["blocked_until"]
    assert (
        "paddleocr_text_target_gate_requires_privacy_cleared_holdout_metrics"
        in payload["blocked_until"]
    )
    assert commands[0].startswith(
        "backend/.venv/bin/python backend/scripts/build_supplement_operator_review_batch_triage.py"
    )
    assert "--queue-key review_pii_screening" in commands[0]
    assert (
        "--batch-file outputs/generated/supplement-learning/2026-06-04/operator-review/batches/review_pii_screening-001.jsonl"
        in commands[0]
    )
    assert (
        "--output outputs/generated/supplement-learning/2026-06-04/operator-review/review_pii_screening-001.triage.json"
        in commands[0]
    )
    assert "backend/scripts/extract_supplement_pii_reviewed_decisions.py" in commands[4]
    assert (
        "--candidate-manifest outputs/generated/supplement-learning/2026-06-04/operator-review/supplement-review-ocr-ground-truth-candidates.jsonl"
        in commands[4]
    )
    assert "backend/scripts/export_supplement_ocr_ground_truth_template.py" in commands[7]
    assert (
        "--candidate-manifest outputs/generated/supplement-learning/2026-06-04/operator-review/reconciled/teacher-safe-ocr-candidates.jsonl"
        in commands[7]
    )
    assert "--source-root data/nutrition_reference/crawling-image" in commands[7]
    assert "backend/scripts/build_supplement_ocr_ground_truth_review_bundle.py" in commands[8]
    assert "backend/scripts/preflight_supplement_ocr_ground_truth_manifest.py" in commands[9]
    assert (
        "--ground-truth outputs/generated/supplement-learning/2026-06-04/operator-review/ocr-ground-truth-review-bundle/ground-truth.todo.jsonl"
        in commands[9]
    )
    assert "--required-expected-section allergen_warnings" in commands[9]
    _assert_pii_ocr_command_chain(commands)
    assert "--require-all-reviewed" in commands[5]
    _assert_pii_execution_states(payload)
    assert str(tmp_path) not in serialized
    assert "/Volumes/" not in serialized
    assert "/Users/" not in serialized
    assert payload["raw_provider_payload_stored"] is False


def test_command_checklist_preserves_applied_batch_overrides_for_pii_queue(
    tmp_path: Path,
) -> None:
    """Verify later queue commands keep already-applied batch decisions."""
    paths = _prepare_repo(tmp_path)
    work_order = _work_order_payload()
    work_order.update(
        {
            "batch_key": "review_pii_screening:001",
            "queue_key": "review_pii_screening",
            "batch_file_name": "review_pii_screening-001.jsonl",
        }
    )
    _write_json(paths["next_work_order"], work_order)
    override_dir = paths["operator_dir"] / "batches-autofill-applied"
    override_dir.mkdir(parents=True, exist_ok=True)
    (override_dir / "brand_product_review-001.jsonl").write_text("", encoding="utf-8")
    (override_dir / "brand_product_review-002.jsonl").write_text("", encoding="utf-8")

    payload = checklist.build_command_checklist(
        repo_root=paths["repo_root"],
        operator_dir=paths["operator_dir"],
        todo_dir=paths["todo_dir"],
        input_paths={
            "next_work_order": paths["next_work_order"],
            "post_completion_plan": paths["post_completion_plan"],
        },
        batch_override_dir=override_dir,
    )
    reconcile_command = payload["commands"][2]["command"]
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)

    assert payload["preserved_batch_override_count"] == 2
    assert payload["preserved_batch_override_names"] == {
        "brand_product_review:001": (
            "outputs/generated/supplement-learning/2026-06-04/operator-review/"
            "batches-autofill-applied/brand_product_review-001.jsonl"
        ),
        "brand_product_review:002": (
            "outputs/generated/supplement-learning/2026-06-04/operator-review/"
            "batches-autofill-applied/brand_product_review-002.jsonl"
        ),
    }
    assert (
        "--batch-file-override brand_product_review:001 "
        "outputs/generated/supplement-learning/2026-06-04/operator-review/"
        "batches-autofill-applied/brand_product_review-001.jsonl"
    ) in reconcile_command
    assert (
        "--batch-file-override brand_product_review:002 "
        "outputs/generated/supplement-learning/2026-06-04/operator-review/"
        "batches-autofill-applied/brand_product_review-002.jsonl"
    ) in reconcile_command
    assert str(tmp_path) not in serialized
    assert "/Volumes/" not in serialized
    assert "/Users/" not in serialized


def test_command_checklist_keeps_long_reconcile_commands_complete(tmp_path: Path) -> None:
    """Verify many preserved batch overrides do not truncate the command."""
    paths = _prepare_repo(tmp_path)
    work_order = _work_order_payload()
    work_order.update(
        {
            "batch_key": "review_pii_screening:001",
            "queue_key": "review_pii_screening",
            "batch_file_name": "review_pii_screening-001.jsonl",
        }
    )
    _write_json(paths["next_work_order"], work_order)
    override_dir = paths["operator_dir"] / "batches-autofill-applied"
    override_dir.mkdir(parents=True, exist_ok=True)
    for batch_number in range(1, 9):
        (override_dir / f"brand_product_review-{batch_number:03d}.jsonl").write_text(
            "",
            encoding="utf-8",
        )

    payload = checklist.build_command_checklist(
        repo_root=paths["repo_root"],
        operator_dir=paths["operator_dir"],
        todo_dir=paths["todo_dir"],
        input_paths={
            "next_work_order": paths["next_work_order"],
            "post_completion_plan": paths["post_completion_plan"],
        },
        batch_override_dir=override_dir,
    )
    reconcile_command = payload["commands"][2]["command"]

    assert payload["preserved_batch_override_count"] == 8
    assert (
        "--batch-file-override brand_product_review:008 "
        "outputs/generated/supplement-learning/2026-06-04/operator-review/"
        "batches-autofill-applied/brand_product_review-008.jsonl"
    ) in reconcile_command
    assert len(reconcile_command) > 2000
    assert len(reconcile_command) < checklist.COMMAND_MAX_LENGTH


def test_command_checklist_generates_repo_relative_yolo_commands(tmp_path: Path) -> None:
    """Verify YOLO section commands are concrete and repo-relative."""
    paths = _prepare_repo(tmp_path)
    work_order = _work_order_payload()
    work_order.update(
        {
            "batch_key": "yolo_section_annotation:001",
            "queue_key": "yolo_section_annotation",
            "batch_file_name": "yolo_section_annotation-001.jsonl",
        }
    )
    _write_json(paths["next_work_order"], work_order)

    payload = checklist.build_command_checklist(
        repo_root=paths["repo_root"],
        operator_dir=paths["operator_dir"],
        todo_dir=paths["todo_dir"],
        input_paths={
            "next_work_order": paths["next_work_order"],
            "post_completion_plan": paths["post_completion_plan"],
        },
    )
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    commands = [row["command"] for row in payload["commands"]]

    assert payload["queue_key"] == "yolo_section_annotation"
    assert payload["command_count"] == 10
    assert commands[0].startswith(
        "backend/.venv/bin/python backend/scripts/build_supplement_operator_review_batch_triage.py"
    )
    assert "--queue-key yolo_section_annotation" in commands[0]
    assert (
        "--batch-file outputs/generated/supplement-learning/2026-06-04/operator-review/batches/yolo_section_annotation-001.jsonl"
        in commands[0]
    )
    assert (
        "--output outputs/generated/supplement-learning/2026-06-04/operator-review/yolo_section_annotation-001.triage.json"
        in commands[0]
    )
    assert "backend/scripts/extract_supplement_yolo_reviewed_annotations.py" in commands[4]
    assert "backend/scripts/materialize_supplement_section_yolo_dataset.py" in commands[7]
    assert "backend/scripts/gate_supplement_yolo_section_dataset.py" in commands[-1]
    assert "> outputs/generated/supplement-learning" in commands[7]
    assert payload["commands"][0]["execution_state"] == "runnable_now"
    assert payload["commands"][1]["execution_state"] == "blocked_until_operator_edits"
    assert payload["commands"][5]["execution_state"] == "blocked_until_all_yolo_rows_reviewed"
    assert payload["commands"][-1]["execution_state"] == "blocked_until_yolo_validation"
    assert str(tmp_path) not in serialized
    assert "/Volumes/" not in serialized
    assert "/Users/" not in serialized
    assert payload["training_execution_performed_by_script"] is False


def test_command_checklist_rejects_outside_repo_paths(tmp_path: Path) -> None:
    """Verify generated command paths must stay under repo root."""
    paths = _prepare_repo(tmp_path)

    with pytest.raises(checklist.OperatorCommandChecklistError, match="outside repo root"):
        checklist.build_command_checklist(
            repo_root=paths["repo_root"],
            operator_dir=tmp_path / "outside",
            todo_dir=paths["todo_dir"],
            input_paths={
                "next_work_order": paths["next_work_order"],
                "post_completion_plan": paths["post_completion_plan"],
            },
        )


def test_command_checklist_rejects_outside_repo_taxonomy_staging(tmp_path: Path) -> None:
    """Verify explicit taxonomy staging must stay under repo root."""
    paths = _prepare_repo(tmp_path)

    with pytest.raises(checklist.OperatorCommandChecklistError, match="outside repo root"):
        checklist.build_command_checklist(
            repo_root=paths["repo_root"],
            operator_dir=paths["operator_dir"],
            todo_dir=paths["todo_dir"],
            input_paths={
                "next_work_order": paths["next_work_order"],
                "post_completion_plan": paths["post_completion_plan"],
            },
            taxonomy_staging=tmp_path / "outside-staging.jsonl",
        )


def test_command_checklist_rejects_missing_explicit_taxonomy_staging(tmp_path: Path) -> None:
    """Verify explicit taxonomy staging must exist before command emission."""
    paths = _prepare_repo(tmp_path)

    with pytest.raises(checklist.OperatorCommandChecklistError, match="does not exist"):
        checklist.build_command_checklist(
            repo_root=paths["repo_root"],
            operator_dir=paths["operator_dir"],
            todo_dir=paths["todo_dir"],
            input_paths={
                "next_work_order": paths["next_work_order"],
                "post_completion_plan": paths["post_completion_plan"],
            },
            taxonomy_staging=paths["repo_root"] / "missing-taxonomy-staging.jsonl",
        )


def test_command_checklist_rejects_unsafe_payload(tmp_path: Path) -> None:
    """Verify unsafe local path markers in inputs are rejected."""
    paths = _prepare_repo(tmp_path)
    payload = _work_order_payload()
    payload["batch_file_name"] = "/Users/leak.jsonl"
    _write_json(paths["next_work_order"], payload)

    with pytest.raises(checklist.OperatorCommandChecklistError, match="Unsafe local path"):
        checklist.build_command_checklist(
            repo_root=paths["repo_root"],
            operator_dir=paths["operator_dir"],
            todo_dir=paths["todo_dir"],
            input_paths={
                "next_work_order": paths["next_work_order"],
                "post_completion_plan": paths["post_completion_plan"],
            },
        )


def test_command_checklist_cli_writes_markdown_without_paths(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI writes redacted JSON and Markdown."""
    paths = _prepare_repo(tmp_path)
    output_path = paths["repo_root"] / "outputs/checklist.json"
    markdown_path = paths["repo_root"] / "outputs/checklist.md"
    taxonomy_staging = (
        paths["repo_root"]
        / "outputs/todo-list/2026-06-04/2026-06-04-supplement-taxonomy-db-staging.jsonl"
    )
    taxonomy_staging.parent.mkdir(parents=True, exist_ok=True)
    taxonomy_staging.write_text("", encoding="utf-8")

    checklist.main(
        [
            "--repo-root",
            str(paths["repo_root"]),
            "--operator-dir",
            str(paths["operator_dir"]),
            "--todo-dir",
            str(paths["todo_dir"]),
            "--taxonomy-staging",
            str(taxonomy_staging),
            "--next-work-order",
            str(paths["next_work_order"]),
            "--post-completion-plan",
            str(paths["post_completion_plan"]),
            "--output",
            str(output_path),
            "--markdown-output",
            str(markdown_path),
        ]
    )

    stdout = capsys.readouterr().out
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")

    assert payload["schema_version"] == checklist.SCHEMA_VERSION
    assert "# Supplement Operator Next Command Checklist" in markdown
    assert "Current blocker" in markdown
    assert "Operator next action" in markdown
    assert "Execution state" in markdown
    assert "Blocked by" in markdown
    assert "Requires operator input" in markdown
    assert "build_supplement_brand_review_batch_triage" in markdown
    assert "preflight_supplement_brand_review_contact_sheet" in markdown
    assert "apply_supplement_brand_batch_review_csv_decisions" in markdown
    assert "preflight_supplement_operator_review_batch_file" in markdown
    for redacted_output in (stdout, json.dumps(payload, ensure_ascii=False), markdown):
        assert str(tmp_path) not in redacted_output
        assert "/Volumes/" not in redacted_output
        assert "/Users/" not in redacted_output
        assert "file://" not in redacted_output
