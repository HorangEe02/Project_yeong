"""Tests for Naver Tampermonkey review-readiness summaries."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import summarize_naver_tampermonkey_review_readiness as readiness


def _write_json(path: Path, value: dict[str, object]) -> None:
    """Write one JSON object."""
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _paths(tmp_path: Path) -> dict[str, Path]:
    """Return summary paths used by readiness tests."""
    return {
        "evaluation": tmp_path / "evaluation.json",
        "review_ingest": tmp_path / "review-ingest.summary.json",
        "gap_queue": tmp_path / "gap-queue.summary.json",
        "gap_template": tmp_path / "gap-template.summary.json",
        "review_import_gate": tmp_path / "gate.summary.json",
    }


def _write_pending_gap_summaries(tmp_path: Path) -> dict[str, Path]:
    """Write matching summaries for a pending manual-review gap state."""
    paths = _paths(tmp_path)
    _write_json(
        paths["evaluation"],
        {
            "fixture_count": 120,
            "observation_count": 120,
            "providers": {
                "paddleocr_local": {
                    "completed_count": 119,
                    "error_count": 1,
                }
            },
            "raw_artifacts_stored": False,
            "raw_ocr_text_stored": False,
            "raw_provider_payload_stored": False,
            "raw_model_response_stored": False,
            "local_path_literals_stored": False,
        },
    )
    _write_json(
        paths["review_ingest"],
        {
            "row_count": 120,
            "review_required_rows": 120,
            "db_import_ready_rows": 0,
            "raw_artifacts_stored": False,
            "raw_ocr_text_stored": False,
            "raw_provider_payload_stored": False,
            "raw_model_response_stored": False,
            "local_path_literals_stored": False,
            "clinical_recommendations_stored": False,
        },
    )
    _write_json(
        paths["gap_queue"],
        {
            "input_row_count": 120,
            "gap_row_count": 6,
            "raw_artifacts_stored": False,
            "raw_ocr_text_stored": False,
            "raw_provider_payload_stored": False,
            "raw_model_response_stored": False,
            "local_path_literals_stored": False,
            "clinical_recommendations_stored": False,
            "db_write_performed": False,
        },
    )
    _write_json(
        paths["gap_template"],
        {
            "row_count": 6,
            "decision_batch_importable": False,
            "raw_artifacts_stored": False,
            "raw_ocr_text_stored": False,
            "raw_provider_payload_stored": False,
            "raw_model_response_stored": False,
            "local_path_literals_stored": False,
            "clinical_recommendations_stored": False,
        },
    )
    _write_json(
        paths["review_import_gate"],
        {
            "gap_pending_count": 6,
            "approved_row_count": 0,
            "planned_product_upsert_count": 0,
            "db_write_performed": False,
            "raw_artifacts_stored": False,
            "raw_ocr_text_stored": False,
            "raw_provider_payload_stored": False,
            "raw_model_response_stored": False,
            "local_path_literals_stored": False,
            "clinical_recommendations_stored": False,
        },
    )
    return paths


def test_summarize_review_readiness_reports_pending_gap(tmp_path: Path) -> None:
    """Verify current EX400U-style pending gaps are not DB import ready."""
    paths = _write_pending_gap_summaries(tmp_path)

    summary = readiness.summarize_review_readiness(input_paths=paths)

    assert summary["fixture_count"] == 120
    assert summary["observation_count"] == 120
    assert summary["provider_id"] == "paddleocr_local"
    assert summary["provider_error_count"] == 1
    assert summary["gap_row_count"] == 6
    assert summary["gap_pending_count"] == 6
    assert summary["ready_for_db_import"] is False
    assert summary["human_review_required"] is True
    assert summary["blocking_reasons"] == [
        "manual_gap_review_pending",
        "no_approved_import_rows",
        "ocr_provider_errors_present",
        "review_rows_not_db_import_ready",
    ]
    assert summary["privacy_failed_flags"] == []
    serialized = json.dumps(summary, ensure_ascii=False).lower()
    assert '"raw_ocr_text"' not in serialized
    assert "/private/" not in serialized


def test_summarize_review_readiness_can_pass_ready_state(tmp_path: Path) -> None:
    """Verify a fully approved and dry-run-matched state can be ready."""
    paths = _write_pending_gap_summaries(tmp_path)
    _write_json(
        paths["evaluation"],
        {
            "fixture_count": 1,
            "observation_count": 1,
            "providers": {"paddleocr_local": {"completed_count": 1, "error_count": 0}},
            "raw_artifacts_stored": False,
            "raw_ocr_text_stored": False,
            "raw_provider_payload_stored": False,
            "raw_model_response_stored": False,
            "local_path_literals_stored": False,
        },
    )
    _write_json(
        paths["review_ingest"],
        {
            "row_count": 1,
            "review_required_rows": 1,
            "db_import_ready_rows": 1,
            "raw_artifacts_stored": False,
            "raw_ocr_text_stored": False,
            "raw_provider_payload_stored": False,
            "raw_model_response_stored": False,
            "local_path_literals_stored": False,
            "clinical_recommendations_stored": False,
        },
    )
    _write_json(
        paths["gap_queue"],
        {
            "gap_row_count": 1,
            "raw_artifacts_stored": False,
            "raw_ocr_text_stored": False,
            "raw_provider_payload_stored": False,
            "raw_model_response_stored": False,
            "local_path_literals_stored": False,
            "clinical_recommendations_stored": False,
            "db_write_performed": False,
        },
    )
    _write_json(
        paths["gap_template"],
        {
            "row_count": 1,
            "raw_artifacts_stored": False,
            "raw_ocr_text_stored": False,
            "raw_provider_payload_stored": False,
            "raw_model_response_stored": False,
            "local_path_literals_stored": False,
            "clinical_recommendations_stored": False,
        },
    )
    _write_json(
        paths["review_import_gate"],
        {
            "gap_pending_count": 0,
            "approved_row_count": 1,
            "planned_product_upsert_count": 1,
            "db_write_performed": False,
            "raw_artifacts_stored": False,
            "raw_ocr_text_stored": False,
            "raw_provider_payload_stored": False,
            "raw_model_response_stored": False,
            "local_path_literals_stored": False,
            "clinical_recommendations_stored": False,
        },
    )

    summary = readiness.summarize_review_readiness(input_paths=paths)

    assert summary["ready_for_db_import"] is True
    assert summary["human_review_required"] is False
    assert summary["blocking_reasons"] == []


def test_summarize_review_readiness_rejects_unsafe_inputs(tmp_path: Path) -> None:
    """Verify raw keys and local paths cannot shape readiness summaries."""
    paths = _write_pending_gap_summaries(tmp_path)
    _write_json(paths["review_ingest"], {"raw_ocr_text": "forbidden"})

    with pytest.raises(ValueError, match="raw_ocr_text"):
        readiness.summarize_review_readiness(input_paths=paths)

    _write_json(paths["review_ingest"], {"source": "/Volumes/Corsair EX400U Media/a.jpg"})
    with pytest.raises(ValueError, match="local path literal"):
        readiness.summarize_review_readiness(input_paths=paths)


def test_summarize_review_readiness_main_error_is_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI failures print redacted JSON without traceback paths."""
    paths = _paths(tmp_path)
    output_path = tmp_path / "readiness.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "summarize_naver_tampermonkey_review_readiness.py",
            "--evaluation-summary",
            str(paths["evaluation"]),
            "--review-ingest-summary",
            str(paths["review_ingest"]),
            "--gap-queue-summary",
            str(paths["gap_queue"]),
            "--gap-template-summary",
            str(paths["gap_template"]),
            "--gate-summary",
            str(paths["review_import_gate"]),
            "--output",
            str(output_path),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        readiness.main()

    assert exc_info.value.code == 1
    stdout = capsys.readouterr().out
    summary = json.loads(stdout)
    assert summary["status"] == "error"
    assert summary["error_message"] == "Local file operation failed."
    assert str(tmp_path) not in stdout
    assert "/private/" not in stdout
