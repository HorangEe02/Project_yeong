"""Tests for supplement operator review batch reconciliation."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

reconciler = importlib.import_module("scripts.reconcile_supplement_operator_review_batch_files")


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


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    """Write JSONL fixture rows.

    Args:
        path: Destination path.
        rows: JSON rows.

    Returns:
        Written path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def _batch_plan() -> dict[str, Any]:
    """Return a compact batch plan fixture.

    Returns:
        Batch plan payload.
    """
    return {
        "schema_version": "supplement-operator-review-batch-plan-v1",
        "batch_count": 4,
        "batch_size": 2,
        "pending_queue_count": 3,
        "total_pending_operator_action_count": 7,
        "batches": [
            _batch("brand_product_review:001", "brand_product_review", 1, 2),
            _batch("brand_product_review:002", "brand_product_review", 3, 3),
            _batch("review_pii_screening:001", "review_pii_screening", 1, 2),
            _batch("yolo_section_annotation:001", "yolo_section_annotation", 1, 2),
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


def _batch(batch_key: str, queue_key: str, start: int, end: int) -> dict[str, Any]:
    """Return one batch plan row.

    Args:
        batch_key: Batch key.
        queue_key: Queue key.
        start: One-based row start.
        end: One-based row end.

    Returns:
        Batch row.
    """
    return {
        "batch_key": batch_key,
        "queue_key": queue_key,
        "editable_file_name": (
            "annotation.todo.jsonl"
            if queue_key == "yolo_section_annotation"
            else "decisions.todo.jsonl"
        ),
        "row_index_start": start,
        "row_index_end": end,
        "pending_row_count": end - start + 1,
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


def _brand_row(fixture_id: str, product_name: str = "") -> dict[str, Any]:
    """Return one brand decision row.

    Args:
        fixture_id: Fixture id.
        product_name: Reviewed product name.

    Returns:
        Decision row.
    """
    return {
        "schema_version": "supplement-brand-review-decision-v1",
        "fixture_id": fixture_id,
        "brand_review_decision": {
            "decision": "approve" if product_name else "",
            "reviewer_id": "operator_batch" if product_name else "",
            "reviewed_at": "2026-06-03T00:00:00Z" if product_name else "",
            "reviewed_manufacturer": "Safe Maker" if product_name else "",
            "reviewed_product_name": product_name,
            "reason_codes": ["reviewed_label_or_catalog"] if product_name else [],
            "attest_brand_product_review_completed": bool(product_name),
            "attest_not_using_product_folder_literal_as_manufacturer": bool(product_name),
            "attest_product_name_reviewed_from_label_or_safe_catalog": bool(product_name),
            "attest_no_raw_ocr_or_provider_payload_copied": bool(product_name),
            "attest_db_import_allowed": bool(product_name),
        },
    }


def _pii_row(fixture_id: str) -> dict[str, Any]:
    """Return one PII decision row.

    Args:
        fixture_id: Fixture id.

    Returns:
        Decision row.
    """
    return {
        "schema_version": "supplement-review-pii-screening-decision-v1",
        "fixture_id": fixture_id,
        "pii_screening_decision": {
            "decision": "",
            "reviewer_id": "",
            "reviewed_at": "",
            "reason_codes": [],
            "attest_local_screening_completed": False,
            "attest_no_personal_data_visible": False,
            "attest_no_raw_text_copied": False,
            "attest_teacher_ocr_transfer_allowed": False,
        },
    }


def _yolo_row(fixture_id: str, accepted: bool = False) -> dict[str, Any]:
    """Return one YOLO annotation row.

    Args:
        fixture_id: Fixture id.
        accepted: Whether a reviewed bbox is present.

    Returns:
        Annotation row.
    """
    boxes = (
        [
            {
                "label": "supplement_facts",
                "x_center": 0.5,
                "y_center": 0.5,
                "width": 0.4,
                "height": 0.3,
            }
        ]
        if accepted
        else []
    )
    return {
        "schema_version": "supplement-yolo-annotation-template-row-v1",
        "fixture_id": fixture_id,
        "annotation_status": "accepted_for_training" if accepted else "pending_human_bbox_review",
        "image_path": "images/example.webp",
        "source_ref": "crawling-image:redacted-test-ref",
        "label_snapshot": {
            "schema_version": "supplement-section-yolo-label-candidates-v1",
            "human_review_required": not accepted,
            "training_export_allowed": accepted,
            "boxes": boxes,
            "text_stored": False,
        },
        "db_write_performed": False,
        "training_export_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }


def _input_paths(tmp_path: Path) -> dict[str, Path]:
    """Write original editable fixtures.

    Args:
        tmp_path: Temporary directory.

    Returns:
        Input paths.
    """
    return {
        "batch_plan": _write_json(tmp_path / "plan.json", _batch_plan()),
        "brand_decisions": _write_jsonl(
            tmp_path / "brand.jsonl",
            [
                _brand_row("brand-secret-a"),
                _brand_row("brand-secret-b"),
                _brand_row("brand-secret-c"),
            ],
        ),
        "pii_decisions": _write_jsonl(
            tmp_path / "pii.jsonl",
            [_pii_row("pii-secret-a"), _pii_row("pii-secret-b")],
        ),
        "yolo_annotations": _write_jsonl(
            tmp_path / "yolo.jsonl",
            [_yolo_row("yolo-secret-a"), _yolo_row("yolo-secret-b")],
        ),
    }


def _write_batch_files(tmp_path: Path) -> Path:
    """Write edited batch files.

    Args:
        tmp_path: Temporary directory.

    Returns:
        Batch directory path.
    """
    batch_dir = tmp_path / "batches"
    _write_jsonl(
        batch_dir / "brand_product_review-001.jsonl",
        [_brand_row("brand-secret-a"), _brand_row("brand-secret-b", "Reviewed Product B")],
    )
    _write_jsonl(batch_dir / "brand_product_review-002.jsonl", [_brand_row("brand-secret-c")])
    _write_jsonl(
        batch_dir / "review_pii_screening-001.jsonl",
        [_pii_row("pii-secret-a"), _pii_row("pii-secret-b")],
    )
    _write_jsonl(
        batch_dir / "yolo_section_annotation-001.jsonl",
        [_yolo_row("yolo-secret-a", accepted=True), _yolo_row("yolo-secret-b")],
    )
    return batch_dir


def test_reconcile_operator_review_batch_files_writes_redacted_summary_and_copies(
    tmp_path: Path,
) -> None:
    """Verify edited batch rows are merged into queue-level copies."""
    paths = _input_paths(tmp_path)
    batch_dir = _write_batch_files(tmp_path)
    output_dir = tmp_path / "reconciled"

    summary = reconciler.reconcile_operator_review_batch_files(
        input_paths=paths,
        batch_dir=batch_dir,
        output_dir=output_dir,
    )

    assert summary["schema_version"] == "supplement-operator-review-batch-file-reconcile-v1"
    assert summary["batch_count"] == 4
    assert summary["expected_row_count"] == 7
    assert summary["changed_row_count"] == 2
    assert summary["human_review_changes_detected"] is True
    assert summary["batch_dir_hash"].startswith("fp-")
    assert len(summary["batch_dir_hash"]) == 15
    assert summary["output_dir_hash"].startswith("fp-")
    assert len(summary["output_dir_hash"]) == 15
    assert all(
        value.startswith("fp-") and len(value) == 15
        for value in summary["input_path_hashes"].values()
    )
    brand_rows = [
        json.loads(line)
        for line in (output_dir / "brand_product_review.reconciled.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert brand_rows[1]["brand_review_decision"]["reviewed_product_name"] == "Reviewed Product B"
    dumped = json.dumps(summary, ensure_ascii=False)
    assert "Reviewed Product B" not in dumped
    assert "brand-secret-b" not in dumped
    assert "images/example.webp" not in dumped
    assert "crawling-image" not in dumped
    assert str(tmp_path) not in dumped


def test_reconcile_uses_single_batch_file_override_without_source_overwrite(
    tmp_path: Path,
) -> None:
    """Verify one applied batch copy can replace the source batch during reconcile."""
    paths = _input_paths(tmp_path)
    batch_dir = _write_batch_files(tmp_path)
    override_file = tmp_path / "applied" / "brand_product_review-001.jsonl"
    _write_jsonl(
        override_file,
        [_brand_row("brand-secret-a", "Reviewed Product A"), _brand_row("brand-secret-b")],
    )
    output_dir = tmp_path / "reconciled"

    summary = reconciler.reconcile_operator_review_batch_files(
        input_paths=paths,
        batch_dir=batch_dir,
        output_dir=output_dir,
        batch_file_overrides={"brand_product_review:001": override_file},
    )

    brand_rows = [
        json.loads(line)
        for line in (output_dir / "brand_product_review.reconciled.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    source_rows = [
        json.loads(line)
        for line in (batch_dir / "brand_product_review-001.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert summary["batch_file_override_count"] == 1
    assert summary["batch_file_override_names"] == {
        "brand_product_review:001": "brand_product_review-001.jsonl"
    }
    assert summary["batches"][0]["batch_file_override_used"] is True
    assert summary["original_editable_files_modified"] is False
    assert brand_rows[0]["brand_review_decision"]["reviewed_product_name"] == "Reviewed Product A"
    assert source_rows[0]["brand_review_decision"]["reviewed_product_name"] == ""
    dumped = json.dumps(summary, ensure_ascii=False)
    assert "Reviewed Product A" not in dumped
    assert "brand-secret-a" not in dumped
    assert str(tmp_path) not in dumped


def test_reconcile_rejects_unknown_batch_file_override(tmp_path: Path) -> None:
    """Verify override keys must map to a planned batch key."""
    paths = _input_paths(tmp_path)
    batch_dir = _write_batch_files(tmp_path)

    try:
        reconciler.reconcile_operator_review_batch_files(
            input_paths=paths,
            batch_dir=batch_dir,
            output_dir=tmp_path / "reconciled",
            batch_file_overrides={
                "brand_product_review:999": batch_dir / "brand_product_review-001.jsonl"
            },
        )
    except reconciler.BatchFileReconcileError as exc:
        assert "batch plan" in str(exc)
    else:
        raise AssertionError("unknown override batch key should fail closed")


def test_reconcile_rejects_missing_batch_file(tmp_path: Path) -> None:
    """Verify missing batch files fail closed."""
    paths = _input_paths(tmp_path)
    batch_dir = _write_batch_files(tmp_path)
    (batch_dir / "brand_product_review-002.jsonl").unlink()

    try:
        reconciler.reconcile_operator_review_batch_files(
            input_paths=paths,
            batch_dir=batch_dir,
            output_dir=tmp_path / "reconciled",
        )
    except reconciler.BatchFileReconcileError as exc:
        assert "missing or unreadable" in str(exc)
    else:
        raise AssertionError("missing batch file should fail closed")


def test_reconcile_rejects_batch_row_count_mismatch(tmp_path: Path) -> None:
    """Verify batch row count must match the plan range."""
    paths = _input_paths(tmp_path)
    batch_dir = _write_batch_files(tmp_path)
    _write_jsonl(batch_dir / "brand_product_review-001.jsonl", [_brand_row("brand-secret-a")])

    try:
        reconciler.reconcile_operator_review_batch_files(
            input_paths=paths,
            batch_dir=batch_dir,
            output_dir=tmp_path / "reconciled",
        )
    except reconciler.BatchFileReconcileError as exc:
        assert "count" in str(exc).casefold()
    else:
        raise AssertionError("row count mismatch should fail closed")


def test_reconcile_rejects_unsafe_batch_row(tmp_path: Path) -> None:
    """Verify raw fields in edited batch files are rejected."""
    paths = _input_paths(tmp_path)
    batch_dir = _write_batch_files(tmp_path)
    unsafe = _brand_row("brand-secret-a", "Reviewed Product A")
    unsafe["raw_ocr_text"] = "do not copy"
    _write_jsonl(
        batch_dir / "brand_product_review-001.jsonl",
        [unsafe, _brand_row("brand-secret-b")],
    )

    try:
        reconciler.reconcile_operator_review_batch_files(
            input_paths=paths,
            batch_dir=batch_dir,
            output_dir=tmp_path / "reconciled",
        )
    except reconciler.BatchFileReconcileError as exc:
        assert "unsafe" in str(exc).casefold()
    else:
        raise AssertionError("unsafe batch row should fail closed")


def test_build_reconcile_markdown_is_redacted(tmp_path: Path) -> None:
    """Verify Markdown reconciliation report is aggregate-only."""
    summary = reconciler.reconcile_operator_review_batch_files(
        input_paths=_input_paths(tmp_path),
        batch_dir=_write_batch_files(tmp_path),
        output_dir=tmp_path / "reconciled",
    )

    markdown = reconciler.build_reconcile_markdown(summary)

    assert "brand_product_review-001.jsonl" in markdown
    assert "Reviewed Product B" not in markdown
    assert "brand-secret-b" not in markdown
    assert "images/example.webp" not in markdown
    assert str(tmp_path) not in markdown


def test_reconcile_cli_writes_summary_markdown_and_copies(
    tmp_path: Path,
    capsys: Any,
) -> None:
    """Verify CLI writes reconciliation artifacts."""
    paths = _input_paths(tmp_path)
    batch_dir = _write_batch_files(tmp_path)
    output_dir = tmp_path / "reconciled"
    summary_path = tmp_path / "out" / "summary.json"
    markdown_path = tmp_path / "out" / "summary.md"

    reconciler.main(
        [
            "--batch-plan",
            str(paths["batch_plan"]),
            "--brand-decisions",
            str(paths["brand_decisions"]),
            "--pii-decisions",
            str(paths["pii_decisions"]),
            "--yolo-annotations",
            str(paths["yolo_annotations"]),
            "--batch-dir",
            str(batch_dir),
            "--output-dir",
            str(output_dir),
            "--summary-output",
            str(summary_path),
            "--markdown-output",
            str(markdown_path),
        ]
    )

    captured = capsys.readouterr().out
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["changed_row_count"] == 2
    assert summary["batch_dir_hash"].startswith("fp-")
    assert len(summary["batch_dir_hash"]) == 15
    assert summary["output_dir_hash"].startswith("fp-")
    assert len(summary["output_dir_hash"]) == 15
    assert markdown_path.is_file()
    assert (output_dir / "yolo_section_annotation.reconciled.jsonl").is_file()
    assert '"changed_row_count": 2' in captured
    assert "Reviewed Product B" not in captured
    assert str(tmp_path) not in captured
