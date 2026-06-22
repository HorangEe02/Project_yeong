"""Tests for supplement review-image PII decision application."""

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
applier = importlib.import_module("scripts.apply_supplement_review_pii_screening_decisions")


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


def test_apply_decisions_unlocks_only_attested_no_pii_candidates(tmp_path: Path) -> None:
    """Verify cleared rows become teacher OCR eligible."""
    candidates = _candidate_rows(tmp_path)
    candidate_manifest = tmp_path / "candidates.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(candidate_manifest, candidates)
    _write_jsonl(decisions_path, [_decision_row(str(candidates[0]["fixture_id"]))])

    rows, summary = applier.apply_pii_screening_decisions(
        candidate_manifest=candidate_manifest,
        decisions_path=decisions_path,
    )

    assert len(rows) == 1
    assert summary["cleared_row_count"] == 1
    assert summary["external_transfer_allowed_rows"] == 1
    assert summary["teacher_ocr_allowed_rows"] == 1
    assert rows[0]["schema_version"] == candidate_builder.OCR_ROW_SCHEMA_VERSION
    assert rows[0]["contains_personal_data"] is False
    assert rows[0]["pii_screening_status"] == "operator_cleared_no_personal_data"
    assert rows[0]["ground_truth_status"] == "pending_manual_transcription"
    assert rows[0]["external_transfer_allowed"] is True
    assert rows[0]["teacher_ocr_allowed"] is True
    assert rows[0]["pii_screening"]["reviewer_id"] == "operator_1"
    serialized = json.dumps({"rows": rows, "summary": summary}, ensure_ascii=False)
    assert "나우푸드 오메가3_123456" not in serialized
    assert str(tmp_path) not in serialized
    assert "/Volumes/" not in serialized
    assert '"raw_ocr_text"' not in serialized
    assert '"provider_payload"' not in serialized


def test_apply_decisions_keeps_pending_rows_blocked(tmp_path: Path) -> None:
    """Verify rows without decisions stay local-only and transfer-blocked."""
    candidates = _candidate_rows(tmp_path, count=2)
    candidate_manifest = tmp_path / "candidates.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(candidate_manifest, candidates)
    _write_jsonl(decisions_path, [_decision_row(str(candidates[0]["fixture_id"]))])

    rows, summary = applier.apply_pii_screening_decisions(
        candidate_manifest=candidate_manifest,
        decisions_path=decisions_path,
    )

    assert len(rows) == 2
    assert summary["pending_count"] == 1
    assert summary["decision_counts"] == {"cleared_no_personal_data": 1, "pending": 1}
    blocked = next(row for row in rows if row["fixture_id"] == candidates[1]["fixture_id"])
    assert blocked["contains_personal_data"] is None
    assert blocked["external_transfer_allowed"] is False
    assert blocked["teacher_ocr_allowed"] is False
    assert blocked["ground_truth_status"] == "pending_pii_screening"


def test_apply_decisions_skips_personal_data_rows(tmp_path: Path) -> None:
    """Verify non-cleared decisions are not exported to teacher OCR flow."""
    candidates = _candidate_rows(tmp_path)
    candidate_manifest = tmp_path / "candidates.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(candidate_manifest, candidates)
    _write_jsonl(
        decisions_path,
        [_decision_row(str(candidates[0]["fixture_id"]), decision="contains_personal_data")],
    )

    rows, summary = applier.apply_pii_screening_decisions(
        candidate_manifest=candidate_manifest,
        decisions_path=decisions_path,
    )

    assert rows == []
    assert summary["cleared_row_count"] == 0
    assert summary["skip_reason_counts"] == {"contains_personal_data_blocked": 1}
    assert summary["external_transfer_allowed_rows"] == 0


def test_apply_decisions_rejects_duplicate_and_unmatched_decisions(tmp_path: Path) -> None:
    """Verify stale or duplicated decision files fail closed."""
    candidates = _candidate_rows(tmp_path)
    candidate_manifest = tmp_path / "candidates.jsonl"
    _write_jsonl(candidate_manifest, candidates)

    duplicate_path = tmp_path / "duplicate.jsonl"
    _write_jsonl(
        duplicate_path,
        [
            _decision_row(str(candidates[0]["fixture_id"])),
            _decision_row(str(candidates[0]["fixture_id"])),
        ],
    )
    with pytest.raises(ValueError, match="Duplicate supplement PII decision"):
        applier.apply_pii_screening_decisions(
            candidate_manifest=candidate_manifest,
            decisions_path=duplicate_path,
        )

    unmatched_path = tmp_path / "unmatched.jsonl"
    _write_jsonl(unmatched_path, [_decision_row("review-ocr-gt-unmatched")])
    with pytest.raises(ValueError, match="not in candidate manifest"):
        applier.apply_pii_screening_decisions(
            candidate_manifest=candidate_manifest,
            decisions_path=unmatched_path,
        )


def test_apply_decisions_rejects_cleared_without_attestations(tmp_path: Path) -> None:
    """Verify a cleared row requires every no-PII attestation."""
    candidates = _candidate_rows(tmp_path)
    candidate_manifest = tmp_path / "candidates.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(candidate_manifest, candidates)
    _write_jsonl(
        decisions_path,
        [
            _decision_row(
                str(candidates[0]["fixture_id"]),
                attest_no_personal_data_visible=False,
            )
        ],
    )

    with pytest.raises(ValueError, match="attest_no_personal_data_visible"):
        applier.apply_pii_screening_decisions(
            candidate_manifest=candidate_manifest,
            decisions_path=decisions_path,
        )


def test_apply_decisions_rejects_unsafe_decision_payloads(tmp_path: Path) -> None:
    """Verify raw fields, paths, notes, URLs, and non-operator ids are rejected."""
    candidates = _candidate_rows(tmp_path)
    candidate_manifest = tmp_path / "candidates.jsonl"
    _write_jsonl(candidate_manifest, candidates)
    fixture_id = str(candidates[0]["fixture_id"])
    unsafe_cases = [
        (_decision_row(fixture_id, raw_ocr_text="secret"), "raw_ocr_text"),
        (_decision_row(fixture_id, review_note="free text"), "free-text"),
        (_decision_row(fixture_id, reviewer_id="ollama_gemma4"), "operator_ prefix"),
        (_decision_row(fixture_id, reviewer_id="/Volumes/Corsair/user"), "local path"),
        (_decision_row(fixture_id, object_url="https://example.test/image.jpg"), "object_url"),
        (_decision_row(fixture_id, extracted_name="홍길동"), "unsupported field"),
    ]
    for index, (payload, match) in enumerate(unsafe_cases):
        decisions_path = tmp_path / f"unsafe-{index}.jsonl"
        _write_jsonl(decisions_path, [payload])
        with pytest.raises(ValueError, match=match):
            applier.apply_pii_screening_decisions(
                candidate_manifest=candidate_manifest,
                decisions_path=decisions_path,
            )


def test_apply_decisions_requires_every_row_when_strict(tmp_path: Path) -> None:
    """Verify strict mode fails if any candidate remains pending."""
    candidates = _candidate_rows(tmp_path)
    candidate_manifest = tmp_path / "candidates.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(candidate_manifest, candidates)
    _write_jsonl(decisions_path, [])

    with pytest.raises(ValueError, match="every supplement review candidate"):
        applier.apply_pii_screening_decisions(
            candidate_manifest=candidate_manifest,
            decisions_path=decisions_path,
            require_all_reviewed=True,
        )


def test_main_writes_rows_and_redacted_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI writes updated candidate rows and a safe summary."""
    candidates = _candidate_rows(tmp_path)
    candidate_manifest = tmp_path / "candidates.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    output_path = tmp_path / "out" / "pii-applied.jsonl"
    summary_path = tmp_path / "out" / "summary.json"
    _write_jsonl(candidate_manifest, candidates)
    _write_jsonl(decisions_path, [_decision_row(str(candidates[0]["fixture_id"]))])

    applier.main(
        [
            "--candidate-manifest",
            str(candidate_manifest),
            "--decisions",
            str(decisions_path),
            "--output",
            str(output_path),
            "--summary",
            str(summary_path),
        ]
    )

    printed = capsys.readouterr().out
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert json.loads(printed)["cleared_row_count"] == 1
    assert summary["db_write_performed"] is False
    assert summary["ocr_provider_call_performed"] is False
    assert summary["local_path_literals_stored"] is False
    assert rows[0]["external_transfer_allowed"] is True
    assert str(tmp_path) not in printed
    assert str(tmp_path) not in json.dumps(summary, ensure_ascii=False)
