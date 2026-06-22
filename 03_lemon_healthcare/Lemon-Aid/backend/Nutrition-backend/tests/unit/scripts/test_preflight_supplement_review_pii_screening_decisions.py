"""Tests for supplement review-image PII decision preflight."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

candidate_builder = importlib.import_module("scripts.build_supplement_learning_candidate_manifests")
applier = importlib.import_module("scripts.apply_supplement_review_pii_screening_decisions")
preflight = importlib.import_module("scripts.preflight_supplement_review_pii_screening_decisions")


def _touch_image(path: Path, content: bytes = b"review-image") -> None:
    """Create an image-like fixture file.

    Args:
        path: Target path.
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
    """Build pending review OCR candidate rows.

    Args:
        tmp_path: Temporary directory.
        count: Number of candidate rows.

    Returns:
        Candidate rows.
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
    """Return a valid decision row.

    Args:
        fixture_id: Candidate fixture id.
        decision: Operator decision value.
        overrides: Extra decision fields.

    Returns:
        Decision row.
    """
    payload: dict[str, Any] = {
        "decision": decision,
        "reviewer_id": "operator_1",
        "reviewed_at": "2026-06-03T12:00:00+09:00",
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
        "schema_version": applier.DECISION_SCHEMA_VERSION,
        "fixture_id": fixture_id,
        "pii_screening_decision": payload,
    }


def _blank_decision_row(fixture_id: str) -> dict[str, Any]:
    """Return the untouched review bundle decision stub.

    Args:
        fixture_id: Candidate fixture id.

    Returns:
        Blank decision row.
    """
    return {
        "schema_version": applier.DECISION_SCHEMA_VERSION,
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


def test_preflight_reports_blank_stubs_as_pending_operator_work(tmp_path: Path) -> None:
    """Verify untouched bundle rows are not considered apply-ready."""
    candidates = _candidate_rows(tmp_path, count=2)
    candidate_manifest = tmp_path / "candidates.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(candidate_manifest, candidates)
    _write_jsonl(
        decisions_path,
        [_blank_decision_row(str(row["fixture_id"])) for row in candidates],
    )

    summary = preflight.preflight_pii_screening_decisions(
        candidate_manifest=candidate_manifest,
        decisions_path=decisions_path,
        require_all_reviewed=True,
    )

    assert summary["blank_decision_count"] == 2
    assert summary["valid_decision_count"] == 0
    assert summary["ready_for_partial_apply"] is False
    assert summary["ready_for_strict_apply"] is False
    assert summary["next_operator_action"] == "complete_operator_pii_review"


def test_preflight_allows_valid_partial_apply_without_auto_clearing_missing(
    tmp_path: Path,
) -> None:
    """Verify partial apply readiness still reports missing candidate decisions."""
    candidates = _candidate_rows(tmp_path, count=2)
    candidate_manifest = tmp_path / "candidates.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(candidate_manifest, candidates)
    _write_jsonl(decisions_path, [_decision_row(str(candidates[0]["fixture_id"]))])

    summary = preflight.preflight_pii_screening_decisions(
        candidate_manifest=candidate_manifest,
        decisions_path=decisions_path,
    )

    assert summary["valid_decision_count"] == 1
    assert summary["cleared_no_personal_data_count"] == 1
    assert summary["missing_decision_count"] == 1
    assert summary["ready_for_partial_apply"] is True
    assert summary["ready_for_strict_apply"] is False
    assert summary["ready_for_requested_apply"] is True


def test_preflight_requires_all_reviewed_when_strict(tmp_path: Path) -> None:
    """Verify strict preflight blocks partial decision sets."""
    candidates = _candidate_rows(tmp_path, count=2)
    candidate_manifest = tmp_path / "candidates.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(candidate_manifest, candidates)
    _write_jsonl(decisions_path, [_decision_row(str(candidates[0]["fixture_id"]))])

    summary = preflight.preflight_pii_screening_decisions(
        candidate_manifest=candidate_manifest,
        decisions_path=decisions_path,
        require_all_reviewed=True,
    )

    assert summary["ready_for_partial_apply"] is True
    assert summary["ready_for_requested_apply"] is False
    assert summary["next_operator_action"] == "complete_operator_pii_review"


def test_preflight_counts_blocking_and_invalid_decisions(tmp_path: Path) -> None:
    """Verify safe aggregate invalid counts without raw decision leakage."""
    candidates = _candidate_rows(tmp_path, count=3)
    candidate_manifest = tmp_path / "candidates.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(candidate_manifest, candidates)
    _write_jsonl(
        decisions_path,
        [
            _decision_row(str(candidates[0]["fixture_id"]), decision="contains_personal_data"),
            _decision_row(
                str(candidates[1]["fixture_id"]),
                attest_no_personal_data_visible=False,
            ),
            _decision_row("review-ocr-gt-unmatched"),
        ],
    )

    summary = preflight.preflight_pii_screening_decisions(
        candidate_manifest=candidate_manifest,
        decisions_path=decisions_path,
    )

    assert summary["blocked_decision_count"] == 1
    assert summary["invalid_decision_count"] == 1
    assert summary["unmatched_decision_count"] == 1
    assert summary["invalid_reason_counts"] == {"missing_required_attestation": 1}
    assert summary["ready_for_requested_apply"] is False
    assert summary["next_operator_action"] == "fix_invalid_pii_decision_rows"
    dumped = json.dumps(summary, ensure_ascii=False)
    assert "나우푸드 오메가3_123456" not in dumped
    assert str(tmp_path) not in dumped


def test_preflight_rejects_unsafe_decision_payload_as_aggregate_error(
    tmp_path: Path,
) -> None:
    """Verify unsafe raw fields are counted and not printed."""
    candidates = _candidate_rows(tmp_path)
    candidate_manifest = tmp_path / "candidates.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(candidate_manifest, candidates)
    _write_jsonl(
        decisions_path,
        [
            _decision_row(
                str(candidates[0]["fixture_id"]),
                raw_ocr_text="visible sensitive text",
            )
        ],
    )

    summary = preflight.preflight_pii_screening_decisions(
        candidate_manifest=candidate_manifest,
        decisions_path=decisions_path,
    )

    assert summary["invalid_decision_count"] == 1
    assert summary["invalid_reason_counts"] == {"unsafe_raw_field": 1}
    dumped = json.dumps(summary, ensure_ascii=False)
    assert "visible sensitive text" not in dumped
    assert '"raw_ocr_text":' not in dumped


def test_preflight_cli_writes_redacted_summary(
    tmp_path: Path,
    capsys: Any,
) -> None:
    """Verify CLI output is redacted and side-effect free."""
    candidates = _candidate_rows(tmp_path)
    candidate_manifest = tmp_path / "candidates.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    output_path = tmp_path / "out" / "preflight.json"
    _write_jsonl(candidate_manifest, candidates)
    _write_jsonl(decisions_path, [_blank_decision_row(str(candidates[0]["fixture_id"]))])

    preflight.main(
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
    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert json.loads(printed)["schema_version"] == preflight.SCHEMA_VERSION
    assert summary["db_write_performed"] is False
    assert summary["ocr_provider_call_performed"] is False
    assert summary["source_image_read_performed"] is False
    assert str(tmp_path) not in printed
    assert str(tmp_path) not in json.dumps(summary, ensure_ascii=False)
