"""Tests for supplement operator review queue summary."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

queue_builder = importlib.import_module("scripts.build_supplement_operator_review_queue")


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


def _brand_preflight(**overrides: Any) -> dict[str, Any]:
    """Return a brand review preflight fixture.

    Args:
        overrides: Payload overrides.

    Returns:
        Preflight payload.
    """
    payload = {
        "schema_version": "supplement-brand-review-decision-preflight-v1",
        "brand_candidate_count": 388,
        "decision_row_count": 388,
        "blank_decision_count": 388,
        "valid_decision_count": 0,
        "invalid_decision_count": 0,
        "pending_operator_action_count": 388,
        "ready_for_requested_apply": False,
        "next_operator_action": "complete_operator_brand_review",
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }
    payload.update(overrides)
    return payload


def _pii_preflight(**overrides: Any) -> dict[str, Any]:
    """Return a review-image PII preflight fixture.

    Args:
        overrides: Payload overrides.

    Returns:
        Preflight payload.
    """
    payload = {
        "schema_version": "supplement-review-pii-screening-decision-preflight-v1",
        "candidate_row_count": 215,
        "decision_row_count": 215,
        "blank_decision_count": 215,
        "valid_decision_count": 0,
        "invalid_decision_count": 0,
        "pending_operator_action_count": 215,
        "ready_for_requested_apply": False,
        "next_operator_action": "complete_operator_pii_review",
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }
    payload.update(overrides)
    return payload


def _yolo_preflight(**overrides: Any) -> dict[str, Any]:
    """Return a YOLO section annotation preflight fixture.

    Args:
        overrides: Payload overrides.

    Returns:
        Preflight payload.
    """
    payload = {
        "schema_version": "supplement-yolo-annotation-decision-preflight-v1",
        "template_row_count": 205,
        "blank_box_row_count": 205,
        "valid_accepted_row_count": 0,
        "invalid_row_count": 0,
        "pending_operator_action_count": 205,
        "ready_for_requested_promotion": False,
        "next_operator_action": "complete_supplement_section_bbox_review",
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
        "training_performed": False,
        "export_artifact_written": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
        "source_ref_printed": False,
        "image_path_printed": False,
        "labels_printed": False,
    }
    payload.update(overrides)
    return payload


def _readiness() -> dict[str, Any]:
    """Return a minimal readiness report fixture.

    Returns:
        Readiness payload.
    """
    return {
        "schema_version": "supplement-learning-pipeline-readiness-v1",
        "stages": [
            {"stage_key": "brand_product_review", "status": "pending_operator_review"},
            {"stage_key": "review_pii_screening", "status": "pending_operator_review"},
            {"stage_key": "yolo_section_annotation", "status": "pending_operator_review"},
        ],
        "db_write_performed": False,
        "external_provider_call_performed": False,
        "llm_call_performed": False,
        "training_execution_performed_by_script": False,
        "source_image_read_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
    }


def _input_paths(tmp_path: Path) -> dict[str, Path]:
    """Write default input fixtures.

    Args:
        tmp_path: Temporary directory.

    Returns:
        Input path mapping.
    """
    return {
        "brand_preflight": _write_json(tmp_path / "brand.json", _brand_preflight()),
        "pii_preflight": _write_json(tmp_path / "pii.json", _pii_preflight()),
        "yolo_preflight": _write_json(tmp_path / "yolo.json", _yolo_preflight()),
        "readiness": _write_json(tmp_path / "readiness.json", _readiness()),
    }


def test_build_operator_review_queue_summarizes_all_pending_reviews(tmp_path: Path) -> None:
    """Verify all three review blockers are summarized in operator order."""
    summary = queue_builder.build_operator_review_queue(input_paths=_input_paths(tmp_path))

    assert summary["queue_count"] == 3
    assert summary["pending_queue_count"] == 3
    assert summary["total_pending_operator_action_count"] == 808
    assert summary["ready_for_next_pipeline_step"] is False
    assert summary["next_queue_key"] == "brand_product_review"
    assert [queue["queue_key"] for queue in summary["queues"]] == [
        "brand_product_review",
        "review_pii_screening",
        "yolo_section_annotation",
    ]
    assert summary["queues"][0]["pending_operator_action_count"] == 388
    assert summary["queues"][2]["blank_row_count"] == 205
    dumped = json.dumps(summary, ensure_ascii=False)
    assert str(tmp_path) not in dumped
    assert "/private/" not in dumped


def test_build_operator_review_queue_marks_ready_when_all_prefights_ready(
    tmp_path: Path,
) -> None:
    """Verify queues become ready only when all preflights are ready."""
    input_paths = {
        "brand_preflight": _write_json(
            tmp_path / "brand.json",
            _brand_preflight(
                blank_decision_count=0,
                valid_decision_count=388,
                pending_operator_action_count=0,
                ready_for_requested_apply=True,
            ),
        ),
        "pii_preflight": _write_json(
            tmp_path / "pii.json",
            _pii_preflight(
                blank_decision_count=0,
                valid_decision_count=215,
                pending_operator_action_count=0,
                ready_for_requested_apply=True,
            ),
        ),
        "yolo_preflight": _write_json(
            tmp_path / "yolo.json",
            _yolo_preflight(
                blank_box_row_count=0,
                valid_accepted_row_count=205,
                pending_operator_action_count=0,
                ready_for_requested_promotion=True,
            ),
        ),
    }

    summary = queue_builder.build_operator_review_queue(input_paths=input_paths)

    assert summary["ready_queue_count"] == 3
    assert summary["pending_queue_count"] == 0
    assert summary["total_pending_operator_action_count"] == 0
    assert summary["ready_for_next_pipeline_step"] is True
    assert summary["next_queue_key"] is None


def test_build_operator_review_queue_rejects_unsafe_preflight_payload(tmp_path: Path) -> None:
    """Verify raw OCR fields are rejected before queue output."""
    paths = _input_paths(tmp_path)
    _write_json(
        paths["pii_preflight"],
        _pii_preflight(raw_ocr_text="visible sensitive text"),
    )

    try:
        queue_builder.build_operator_review_queue(input_paths=paths)
    except queue_builder.OperatorReviewQueueError as exc:
        assert "Unsafe raw" in str(exc)
    else:
        raise AssertionError("unsafe payload should fail closed")


def test_build_operator_review_queue_accepts_known_official_source_docs(
    tmp_path: Path,
) -> None:
    """Verify source docs from upstream preflights remain allow-listed."""
    paths = _input_paths(tmp_path)
    _write_json(
        paths["brand_preflight"],
        _brand_preflight(
            source_doc_urls=[
                "https://www.postgresql.org/docs/current/ddl-constraints.html",
                "https://supabase.com/docs/guides/database/postgres/row-level-security",
                "https://docs.sqlalchemy.org/en/21/orm/queryguide/select.html",
            ]
        ),
    )
    _write_json(
        paths["pii_preflight"],
        _pii_preflight(
            source_doc_urls=[
                "https://cloud.google.com/vision/docs/ocr",
                "https://api.ncloud-docs.com/docs/en/ai-application-service-ocr",
            ]
        ),
    )
    _write_json(
        paths["yolo_preflight"],
        _yolo_preflight(
            source_doc_urls=[
                "https://docs.ultralytics.com/datasets/detect/",
                "https://docs.ultralytics.com/tasks/detect/",
            ]
        ),
    )

    summary = queue_builder.build_operator_review_queue(input_paths=paths)

    assert summary["total_pending_operator_action_count"] == 808


def test_build_operator_review_queue_rejects_unknown_source_doc_url(
    tmp_path: Path,
) -> None:
    """Verify unapproved documentation URLs fail closed."""
    paths = _input_paths(tmp_path)
    _write_json(
        paths["brand_preflight"],
        _brand_preflight(source_doc_urls=["https://example.com/not-official"]),
    )

    try:
        queue_builder.build_operator_review_queue(input_paths=paths)
    except queue_builder.OperatorReviewQueueError as exc:
        assert "Unexpected source documentation URL" in str(exc)
    else:
        raise AssertionError("unknown source documentation URL should fail closed")


def test_build_operator_review_queue_markdown_is_redacted(tmp_path: Path) -> None:
    """Verify Markdown output hides paths and raw data."""
    summary = queue_builder.build_operator_review_queue(input_paths=_input_paths(tmp_path))

    markdown = queue_builder.build_operator_review_markdown(summary)

    assert "brand_product_review" in markdown
    assert "complete_operator_brand_review" in markdown
    assert str(tmp_path) not in markdown
    assert "/private/" not in markdown
    assert "raw_ocr_text" not in markdown


def test_operator_review_queue_cli_writes_json_and_markdown(
    tmp_path: Path,
    capsys: Any,
) -> None:
    """Verify CLI writes queue artifacts and prints a compact redacted summary."""
    paths = _input_paths(tmp_path)
    output_path = tmp_path / "out" / "queue.json"
    markdown_path = tmp_path / "out" / "queue.md"

    queue_builder.main(
        [
            "--brand-preflight",
            str(paths["brand_preflight"]),
            "--pii-preflight",
            str(paths["pii_preflight"]),
            "--yolo-preflight",
            str(paths["yolo_preflight"]),
            "--readiness",
            str(paths["readiness"]),
            "--output",
            str(output_path),
            "--markdown-output",
            str(markdown_path),
        ]
    )

    captured = capsys.readouterr().out
    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert summary["schema_version"] == "supplement-operator-review-queue-summary-v1"
    assert markdown_path.is_file()
    assert '"total_pending_operator_action_count": 808' in captured
    assert str(tmp_path) not in captured
