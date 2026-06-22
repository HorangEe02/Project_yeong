"""Tests for supplement OCR benchmark readiness gate reports."""

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

gate = importlib.import_module("scripts.gate_supplement_ocr_benchmark")


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


def _pii_payload(
    *,
    ready: bool = False,
    cleared_count: int = 0,
    blocked_count: int = 0,
    blank_count: int = 215,
    pending_count: int = 215,
) -> dict[str, Any]:
    """Return a PII decision preflight fixture.

    Args:
        ready: Whether strict/requested apply flags are true.
        cleared_count: Rows cleared for teacher OCR transfer.
        blocked_count: Rows explicitly blocked by operator review.
        blank_count: Blank PII decision count.
        pending_count: Pending operator action count.

    Returns:
        PII preflight payload.
    """
    valid_count = cleared_count + blocked_count
    decision_counts = {"blank": blank_count} if blank_count else {}
    if cleared_count:
        decision_counts["cleared_no_personal_data"] = cleared_count
    if blocked_count:
        decision_counts["blocked"] = blocked_count
    return {
        "schema_version": "supplement-review-pii-screening-decision-preflight-v1",
        "candidate_row_count": 215,
        "decision_row_count": 215,
        "valid_decision_count": valid_count,
        "cleared_no_personal_data_count": cleared_count,
        "blocked_decision_count": blocked_count,
        "blank_decision_count": blank_count,
        "invalid_decision_count": 0,
        "unmatched_decision_count": 0,
        "missing_decision_count": 0,
        "pending_operator_action_count": pending_count,
        "decision_counts": decision_counts,
        "invalid_reason_counts": {},
        "require_all_reviewed": True,
        "ready_for_partial_apply": ready,
        "ready_for_strict_apply": ready,
        "ready_for_requested_apply": ready,
        "next_operator_action": (
            "run_pii_screening_apply" if ready else "complete_operator_pii_review"
        ),
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "source_image_read_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }


def _gt_payload(*, row_count: int, ready_count: int) -> dict[str, Any]:
    """Return a ground-truth review bundle summary fixture.

    Args:
        row_count: Ground-truth template row count.
        ready_count: Human-reviewed rows ready for benchmark.

    Returns:
        GT bundle summary payload.
    """
    return {
        "schema_version": "supplement-ocr-ground-truth-review-bundle-v1",
        "template_row_count": row_count,
        "reviewable_row_count": row_count,
        "ground_truth_template_row_count": row_count,
        "category_counts": {},
        "skip_reason_counts": {},
        "manual_review_required_count": max(row_count - ready_count, 0),
        "ready_for_benchmark_rows": ready_count,
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }


def _gt_preflight_payload(*, row_count: int, ready_count: int) -> dict[str, Any]:
    """Return a manual ground-truth benchmark preflight fixture.

    Args:
        row_count: Ground-truth row count.
        ready_count: Rows ready for benchmark build.

    Returns:
        Ground-truth preflight payload.
    """
    return {
        "schema_version": "supplement-ocr-ground-truth-preflight-v1",
        "status": "ready_for_benchmark_build" if ready_count else "blocked_by_no_ready_rows",
        "ready_for_benchmark_build": ready_count > 0,
        "row_count": row_count,
        "human_reviewed_row_count": ready_count,
        "explicit_ready_flag_count": ready_count,
        "benchmark_ready_row_count": ready_count,
        "min_ready_rows": 1,
        "required_expected_sections": [
            "ingredient_amounts",
            "intake_method",
            "precautions",
            "allergen_warnings",
        ],
        "issue_counts": {},
        "missing_required_section_counts": {},
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }


def _benchmark_payload(
    *,
    fixture_count: int,
    scoreable_count: int,
    required_expected_sections: list[str] | None = None,
) -> dict[str, Any]:
    """Return an OCR benchmark manifest summary fixture.

    Args:
        fixture_count: Benchmark fixture count.
        scoreable_count: Fixtures with human-reviewed expected ingredients.
        required_expected_sections: Section requirements declared by benchmark build.

    Returns:
        Benchmark summary payload.
    """
    sections = required_expected_sections or [
        "ingredient_amounts",
        "intake_method",
        "precautions",
        "allergen_warnings",
    ]
    return {
        "schema_version": "supplement-ocr-provider-benchmark-manifest-v1",
        "candidate_count": fixture_count,
        "ground_truth_decision_count": fixture_count,
        "benchmark_fixture_count": fixture_count,
        "skip_reason_counts": {},
        "required_expected_sections": sections,
        "missing_required_section_counts": {},
        "scoreable_fixture_count": scoreable_count,
        "image_materialization_requested": False,
        "image_materialized_count": 0,
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }


def _split_payload(
    *,
    row_count: int,
    holdout_count: int,
    test_count: int = 0,
    leakage_check_passed: bool = True,
) -> dict[str, Any]:
    """Return a product-group-safe split assignment summary fixture.

    Args:
        row_count: Split-assigned row count.
        holdout_count: Holdout fixture count.
        test_count: Test fixture count.
        leakage_check_passed: Whether product-group leakage checks passed.

    Returns:
        Split assignment summary payload.
    """
    train_count = max(row_count - holdout_count - test_count, 0)
    return {
        "schema_version": "paddleocr-benchmark-split-assignment-v1",
        "row_count": row_count,
        "product_group_count": row_count,
        "split_counts": {
            "train": train_count,
            "holdout": holdout_count,
            "test": test_count,
        },
        "product_group_split_counts": {
            "train": train_count,
            "holdout": holdout_count,
            "test": test_count,
        },
        "ready_for_holdout_eval": leakage_check_passed and holdout_count > 0,
        "leakage_check_passed": leakage_check_passed,
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "source_image_read_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }


def test_ocr_benchmark_gate_blocks_blank_pii_review(tmp_path: Path) -> None:
    """Verify blank PII review rows block OCR benchmark preparation."""
    pii_path = _write_json(tmp_path / "pii.json", _pii_payload())

    summary = gate.build_ocr_benchmark_gate(pii_preflight_path=pii_path)
    markdown = gate.build_markdown(summary)

    assert summary["schema_version"] == "supplement-ocr-benchmark-gate-v1"
    assert summary["status"] == "blocked_by_pii_screening"
    assert summary["strict_pii_review_requested"] is True
    assert summary["pii_ready_for_strict_apply"] is False
    assert summary["pii_blank_decision_count"] == 215
    assert summary["ground_truth_template_allowed"] is False
    assert summary["teacher_ocr_benchmark_allowed"] is False
    assert summary["external_teacher_ocr_eval_allowed"] is False
    assert summary["paddleocr_training_allowed_now"] is False
    assert "blocked_by_pii_screening" in markdown
    assert str(tmp_path) not in json.dumps(summary, ensure_ascii=False) + markdown


def test_ocr_benchmark_gate_blocks_when_no_teacher_safe_rows(tmp_path: Path) -> None:
    """Verify strict PII completion still blocks if no row is teacher-safe."""
    pii_path = _write_json(
        tmp_path / "pii.json",
        _pii_payload(
            ready=True, cleared_count=0, blocked_count=215, blank_count=0, pending_count=0
        ),
    )

    summary = gate.build_ocr_benchmark_gate(pii_preflight_path=pii_path)

    assert summary["status"] == "blocked_by_no_teacher_safe_rows"
    assert summary["pii_strict_clear"] is True
    assert summary["has_teacher_safe_rows"] is False
    assert summary["blocked_pii_decision_count"] == 215
    assert summary["ground_truth_template_allowed"] is False


def test_ocr_benchmark_gate_blocks_until_ground_truth_review_exists(tmp_path: Path) -> None:
    """Verify PII-cleared rows require human ground-truth review before benchmark."""
    pii_path = _write_json(
        tmp_path / "pii.json",
        _pii_payload(ready=True, cleared_count=3, blank_count=0, pending_count=0),
    )

    summary = gate.build_ocr_benchmark_gate(pii_preflight_path=pii_path)

    assert summary["status"] == "blocked_by_ground_truth_review"
    assert summary["ground_truth_template_allowed"] is True
    assert summary["ground_truth_review_ready"] is False
    assert summary["ready_for_benchmark_rows"] == 0


def test_ocr_benchmark_gate_blocks_zero_ready_ground_truth_rows(tmp_path: Path) -> None:
    """Verify unreviewed GT bundle summaries cannot become benchmarks."""
    pii_path = _write_json(
        tmp_path / "pii.json",
        _pii_payload(ready=True, cleared_count=3, blank_count=0, pending_count=0),
    )
    gt_path = _write_json(tmp_path / "gt-summary.json", _gt_payload(row_count=3, ready_count=0))

    summary = gate.build_ocr_benchmark_gate(
        pii_preflight_path=pii_path,
        ground_truth_bundle_summary_path=gt_path,
    )

    assert summary["status"] == "blocked_by_ground_truth_review"
    assert summary["manual_ground_truth_review_required_count"] == 3
    assert summary["ready_for_benchmark_rows"] == 0


def test_ocr_benchmark_gate_blocks_until_benchmark_manifest_exists(tmp_path: Path) -> None:
    """Verify human-reviewed GT still requires a benchmark manifest summary."""
    pii_path = _write_json(
        tmp_path / "pii.json",
        _pii_payload(ready=True, cleared_count=3, blank_count=0, pending_count=0),
    )
    gt_path = _write_json(tmp_path / "gt-summary.json", _gt_payload(row_count=3, ready_count=3))
    gt_preflight_path = _write_json(
        tmp_path / "gt-preflight.json",
        _gt_preflight_payload(row_count=3, ready_count=3),
    )

    summary = gate.build_ocr_benchmark_gate(
        pii_preflight_path=pii_path,
        ground_truth_bundle_summary_path=gt_path,
        ground_truth_preflight_path=gt_preflight_path,
    )

    assert summary["status"] == "blocked_by_benchmark_manifest"
    assert summary["ground_truth_review_ready"] is True
    assert summary["benchmark_manifest_ready"] is False
    assert summary["benchmark_fixture_count"] == 0


def test_ocr_benchmark_gate_blocks_until_ground_truth_preflight_exists(tmp_path: Path) -> None:
    """Verify reviewed GT needs a dedicated preflight before benchmark use."""
    pii_path = _write_json(
        tmp_path / "pii.json",
        _pii_payload(ready=True, cleared_count=3, blank_count=0, pending_count=0),
    )
    gt_path = _write_json(tmp_path / "gt-summary.json", _gt_payload(row_count=3, ready_count=3))
    benchmark_path = _write_json(
        tmp_path / "benchmark-summary.json",
        _benchmark_payload(fixture_count=3, scoreable_count=3),
    )

    summary = gate.build_ocr_benchmark_gate(
        pii_preflight_path=pii_path,
        ground_truth_bundle_summary_path=gt_path,
        benchmark_summary_path=benchmark_path,
    )

    assert summary["status"] == "blocked_by_ground_truth_review"
    assert summary["ground_truth_review_ready"] is True
    assert summary["ground_truth_preflight_ready"] is False
    assert summary["ground_truth_preflight_benchmark_ready_row_count"] == 0
    assert "run_ocr_ground_truth_preflight_require_all_sections" in summary["next_steps"]
    assert summary["teacher_ocr_benchmark_allowed"] is False


def test_ocr_benchmark_gate_blocks_failed_ground_truth_preflight(tmp_path: Path) -> None:
    """Verify a non-ready GT preflight cannot unlock teacher OCR comparison."""
    pii_path = _write_json(
        tmp_path / "pii.json",
        _pii_payload(ready=True, cleared_count=3, blank_count=0, pending_count=0),
    )
    gt_path = _write_json(tmp_path / "gt-summary.json", _gt_payload(row_count=3, ready_count=3))
    gt_preflight_path = _write_json(
        tmp_path / "gt-preflight.json",
        _gt_preflight_payload(row_count=3, ready_count=0),
    )
    benchmark_path = _write_json(
        tmp_path / "benchmark-summary.json",
        _benchmark_payload(fixture_count=3, scoreable_count=3),
    )

    summary = gate.build_ocr_benchmark_gate(
        pii_preflight_path=pii_path,
        ground_truth_bundle_summary_path=gt_path,
        ground_truth_preflight_path=gt_preflight_path,
        benchmark_summary_path=benchmark_path,
    )

    assert summary["status"] == "blocked_by_ground_truth_review"
    assert summary["ground_truth_review_ready"] is True
    assert summary["ground_truth_preflight_ready"] is False
    assert summary["ground_truth_preflight_row_count"] == 3
    assert summary["ground_truth_preflight_benchmark_ready_row_count"] == 0
    assert summary["teacher_ocr_benchmark_allowed"] is False


def test_ocr_benchmark_gate_blocks_until_split_assignment_exists(tmp_path: Path) -> None:
    """Verify benchmark fixtures still require leakage-safe split assignment."""
    pii_path = _write_json(
        tmp_path / "pii.json",
        _pii_payload(ready=True, cleared_count=3, blank_count=0, pending_count=0),
    )
    gt_path = _write_json(tmp_path / "gt-summary.json", _gt_payload(row_count=3, ready_count=3))
    gt_preflight_path = _write_json(
        tmp_path / "gt-preflight.json",
        _gt_preflight_payload(row_count=3, ready_count=3),
    )
    benchmark_path = _write_json(
        tmp_path / "benchmark-summary.json",
        _benchmark_payload(fixture_count=3, scoreable_count=3),
    )

    summary = gate.build_ocr_benchmark_gate(
        pii_preflight_path=pii_path,
        ground_truth_bundle_summary_path=gt_path,
        ground_truth_preflight_path=gt_preflight_path,
        benchmark_summary_path=benchmark_path,
    )

    assert summary["status"] == "blocked_by_benchmark_split_assignment"
    assert summary["benchmark_manifest_ready"] is True
    assert summary["benchmark_required_sections_ready"] is True
    assert summary["benchmark_split_ready"] is False
    assert summary["teacher_ocr_benchmark_allowed"] is False


def test_ocr_benchmark_gate_blocks_benchmark_missing_full_card_sections(tmp_path: Path) -> None:
    """Verify ingredient-only benchmarks cannot unlock full supplement OCR eval."""
    pii_path = _write_json(
        tmp_path / "pii.json",
        _pii_payload(ready=True, cleared_count=3, blank_count=0, pending_count=0),
    )
    gt_path = _write_json(tmp_path / "gt-summary.json", _gt_payload(row_count=3, ready_count=3))
    gt_preflight_path = _write_json(
        tmp_path / "gt-preflight.json",
        _gt_preflight_payload(row_count=3, ready_count=3),
    )
    benchmark_path = _write_json(
        tmp_path / "benchmark-summary.json",
        _benchmark_payload(
            fixture_count=3,
            scoreable_count=3,
            required_expected_sections=["ingredient_amounts"],
        ),
    )
    split_path = _write_json(
        tmp_path / "split-summary.json",
        _split_payload(row_count=3, holdout_count=1),
    )

    summary = gate.build_ocr_benchmark_gate(
        pii_preflight_path=pii_path,
        ground_truth_bundle_summary_path=gt_path,
        ground_truth_preflight_path=gt_preflight_path,
        benchmark_summary_path=benchmark_path,
        benchmark_split_summary_path=split_path,
    )

    assert summary["status"] == "blocked_by_benchmark_manifest"
    assert summary["benchmark_manifest_ready"] is False
    assert summary["benchmark_required_sections_ready"] is False
    assert summary["benchmark_required_expected_sections"] == ["ingredient_amounts"]
    assert summary["benchmark_missing_required_expected_sections"] == [
        "intake_method",
        "precautions",
        "allergen_warnings",
    ]
    assert summary["teacher_ocr_benchmark_allowed"] is False


def test_ocr_benchmark_gate_blocks_failed_split_leakage_check(tmp_path: Path) -> None:
    """Verify split leakage failure blocks teacher OCR eval."""
    pii_path = _write_json(
        tmp_path / "pii.json",
        _pii_payload(ready=True, cleared_count=3, blank_count=0, pending_count=0),
    )
    gt_path = _write_json(tmp_path / "gt-summary.json", _gt_payload(row_count=3, ready_count=3))
    gt_preflight_path = _write_json(
        tmp_path / "gt-preflight.json",
        _gt_preflight_payload(row_count=3, ready_count=3),
    )
    benchmark_path = _write_json(
        tmp_path / "benchmark-summary.json",
        _benchmark_payload(fixture_count=3, scoreable_count=3),
    )
    split_path = _write_json(
        tmp_path / "split-summary.json",
        _split_payload(row_count=3, holdout_count=1, leakage_check_passed=False),
    )

    summary = gate.build_ocr_benchmark_gate(
        pii_preflight_path=pii_path,
        ground_truth_bundle_summary_path=gt_path,
        ground_truth_preflight_path=gt_preflight_path,
        benchmark_summary_path=benchmark_path,
        benchmark_split_summary_path=split_path,
    )

    assert summary["status"] == "blocked_by_benchmark_split_assignment"
    assert summary["benchmark_split_leakage_check_passed"] is False
    assert summary["external_teacher_ocr_eval_allowed"] is False


def test_ocr_benchmark_gate_allows_teacher_eval_after_all_gates(tmp_path: Path) -> None:
    """Verify full gate readiness allows teacher OCR eval but not PaddleOCR training."""
    pii_path = _write_json(
        tmp_path / "pii.json",
        _pii_payload(ready=True, cleared_count=3, blank_count=0, pending_count=0),
    )
    gt_path = _write_json(tmp_path / "gt-summary.json", _gt_payload(row_count=3, ready_count=3))
    gt_preflight_path = _write_json(
        tmp_path / "gt-preflight.json",
        _gt_preflight_payload(row_count=3, ready_count=3),
    )
    benchmark_path = _write_json(
        tmp_path / "benchmark-summary.json",
        _benchmark_payload(fixture_count=3, scoreable_count=3),
    )
    split_path = _write_json(
        tmp_path / "split-summary.json",
        _split_payload(row_count=3, holdout_count=1),
    )

    summary = gate.build_ocr_benchmark_gate(
        pii_preflight_path=pii_path,
        ground_truth_bundle_summary_path=gt_path,
        ground_truth_preflight_path=gt_preflight_path,
        benchmark_summary_path=benchmark_path,
        benchmark_split_summary_path=split_path,
    )

    assert summary["status"] == "ready_for_teacher_ocr_eval"
    assert summary["ground_truth_template_allowed"] is True
    assert summary["benchmark_required_expected_sections"] == [
        "ingredient_amounts",
        "intake_method",
        "precautions",
        "allergen_warnings",
    ]
    assert summary["benchmark_required_sections_ready"] is True
    assert summary["benchmark_split_ready"] is True
    assert summary["benchmark_holdout_fixture_count"] == 1
    assert summary["teacher_ocr_benchmark_allowed"] is True
    assert summary["external_teacher_ocr_allowed_now"] is True
    assert summary["external_teacher_ocr_eval_allowed"] is True
    assert summary["paddleocr_training_allowed_now"] is False
    assert summary["paddleocr_training_allowed_after_eval_gate"] is False
    assert summary["next_steps"] == [
        "run_clova_google_vision_paddleocr_eval_on_benchmark_manifest",
        "build_paddleocr_improvement_candidates_from_eval",
        "keep_paddleocr_training_blocked_until_baseline_gate_passes",
    ]


def test_ocr_benchmark_gate_rejects_unsafe_input_payload(tmp_path: Path) -> None:
    """Verify raw OCR/provider payload keys fail closed."""
    payload = _pii_payload()
    payload["raw_ocr_text"] = "unsafe"
    pii_path = _write_json(tmp_path / "pii.json", payload)

    with pytest.raises(ValueError, match="raw key"):
        gate.build_ocr_benchmark_gate(pii_preflight_path=pii_path)


def test_ocr_benchmark_gate_cli_writes_json_and_markdown(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI writes redacted JSON and Markdown reports."""
    pii_path = _write_json(tmp_path / "pii.json", _pii_payload())
    output_path = tmp_path / "gate.json"
    markdown_path = tmp_path / "gate.md"

    gate.main(
        [
            "--pii-decision-preflight",
            str(pii_path),
            "--output",
            str(output_path),
            "--markdown-output",
            str(markdown_path),
        ]
    )

    stdout = capsys.readouterr().out
    summary = json.loads(output_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert summary["status"] == "blocked_by_pii_screening"
    assert "Teacher OCR benchmark allowed" in markdown
    assert '"teacher_ocr_benchmark_allowed": false' in stdout
    assert str(tmp_path) not in stdout


def test_ocr_benchmark_gate_cli_require_ready_exits_nonzero_when_blocked(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify the CLI can fail closed before provider OCR commands run."""
    pii_path = _write_json(tmp_path / "pii.json", _pii_payload())
    output_path = tmp_path / "gate.json"

    with pytest.raises(SystemExit) as exc:
        gate.main(
            [
                "--pii-decision-preflight",
                str(pii_path),
                "--output",
                str(output_path),
                "--require-ready-for-teacher-ocr-eval",
            ]
        )

    stdout = capsys.readouterr().out
    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert exc.value.code == 1
    assert summary["status"] == "blocked_by_pii_screening"
    assert '"external_teacher_ocr_eval_allowed": false' in stdout
    assert str(tmp_path) not in stdout
