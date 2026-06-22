"""Tests for the Naver Tampermonkey review import gate runner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import run_naver_tampermonkey_review_import_gate as gate_runner


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write JSONL test rows."""
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _review_row(**overrides: object) -> dict[str, object]:
    """Return a minimal review ingest row."""
    row: dict[str, object] = {
        "schema_version": "naver-tampermonkey-review-ingest-v1",
        "review_task_id": "d" * 64,
        "fixture_id": "naver-tm-detail-000001",
        "source": "naver_tampermonkey",
        "section": "detail",
        "product": {
            "product_id": "1234567890",
            "product_dir_hash": "c" * 64,
        },
        "category_key": "omega_3",
        "contains_personal_data": False,
        "pii_screening_status": "not_required_detail_page",
        "external_transfer_allowed": True,
        "local_processing_allowed": True,
        "requires_human_review": True,
        "is_clinical_recommendation": False,
        "clinical_recommendation_forbidden": True,
    }
    row.update(overrides)
    return row


def _decision_row(**overrides: object) -> dict[str, object]:
    """Return a valid approved decision row."""
    row: dict[str, object] = {
        "schema_version": "naver-tampermonkey-review-decision-v1",
        "review_task_id": "d" * 64,
        "fixture_id": "naver-tm-detail-000001",
        "review_decision": {
            "status": "approved",
            "reviewer_id": "operator_1",
            "reviewed_at": "2026-05-24T14:30:00+09:00",
            "display_name": "Omega-3 1000",
            "manufacturer": "Reviewed Nutrition",
            "category_key": "omega_3",
            "attest_pii_screening_completed": True,
            "attest_no_raw_ocr_text": True,
            "attest_not_clinical_recommendation": True,
            "ingredients": [
                {
                    "display_name": "Omega-3",
                    "nutrient_code": "omega_3",
                    "amount": 1000,
                    "unit": "mg",
                    "source": "human_reviewed",
                }
            ],
        },
    }
    row.update(overrides)
    return row


def _gap_queue_row(**overrides: object) -> dict[str, object]:
    """Return a minimal manual-review gap queue row."""
    row: dict[str, object] = {
        "schema_version": "naver-tampermonkey-manual-review-gap-v1",
        "review_task_id": "d" * 64,
        "fixture_id": "naver-tm-detail-000001",
        "category_key": "omega_3",
        "gap_reasons": ["ingredient_candidate_count_zero"],
        "suggested_operator_actions": ["inspect_source_image_and_enter_manual_ingredients"],
        "ingredient_candidate_count": 0,
        "ocr_observation_count": 1,
        "requires_human_review": True,
        "decision_batch_importable": False,
        "db_write_performed": False,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }
    row.update(overrides)
    return row


def test_review_import_gate_allows_empty_decision_batch(tmp_path: Path) -> None:
    """Verify the gate keeps pending review rows out of DB import plans."""
    review_path = tmp_path / "review.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    output_dir = tmp_path / "gate"
    _write_jsonl(review_path, [_review_row()])
    _write_jsonl(decisions_path, [])

    summary = gate_runner.run_review_import_gate(
        review_ingest_path=review_path,
        decisions_path=decisions_path,
        output_dir=output_dir,
        artifact_prefix="empty",
    )

    assert summary["review_row_count"] == 1
    assert summary["matched_decision_count"] == 0
    assert summary["pending_count"] == 1
    assert summary["approved_row_count"] == 0
    assert summary["planned_product_upsert_count"] == 0
    assert summary["planned_ingredient_row_count"] == 0
    assert summary["dry_run_only"] is True
    assert summary["db_write_performed"] is False
    assert (output_dir / "empty-review-ingest-with-decisions.jsonl").exists()
    assert (output_dir / "empty-approved-db-import.jsonl").read_text(encoding="utf-8") == ""
    serialized = json.dumps(summary, ensure_ascii=False).lower()
    assert '"raw_ocr_text"' not in serialized
    assert "/volumes/" not in serialized


def test_review_import_gate_can_require_gap_rows_only(tmp_path: Path) -> None:
    """Verify gap-scoped strict mode does not require all review rows."""
    review_path = tmp_path / "review.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    gap_path = tmp_path / "gap.jsonl"
    output_dir = tmp_path / "gate"
    _write_jsonl(
        review_path,
        [
            _review_row(),
            _review_row(
                review_task_id="e" * 64,
                fixture_id="naver-tm-detail-000002",
                category_key="vitamin_d",
            ),
        ],
    )
    _write_jsonl(decisions_path, [_decision_row()])
    _write_jsonl(gap_path, [_gap_queue_row()])

    summary = gate_runner.run_review_import_gate(
        review_ingest_path=review_path,
        decisions_path=decisions_path,
        output_dir=output_dir,
        artifact_prefix="gap",
        gap_queue_path=gap_path,
        require_gap_reviewed=True,
        require_gap_approved=True,
    )

    assert summary["review_row_count"] == 2
    assert summary["pending_count"] == 1
    assert summary["gap_queue_row_count"] == 1
    assert summary["gap_reviewed_count"] == 1
    assert summary["gap_pending_count"] == 0
    assert summary["gap_approved_count"] == 1
    assert summary["gap_decision_status_counts"] == {"approved": 1}
    assert summary["approved_row_count"] == 1
    assert summary["planned_product_upsert_count"] == 1
    assert summary["db_write_performed"] is False


def test_review_import_gate_can_restrict_decisions_to_gap_queue(tmp_path: Path) -> None:
    """Verify gap-only mode rejects approval rows outside the gap queue."""
    review_path = tmp_path / "review.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    gap_path = tmp_path / "gap.jsonl"
    _write_jsonl(
        review_path,
        [
            _review_row(),
            _review_row(
                review_task_id="e" * 64,
                fixture_id="naver-tm-detail-000002",
                category_key="vitamin_d",
            ),
        ],
    )
    _write_jsonl(
        decisions_path,
        [
            _decision_row(
                review_task_id="e" * 64,
                fixture_id="naver-tm-detail-000002",
            )
        ],
    )
    _write_jsonl(gap_path, [_gap_queue_row()])

    with pytest.raises(ValueError, match="outside gap queue"):
        gate_runner.run_review_import_gate(
            review_ingest_path=review_path,
            decisions_path=decisions_path,
            output_dir=tmp_path / "gate",
            gap_queue_path=gap_path,
            restrict_decisions_to_gap=True,
        )


def test_review_import_gate_rejects_decision_rows_without_schema_version(
    tmp_path: Path,
) -> None:
    """Verify gate-scoped decision batches must declare the decision schema."""
    review_path = tmp_path / "review.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    decision = _decision_row()
    decision.pop("schema_version")
    _write_jsonl(review_path, [_review_row()])
    _write_jsonl(decisions_path, [decision])

    with pytest.raises(ValueError, match="review decision schema"):
        gate_runner.run_review_import_gate(
            review_ingest_path=review_path,
            decisions_path=decisions_path,
            output_dir=tmp_path / "gate",
        )


def test_review_import_gate_reports_non_gap_decision_count(tmp_path: Path) -> None:
    """Verify non-gap decisions are counted when restriction is disabled."""
    review_path = tmp_path / "review.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    gap_path = tmp_path / "gap.jsonl"
    _write_jsonl(
        review_path,
        [
            _review_row(),
            _review_row(
                review_task_id="e" * 64,
                fixture_id="naver-tm-detail-000002",
                category_key="vitamin_d",
            ),
        ],
    )
    _write_jsonl(
        decisions_path,
        [
            _decision_row(
                review_task_id="e" * 64,
                fixture_id="naver-tm-detail-000002",
            )
        ],
    )
    _write_jsonl(gap_path, [_gap_queue_row()])

    summary = gate_runner.run_review_import_gate(
        review_ingest_path=review_path,
        decisions_path=decisions_path,
        output_dir=tmp_path / "gate",
        artifact_prefix="scope",
        gap_queue_path=gap_path,
    )

    assert summary["non_gap_decision_count"] == 1
    assert summary["restrict_decisions_to_gap"] is False


def test_review_import_gate_requires_gap_rows_reviewed(tmp_path: Path) -> None:
    """Verify gap-scoped strict mode fails when a gap row is still pending."""
    review_path = tmp_path / "review.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    gap_path = tmp_path / "gap.jsonl"
    _write_jsonl(review_path, [_review_row()])
    _write_jsonl(decisions_path, [])
    _write_jsonl(gap_path, [_gap_queue_row()])

    with pytest.raises(ValueError, match="every gap row"):
        gate_runner.run_review_import_gate(
            review_ingest_path=review_path,
            decisions_path=decisions_path,
            output_dir=tmp_path / "gate",
            gap_queue_path=gap_path,
            require_gap_reviewed=True,
        )


def test_review_import_gate_keeps_rejected_gap_rows_out_of_import(
    tmp_path: Path,
) -> None:
    """Verify reviewed but rejected gap rows do not become DB import candidates."""
    review_path = tmp_path / "review.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    gap_path = tmp_path / "gap.jsonl"
    rejected_decision = _decision_row()
    rejected_decision["review_decision"] = {
        "status": "rejected",
        "reviewer_id": "operator_1",
        "reviewed_at": "2026-05-24T14:30:00+09:00",
        "reason_codes": ["not_scoreable"],
    }
    _write_jsonl(review_path, [_review_row()])
    _write_jsonl(decisions_path, [rejected_decision])
    _write_jsonl(gap_path, [_gap_queue_row()])

    summary = gate_runner.run_review_import_gate(
        review_ingest_path=review_path,
        decisions_path=decisions_path,
        output_dir=tmp_path / "reviewed-gate",
        artifact_prefix="rejected-gap",
        gap_queue_path=gap_path,
        require_gap_reviewed=True,
    )

    assert summary["gap_reviewed_count"] == 1
    assert summary["gap_pending_count"] == 0
    assert summary["gap_approved_count"] == 0
    assert summary["gap_decision_status_counts"] == {"rejected": 1}
    assert summary["approved_row_count"] == 0
    assert summary["planned_product_upsert_count"] == 0
    assert summary["db_write_performed"] is False

    with pytest.raises(ValueError, match="approved"):
        gate_runner.run_review_import_gate(
            review_ingest_path=review_path,
            decisions_path=decisions_path,
            output_dir=tmp_path / "approved-gate",
            artifact_prefix="rejected-gap-approved",
            gap_queue_path=gap_path,
            require_gap_reviewed=True,
            require_gap_approved=True,
        )


def test_review_import_gate_rejects_unmatched_gap_queue(tmp_path: Path) -> None:
    """Verify gap queues must reference review ingest rows."""
    review_path = tmp_path / "review.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    gap_path = tmp_path / "gap.jsonl"
    _write_jsonl(review_path, [_review_row()])
    _write_jsonl(decisions_path, [])
    _write_jsonl(gap_path, [_gap_queue_row(review_task_id="e" * 64)])

    with pytest.raises(ValueError, match="not in review ingest"):
        gate_runner.run_review_import_gate(
            review_ingest_path=review_path,
            decisions_path=decisions_path,
            output_dir=tmp_path / "gate",
            gap_queue_path=gap_path,
        )


def test_review_import_gate_rejects_gap_queue_fixture_mismatch(tmp_path: Path) -> None:
    """Verify gap queues cannot retarget a review id to a different fixture."""
    review_path = tmp_path / "review.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    gap_path = tmp_path / "gap.jsonl"
    _write_jsonl(review_path, [_review_row()])
    _write_jsonl(decisions_path, [])
    _write_jsonl(gap_path, [_gap_queue_row(fixture_id="naver-tm-detail-999999")])

    with pytest.raises(ValueError, match="fixture_id"):
        gate_runner.run_review_import_gate(
            review_ingest_path=review_path,
            decisions_path=decisions_path,
            output_dir=tmp_path / "gate",
            gap_queue_path=gap_path,
        )


def test_review_import_gate_rejects_unsafe_gap_queue(tmp_path: Path) -> None:
    """Verify unsafe gap queues cannot drive scoped import gates."""
    review_path = tmp_path / "review.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    gap_path = tmp_path / "gap.jsonl"
    _write_jsonl(review_path, [_review_row()])
    _write_jsonl(decisions_path, [])
    _write_jsonl(gap_path, [_gap_queue_row(raw_ocr_text="forbidden")])

    with pytest.raises(ValueError, match="raw_ocr_text"):
        gate_runner.run_review_import_gate(
            review_ingest_path=review_path,
            decisions_path=decisions_path,
            output_dir=tmp_path / "gate",
            gap_queue_path=gap_path,
        )


def test_review_import_gate_exports_approved_rows_to_dry_run_plan(tmp_path: Path) -> None:
    """Verify an approved human decision reaches the ORM dry-run plan only."""
    review_path = tmp_path / "review.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    output_dir = tmp_path / "gate"
    _write_jsonl(review_path, [_review_row()])
    _write_jsonl(decisions_path, [_decision_row()])

    summary = gate_runner.run_review_import_gate(
        review_ingest_path=review_path,
        decisions_path=decisions_path,
        output_dir=output_dir,
        artifact_prefix="approved",
        require_reviewed=True,
        require_all_approved=True,
    )

    assert summary["matched_decision_count"] == 1
    assert summary["pending_count"] == 0
    assert summary["approved_row_count"] == 1
    assert summary["planned_product_upsert_count"] == 1
    assert summary["planned_ingredient_row_count"] == 1
    plan_rows = [
        json.loads(line)
        for line in (output_dir / "approved-approved-db-import-dry-run.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert plan_rows[0]["product"]["table"] == "supplement_products"
    assert plan_rows[0]["ingredient_replace_plan"]["ingredient_count"] == 1
    assert plan_rows[0]["db_write_performed"] is False


def test_review_import_gate_can_require_all_rows_reviewed(tmp_path: Path) -> None:
    """Verify strict review mode fails when rows remain pending."""
    review_path = tmp_path / "review.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(review_path, [_review_row()])
    _write_jsonl(decisions_path, [])

    with pytest.raises(ValueError, match="requires every row"):
        gate_runner.run_review_import_gate(
            review_ingest_path=review_path,
            decisions_path=decisions_path,
            output_dir=tmp_path / "gate",
            require_reviewed=True,
        )


def test_review_import_gate_rejects_unmatched_decisions_by_default(tmp_path: Path) -> None:
    """Verify decisions absent from the review queue fail closed by default."""
    review_path = tmp_path / "review.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(review_path, [_review_row()])
    _write_jsonl(decisions_path, [_decision_row(review_task_id="e" * 64)])

    with pytest.raises(ValueError, match="not in review ingest"):
        gate_runner.run_review_import_gate(
            review_ingest_path=review_path,
            decisions_path=decisions_path,
            output_dir=tmp_path / "gate",
        )


def test_review_import_gate_rejects_unsafe_decision_payloads(tmp_path: Path) -> None:
    """Verify raw fields, local paths, and free-text decisions are rejected."""
    review_path = tmp_path / "review.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    output_dir = tmp_path / "gate"
    _write_jsonl(review_path, [_review_row()])
    unsafe_decision = _decision_row()
    review_decision = dict(unsafe_decision["review_decision"])  # type: ignore[arg-type]
    review_decision["display_name"] = "/Volumes/Corsair EX400U Media/a.jpg"
    unsafe_decision["review_decision"] = review_decision
    _write_jsonl(decisions_path, [unsafe_decision])

    with pytest.raises(ValueError, match="local path literal"):
        gate_runner.run_review_import_gate(
            review_ingest_path=review_path,
            decisions_path=decisions_path,
            output_dir=output_dir,
        )

    assert not list(output_dir.glob("*.jsonl"))


def test_review_import_gate_main_error_is_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI failures print a redacted JSON summary instead of traceback paths."""
    missing_review = tmp_path / "missing-review.jsonl"
    missing_decisions = tmp_path / "missing-decisions.jsonl"
    output_dir = tmp_path / "gate"
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_naver_tampermonkey_review_import_gate.py",
            "--review-ingest",
            str(missing_review),
            "--decisions",
            str(missing_decisions),
            "--output-dir",
            str(output_dir),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        gate_runner.main()

    assert exc_info.value.code == 1
    stdout = capsys.readouterr().out
    summary = json.loads(stdout)
    assert summary["status"] == "error"
    assert summary["error_message"] == "Local file operation failed."
    assert str(tmp_path) not in stdout
    assert "/private/" not in stdout
