"""Tests for extracting reviewed supplement PII screening decisions."""

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

candidate_builder = importlib.import_module("scripts.build_supplement_learning_candidate_manifests")
extract = importlib.import_module("scripts.extract_supplement_pii_reviewed_decisions")


def _touch_image(path: Path, content: bytes = b"review-image") -> None:
    """Create an image-like file fixture.

    Args:
        path: Target image path.
        content: File bytes.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write JSONL rows.

    Args:
        path: Destination path.
        rows: Rows to write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _candidate_rows(tmp_path: Path, *, count: int = 1) -> list[dict[str, Any]]:
    """Build pending supplement review OCR candidate rows.

    Args:
        tmp_path: Test temp directory.
        count: Number of review images in the same category.

    Returns:
        Pending OCR candidate rows.
    """
    root = tmp_path / "crawling-image"
    for index in range(count):
        _touch_image(
            root / "[오메가3]" / "나우푸드 오메가3_123456" / "리뷰" / f"review-{index}.jpg",
            f"review-image-{index}".encode(),
        )
    rows, _, _ = candidate_builder.build_learning_candidate_manifests(
        root=root,
        max_review_per_category=count,
        max_detail_per_category=0,
    )
    return rows


def _decision_row(
    fixture_id: str,
    decision: str = "cleared_no_personal_data",
    **overrides: Any,
) -> dict[str, Any]:
    """Return one supplement PII screening decision row.

    Args:
        fixture_id: Candidate fixture id.
        decision: Operator decision.
        overrides: Additional decision payload fields.

    Returns:
        Decision JSON object.
    """
    payload: dict[str, Any] = {
        "decision": decision,
        "reviewer_id": "operator_1",
        "reviewed_at": "2026-06-04T12:00:00Z",
    }
    if decision == "cleared_no_personal_data":
        payload.update(
            {
                "reason_codes": ["no_personal_data_visible"],
                "attest_local_screening_completed": True,
                "attest_no_personal_data_visible": True,
                "attest_no_raw_text_copied": True,
                "attest_teacher_ocr_transfer_allowed": True,
            }
        )
    else:
        payload["reason_codes"] = ["face_visible"]
    payload.update(overrides)
    return {
        "schema_version": extract.applier.DECISION_SCHEMA_VERSION,
        "fixture_id": fixture_id,
        "pii_screening_decision": payload,
    }


def _blank_decision_row(fixture_id: str) -> dict[str, Any]:
    """Return an untouched PII decision stub.

    Args:
        fixture_id: Candidate fixture id.

    Returns:
        Blank decision row.
    """
    return {
        "schema_version": extract.applier.DECISION_SCHEMA_VERSION,
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


def test_extract_reviewed_pii_decisions_ignores_blank_stubs(tmp_path: Path) -> None:
    """Verify reviewed-only extraction can consume mixed queue files."""
    candidates = _candidate_rows(tmp_path, count=2)
    candidate_manifest = tmp_path / "candidates.jsonl"
    decisions_path = tmp_path / "pii.queue.jsonl"
    _write_jsonl(candidate_manifest, candidates)
    _write_jsonl(
        decisions_path,
        [
            _decision_row(str(candidates[0]["fixture_id"])),
            _blank_decision_row(str(candidates[1]["fixture_id"])),
        ],
    )

    extracted_rows, summary = extract.extract_reviewed_pii_decisions(
        candidate_manifest=candidate_manifest,
        decisions_path=decisions_path,
    )

    assert len(extracted_rows) == 1
    assert extracted_rows[0]["fixture_id"] == candidates[0]["fixture_id"]
    assert summary["input_decision_row_count"] == 2
    assert summary["reviewed_decision_count"] == 1
    assert summary["cleared_no_personal_data_count"] == 1
    assert summary["blank_decision_ignored_count"] == 1
    assert summary["decision_counts"] == {"blank": 1, "cleared_no_personal_data": 1}
    assert summary["ready_for_partial_apply"] is True
    assert summary["ready_for_strict_apply"] is False
    assert summary["db_write_performed"] is False


def test_extract_reviewed_pii_decisions_all_blank_is_controlled_noop(
    tmp_path: Path,
) -> None:
    """Verify all-blank queues create an empty reviewed-only file."""
    candidates = _candidate_rows(tmp_path, count=2)
    candidate_manifest = tmp_path / "candidates.jsonl"
    decisions_path = tmp_path / "pii.queue.jsonl"
    _write_jsonl(candidate_manifest, candidates)
    _write_jsonl(
        decisions_path,
        [_blank_decision_row(str(row["fixture_id"])) for row in candidates],
    )

    extracted_rows, summary = extract.extract_reviewed_pii_decisions(
        candidate_manifest=candidate_manifest,
        decisions_path=decisions_path,
    )

    assert extracted_rows == []
    assert summary["reviewed_decision_count"] == 0
    assert summary["blank_decision_ignored_count"] == 2
    assert summary["ready_for_partial_apply"] is False
    assert summary["output_rows_written"] == 0


def test_extract_reviewed_pii_decisions_keeps_blocking_decisions_as_reviewed(
    tmp_path: Path,
) -> None:
    """Verify personal-data decisions stay reviewed but not teacher-OCR cleared."""
    candidates = _candidate_rows(tmp_path)
    candidate_manifest = tmp_path / "candidates.jsonl"
    decisions_path = tmp_path / "pii.queue.jsonl"
    _write_jsonl(candidate_manifest, candidates)
    _write_jsonl(
        decisions_path,
        [_decision_row(str(candidates[0]["fixture_id"]), decision="contains_personal_data")],
    )

    extracted_rows, summary = extract.extract_reviewed_pii_decisions(
        candidate_manifest=candidate_manifest,
        decisions_path=decisions_path,
    )

    assert len(extracted_rows) == 1
    assert summary["reviewed_decision_count"] == 1
    assert summary["cleared_no_personal_data_count"] == 0
    assert summary["blocked_decision_count"] == 1
    assert summary["decision_counts"] == {"contains_personal_data": 1}


def test_extract_reviewed_pii_decisions_rejects_nonblank_invalid_row(
    tmp_path: Path,
) -> None:
    """Verify malformed reviewed rows fail closed instead of being ignored."""
    candidates = _candidate_rows(tmp_path)
    candidate_manifest = tmp_path / "candidates.jsonl"
    decisions_path = tmp_path / "pii.queue.jsonl"
    _write_jsonl(candidate_manifest, candidates)
    invalid = _decision_row(
        str(candidates[0]["fixture_id"]),
        attest_no_personal_data_visible=False,
    )
    _write_jsonl(decisions_path, [invalid])

    with pytest.raises(ValueError, match="attest_no_personal_data_visible"):
        extract.extract_reviewed_pii_decisions(
            candidate_manifest=candidate_manifest,
            decisions_path=decisions_path,
        )


def test_extract_reviewed_pii_decisions_rejects_unmatched_row(tmp_path: Path) -> None:
    """Verify stale reviewed rows cannot be copied into partial apply input."""
    candidates = _candidate_rows(tmp_path)
    candidate_manifest = tmp_path / "candidates.jsonl"
    decisions_path = tmp_path / "pii.queue.jsonl"
    _write_jsonl(candidate_manifest, candidates)
    _write_jsonl(decisions_path, [_decision_row("review-ocr-gt-unmatched")])

    with pytest.raises(ValueError, match="not in candidate manifest"):
        extract.extract_reviewed_pii_decisions(
            candidate_manifest=candidate_manifest,
            decisions_path=decisions_path,
        )


def test_extract_reviewed_pii_decisions_cli_writes_redacted_outputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI output stays aggregate-only and path-redacted."""
    candidates = _candidate_rows(tmp_path, count=2)
    candidate_manifest = tmp_path / "candidates.jsonl"
    decisions_path = tmp_path / "pii.queue.jsonl"
    output_path = tmp_path / "out" / "reviewed.jsonl"
    _write_jsonl(candidate_manifest, candidates)
    _write_jsonl(
        decisions_path,
        [
            _decision_row(str(candidates[0]["fixture_id"])),
            _blank_decision_row(str(candidates[1]["fixture_id"])),
        ],
    )

    extract.main(
        [
            "--candidate-manifest",
            str(candidate_manifest),
            "--decisions",
            str(decisions_path),
            "--output",
            str(output_path),
        ]
    )

    printed = capsys.readouterr().out
    summary = json.loads(output_path.with_suffix(".jsonl.summary.json").read_text(encoding="utf-8"))
    assert output_path.exists()
    assert summary["reviewed_decision_count"] == 1
    assert str(tmp_path) not in printed
    assert str(tmp_path) not in json.dumps(summary, ensure_ascii=False)
    assert "나우푸드 오메가3_123456" not in printed
