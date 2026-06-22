"""Tests for supplement operator review batch plan generation."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

batch_plan = importlib.import_module("scripts.build_supplement_operator_review_batch_plan")


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


def _queue_summary(**overrides: Any) -> dict[str, Any]:
    """Return an operator queue summary fixture.

    Args:
        overrides: Payload overrides.

    Returns:
        Queue summary payload.
    """
    payload = {
        "schema_version": "supplement-operator-review-queue-summary-v1",
        "queue_count": 3,
        "pending_queue_count": 3,
        "total_pending_operator_action_count": 808,
        "next_queue_key": "brand_product_review",
        "ready_for_next_pipeline_step": False,
        "queues": [
            _queue_row("brand_product_review", 388, "complete_operator_brand_review"),
            _queue_row("review_pii_screening", 215, "complete_operator_pii_review"),
            _queue_row(
                "yolo_section_annotation",
                205,
                "complete_supplement_section_bbox_review",
            ),
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
    payload.update(overrides)
    return payload


def _queue_row(queue_key: str, pending: int, next_action: str) -> dict[str, Any]:
    """Return one queue row fixture.

    Args:
        queue_key: Queue key.
        pending: Pending operator action count.
        next_action: Next operator action token.

    Returns:
        Queue row.
    """
    return {
        "queue_key": queue_key,
        "queue_status": "pending_operator_review",
        "pending_operator_action_count": pending,
        "next_operator_action": next_action,
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


def _brand_bundle(**overrides: Any) -> dict[str, Any]:
    """Return a brand review bundle summary fixture.

    Args:
        overrides: Payload overrides.

    Returns:
        Bundle summary.
    """
    payload = {
        "schema_version": "supplement-brand-review-bundle-v1",
        "decision_template_name": "decisions.todo.jsonl",
        "csv_name": "review.csv",
        "html_index_name": "review-index.html",
        "readme_name": "README.md",
        "decision_template_row_count": 388,
        "operator_decision_required_count": 388,
        "db_write_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }
    payload.update(overrides)
    return payload


def _pii_bundle(**overrides: Any) -> dict[str, Any]:
    """Return a PII review bundle summary fixture.

    Args:
        overrides: Payload overrides.

    Returns:
        Bundle summary.
    """
    payload = {
        "schema_version": "supplement-review-pii-screening-review-bundle-v1",
        "decision_template_name": "decisions.todo.jsonl",
        "html_index_name": "review-index.html",
        "readme_name": "README.md",
        "decision_template_row_count": 215,
        "operator_decision_required_count": 215,
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }
    payload.update(overrides)
    return payload


def _yolo_bundle(**overrides: Any) -> dict[str, Any]:
    """Return a YOLO annotation bundle summary fixture.

    Args:
        overrides: Payload overrides.

    Returns:
        Bundle summary.
    """
    payload = {
        "schema_version": "supplement-yolo-annotation-review-bundle-v1",
        "annotation_template_name": "annotation.todo.jsonl",
        "html_index_name": "annotation-index.html",
        "readme_name": "README.md",
        "annotation_template_row_count": 205,
        "required_human_review_count": 205,
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
        "training_export_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }
    payload.update(overrides)
    return payload


def _input_paths(tmp_path: Path) -> dict[str, Path]:
    """Write default input fixtures.

    Args:
        tmp_path: Temporary directory.

    Returns:
        Input path mapping.
    """
    return {
        "queue_summary": _write_json(tmp_path / "queue.json", _queue_summary()),
        "brand_bundle_summary": _write_json(tmp_path / "brand.json", _brand_bundle()),
        "pii_bundle_summary": _write_json(tmp_path / "pii.json", _pii_bundle()),
        "yolo_bundle_summary": _write_json(tmp_path / "yolo.json", _yolo_bundle()),
    }


def test_build_operator_review_batch_plan_splits_pending_queues(
    tmp_path: Path,
) -> None:
    """Verify pending queues are split into bounded row ranges."""
    plan = batch_plan.build_operator_review_batch_plan(
        input_paths=_input_paths(tmp_path),
        batch_size=100,
    )

    assert plan["batch_count"] == 10
    assert plan["queue_batch_counts"] == {
        "brand_product_review": 4,
        "review_pii_screening": 3,
        "yolo_section_annotation": 3,
    }
    assert plan["batches"][0]["batch_key"] == "brand_product_review:001"
    assert plan["batches"][0]["row_index_start"] == 1
    assert plan["batches"][0]["row_index_end"] == 100
    assert plan["batches"][3]["row_index_end"] == 388
    assert plan["batches"][-1]["queue_key"] == "yolo_section_annotation"
    assert plan["batches"][-1]["pending_row_count"] == 5
    assert plan["batches"][-1]["editable_file_name"] == "annotation.todo.jsonl"
    dumped = json.dumps(plan, ensure_ascii=False)
    assert str(tmp_path) not in dumped
    assert "/private/" not in dumped


def test_build_operator_review_batch_plan_handles_ready_queue(
    tmp_path: Path,
) -> None:
    """Verify a ready queue summary produces no batches."""
    paths = {
        "queue_summary": _write_json(
            tmp_path / "queue.json",
            _queue_summary(
                pending_queue_count=0,
                total_pending_operator_action_count=0,
                next_queue_key=None,
                ready_for_next_pipeline_step=True,
                queues=[
                    _queue_row("brand_product_review", 0, "complete_operator_brand_review"),
                    _queue_row("review_pii_screening", 0, "complete_operator_pii_review"),
                ],
            ),
        )
    }

    plan = batch_plan.build_operator_review_batch_plan(input_paths=paths, batch_size=50)

    assert plan["batch_count"] == 0
    assert plan["batches"] == []
    assert plan["ready_for_next_pipeline_step"] is True


def test_build_operator_review_batch_plan_rejects_unsafe_queue_summary(
    tmp_path: Path,
) -> None:
    """Verify raw OCR fields fail closed."""
    paths = _input_paths(tmp_path)
    _write_json(paths["queue_summary"], _queue_summary(raw_ocr_text="visible text"))

    try:
        batch_plan.build_operator_review_batch_plan(input_paths=paths, batch_size=50)
    except batch_plan.OperatorBatchPlanError as exc:
        assert "Unsafe raw" in str(exc)
    else:
        raise AssertionError("unsafe queue summary should fail closed")


def test_build_operator_review_batch_plan_rejects_wrong_bundle_schema(
    tmp_path: Path,
) -> None:
    """Verify mismatched bundle summaries fail closed."""
    paths = _input_paths(tmp_path)
    _write_json(paths["brand_bundle_summary"], _brand_bundle(schema_version="wrong"))

    try:
        batch_plan.build_operator_review_batch_plan(input_paths=paths, batch_size=50)
    except batch_plan.OperatorBatchPlanError as exc:
        assert "schema does not match" in str(exc)
    else:
        raise AssertionError("wrong bundle schema should fail closed")


def test_build_operator_review_batch_markdown_is_redacted(tmp_path: Path) -> None:
    """Verify Markdown output contains only safe row ranges."""
    plan = batch_plan.build_operator_review_batch_plan(
        input_paths=_input_paths(tmp_path),
        batch_size=200,
    )

    markdown = batch_plan.build_operator_review_batch_markdown(plan)

    assert "brand_product_review:001" in markdown
    assert "annotation.todo.jsonl" in markdown
    assert str(tmp_path) not in markdown
    assert "/private/" not in markdown
    assert "raw_ocr_text" not in markdown


def test_operator_review_batch_plan_cli_writes_json_and_markdown(
    tmp_path: Path,
    capsys: Any,
) -> None:
    """Verify CLI writes JSON/Markdown and prints compact redacted summary."""
    paths = _input_paths(tmp_path)
    output_path = tmp_path / "out" / "batch-plan.json"
    markdown_path = tmp_path / "out" / "batch-plan.md"

    batch_plan.main(
        [
            "--queue-summary",
            str(paths["queue_summary"]),
            "--brand-bundle-summary",
            str(paths["brand_bundle_summary"]),
            "--pii-bundle-summary",
            str(paths["pii_bundle_summary"]),
            "--yolo-bundle-summary",
            str(paths["yolo_bundle_summary"]),
            "--batch-size",
            "100",
            "--output",
            str(output_path),
            "--markdown-output",
            str(markdown_path),
        ]
    )

    captured = capsys.readouterr().out
    plan = json.loads(output_path.read_text(encoding="utf-8"))
    assert plan["schema_version"] == "supplement-operator-review-batch-plan-v1"
    assert plan["batch_count"] == 10
    assert markdown_path.is_file()
    assert '"batch_count": 10' in captured
    assert str(tmp_path) not in captured
