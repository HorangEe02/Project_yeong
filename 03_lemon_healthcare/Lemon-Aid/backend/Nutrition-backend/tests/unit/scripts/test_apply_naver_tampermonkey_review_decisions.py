"""Tests for applying review decisions to Naver Tampermonkey review ingest rows."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import apply_naver_tampermonkey_review_decisions as applier


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
        "image": {
            "root_token": "$NAVER_TAMPERMONKEY_SOURCE_ROOT",
            "image_ref_hash": "b" * 64,
            "image_sha256": "a" * 64,
        },
        "category_key": "omega_3",
        "language_targets": ["ko", "en"],
        "contains_personal_data": False,
        "pii_screening_status": "not_required_detail_page",
        "external_transfer_allowed": True,
        "local_processing_allowed": True,
        "requires_human_review": True,
        "is_clinical_recommendation": False,
        "clinical_recommendation_forbidden": True,
        "ocr_observation_count": 1,
        "ingredient_candidate_count": 1,
        "ingredient_candidates": [
            {
                "display_name": "오메가3",
                "nutrient_code": "omega_3",
                "amount": 1000.0,
                "unit": "mg",
                "confidence": 0.92,
                "source": "ollama_structured",
                "provider": "paddleocr_local",
            }
        ],
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
            "attest_pii_screening_completed": True,
            "attest_no_raw_ocr_text": True,
            "attest_not_clinical_recommendation": True,
            "ingredients": [
                {
                    "display_name": "Omega-3",
                    "nutrient_code": "omega_3",
                    "amount": 1000,
                    "unit": "mg",
                }
            ],
        },
    }
    row.update(overrides)
    return row


def test_apply_review_decisions_attaches_valid_decisions(tmp_path: Path) -> None:
    """Verify structured decisions are attached and validated."""
    review_path = tmp_path / "review.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(review_path, [_review_row()])
    _write_jsonl(decisions_path, [_decision_row()])

    rows, summary = applier.apply_review_decisions(
        review_ingest_path=review_path,
        decisions_path=decisions_path,
        output_name="review-with-decisions.jsonl",
        require_reviewed=True,
    )

    assert summary["matched_decision_count"] == 1
    assert summary["pending_count"] == 0
    assert summary["decision_status_counts"] == {"approved": 1}
    assert rows[0]["review_decision"] == {
        "status": "approved",
        "reviewer_id": "operator_1",
        "reviewed_at": "2026-05-24T14:30:00+09:00",
        "display_name": "Omega-3 1000",
        "attest_pii_screening_completed": True,
        "attest_no_raw_ocr_text": True,
        "attest_not_clinical_recommendation": True,
        "ingredients": [
            {
                "display_name": "Omega-3",
                "nutrient_code": "omega_3",
                "amount": 1000,
                "unit": "mg",
            }
        ],
    }
    serialized = json.dumps(rows, ensure_ascii=False).lower()
    assert '"raw_ocr_text"' not in serialized
    assert '"provider_payload"' not in serialized
    assert "/volumes/" not in serialized


def test_apply_review_decisions_allows_partial_pending_by_default(tmp_path: Path) -> None:
    """Verify operator can apply partial decision batches."""
    review_path = tmp_path / "review.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(
        review_path,
        [
            _review_row(),
            _review_row(
                review_task_id="e" * 64,
                fixture_id="naver-tm-detail-000002",
            ),
        ],
    )
    _write_jsonl(decisions_path, [_decision_row()])

    rows, summary = applier.apply_review_decisions(
        review_ingest_path=review_path,
        decisions_path=decisions_path,
        output_name="review-with-decisions.jsonl",
    )

    assert len(rows) == 2
    assert summary["matched_decision_count"] == 1
    assert summary["pending_count"] == 1
    assert summary["decision_status_counts"] == {"approved": 1, "pending": 1}
    assert "review_decision" not in rows[1]


def test_apply_review_decisions_can_require_all_reviewed(tmp_path: Path) -> None:
    """Verify strict mode fails when any row remains pending."""
    review_path = tmp_path / "review.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(
        review_path,
        [
            _review_row(),
            _review_row(review_task_id="e" * 64, fixture_id="naver-tm-detail-000002"),
        ],
    )
    _write_jsonl(decisions_path, [_decision_row()])

    with pytest.raises(ValueError, match="requires every row"):
        applier.apply_review_decisions(
            review_ingest_path=review_path,
            decisions_path=decisions_path,
            output_name="review-with-decisions.jsonl",
            require_reviewed=True,
        )


def test_apply_review_decisions_rejects_unmatched_and_duplicate_decisions(
    tmp_path: Path,
) -> None:
    """Verify cross-file decision mismatches fail closed."""
    review_path = tmp_path / "review.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(review_path, [_review_row()])
    _write_jsonl(decisions_path, [_decision_row(review_task_id="e" * 64)])

    with pytest.raises(ValueError, match="not in review ingest"):
        applier.apply_review_decisions(
            review_ingest_path=review_path,
            decisions_path=decisions_path,
            output_name="review-with-decisions.jsonl",
        )

    duplicate_path = tmp_path / "duplicate-decisions.jsonl"
    _write_jsonl(duplicate_path, [_decision_row(), _decision_row()])

    with pytest.raises(ValueError, match="Duplicate review decision"):
        applier.apply_review_decisions(
            review_ingest_path=review_path,
            decisions_path=duplicate_path,
            output_name="review-with-decisions.jsonl",
        )


def test_apply_review_decisions_rejects_missing_decision_schema_version(
    tmp_path: Path,
) -> None:
    """Verify decision batches must declare the importable decision schema."""
    review_path = tmp_path / "review.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    decision = _decision_row()
    decision.pop("schema_version")
    _write_jsonl(review_path, [_review_row()])
    _write_jsonl(decisions_path, [decision])

    with pytest.raises(ValueError, match="review decision schema"):
        applier.apply_review_decisions(
            review_ingest_path=review_path,
            decisions_path=decisions_path,
            output_name="review-with-decisions.jsonl",
        )


def test_apply_review_decisions_rejects_fixture_id_mismatch(
    tmp_path: Path,
) -> None:
    """Verify decision rows must target the matched fixture, not just review id."""
    review_path = tmp_path / "review.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(review_path, [_review_row()])
    _write_jsonl(
        decisions_path,
        [_decision_row(fixture_id="naver-tm-detail-999999")],
    )

    with pytest.raises(ValueError, match="review ingest fixture_id"):
        applier.apply_review_decisions(
            review_ingest_path=review_path,
            decisions_path=decisions_path,
            output_name="review-with-decisions.jsonl",
        )


def test_apply_review_decisions_rejects_existing_decision_without_overwrite(
    tmp_path: Path,
) -> None:
    """Verify decisions are not silently overwritten."""
    review_path = tmp_path / "review.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(review_path, [_review_row(review_decision=_decision_row()["review_decision"])])
    _write_jsonl(decisions_path, [_decision_row()])

    with pytest.raises(ValueError, match="already has review_decision"):
        applier.apply_review_decisions(
            review_ingest_path=review_path,
            decisions_path=decisions_path,
            output_name="review-with-decisions.jsonl",
        )

    rows, summary = applier.apply_review_decisions(
        review_ingest_path=review_path,
        decisions_path=decisions_path,
        output_name="review-with-decisions.jsonl",
        overwrite_existing=True,
        require_reviewed=True,
    )
    assert rows[0]["review_decision"] == _decision_row()["review_decision"]
    assert summary["overwrite_existing"] is True


def test_apply_review_decisions_rejects_unsafe_decision_payloads(tmp_path: Path) -> None:
    """Verify raw fields, local paths, and free-text notes are blocked."""
    review_path = tmp_path / "review.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(review_path, [_review_row()])
    unsafe = _decision_row()
    decision = dict(unsafe["review_decision"])  # type: ignore[arg-type]
    decision["review_note"] = "free text is not allowed"
    unsafe["review_decision"] = decision
    _write_jsonl(decisions_path, [unsafe])

    with pytest.raises(ValueError, match="free-text"):
        applier.apply_review_decisions(
            review_ingest_path=review_path,
            decisions_path=decisions_path,
            output_name="review-with-decisions.jsonl",
        )

    raw_path = tmp_path / "raw-decisions.jsonl"
    _write_jsonl(raw_path, [_decision_row(raw_ocr_text="do not persist")])

    with pytest.raises(ValueError, match="raw_ocr_text"):
        applier.apply_review_decisions(
            review_ingest_path=review_path,
            decisions_path=raw_path,
            output_name="review-with-decisions.jsonl",
        )

    local_path = tmp_path / "local-decisions.jsonl"
    local_decision = _decision_row()
    local_payload = dict(local_decision["review_decision"])  # type: ignore[arg-type]
    local_payload["display_name"] = "/Volumes/Corsair EX400U Media/a.jpg"
    local_decision["review_decision"] = local_payload
    _write_jsonl(local_path, [local_decision])

    with pytest.raises(ValueError, match="local path literal"):
        applier.apply_review_decisions(
            review_ingest_path=review_path,
            decisions_path=local_path,
            output_name="review-with-decisions.jsonl",
        )


def test_apply_review_decisions_rejects_template_rows(tmp_path: Path) -> None:
    """Verify operator templates cannot be imported as decision rows."""
    review_path = tmp_path / "review.jsonl"
    decisions_path = tmp_path / "template-as-decisions.jsonl"
    _write_jsonl(review_path, [_review_row()])
    _write_jsonl(
        decisions_path,
        [
            {
                "schema_version": "naver-tampermonkey-review-decision-template-v1",
                "review_task_id": "d" * 64,
                "fixture_id": "naver-tm-detail-000001",
                "decision_entry_template": _decision_row(),
                "decision_batch_importable": False,
            }
        ],
    )

    with pytest.raises(ValueError, match="review decision schema"):
        applier.apply_review_decisions(
            review_ingest_path=review_path,
            decisions_path=decisions_path,
            output_name="review-with-decisions.jsonl",
        )


def test_apply_review_decisions_rejects_unedited_decision_skeleton(
    tmp_path: Path,
) -> None:
    """Verify null placeholder skeletons fail before import."""
    review_path = tmp_path / "review.jsonl"
    decisions_path = tmp_path / "skeleton-decisions.jsonl"
    _write_jsonl(review_path, [_review_row()])
    _write_jsonl(
        decisions_path,
        [
            {
                "schema_version": "naver-tampermonkey-review-decision-v1",
                "review_task_id": "d" * 64,
                "fixture_id": "naver-tm-detail-000001",
                "review_decision": {
                    "status": None,
                    "reviewer_id": None,
                    "reviewed_at": None,
                    "display_name": None,
                    "ingredients": [
                        {
                            "display_name": None,
                            "nutrient_code": None,
                            "amount": None,
                            "unit": None,
                            "source": "human_reviewed",
                        }
                    ],
                    "reason_codes": [],
                    "attest_pii_screening_completed": False,
                    "attest_no_raw_ocr_text": False,
                    "attest_not_clinical_recommendation": False,
                },
                "decision_batch_importable": False,
            }
        ],
    )

    with pytest.raises(ValueError, match="status"):
        applier.apply_review_decisions(
            review_ingest_path=review_path,
            decisions_path=decisions_path,
            output_name="review-with-decisions.jsonl",
        )


def test_apply_review_decisions_rejects_pii_pending_approval(tmp_path: Path) -> None:
    """Verify merged validation catches PII-pending review row approvals."""
    review_path = tmp_path / "review.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    _write_jsonl(
        review_path,
        [
            _review_row(
                section="review",
                contains_personal_data=None,
                pii_screening_status="pending_local_screening",
            )
        ],
    )
    _write_jsonl(decisions_path, [_decision_row()])

    with pytest.raises(ValueError, match="PII clearance"):
        applier.apply_review_decisions(
            review_ingest_path=review_path,
            decisions_path=decisions_path,
            output_name="review-with-decisions.jsonl",
        )


def test_apply_review_decisions_rejects_non_object_rows_without_path_leak(
    tmp_path: Path,
) -> None:
    """Verify direct decision-apply errors do not include the input path."""
    review_path = tmp_path / "review.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    review_path.write_text("[]\n", encoding="utf-8")
    _write_jsonl(decisions_path, [])

    with pytest.raises(ValueError) as exc_info:
        applier.apply_review_decisions(
            review_ingest_path=review_path,
            decisions_path=decisions_path,
            output_name="review-with-decisions.jsonl",
        )

    assert str(tmp_path) not in str(exc_info.value)
    assert str(review_path) not in str(exc_info.value)
    assert str(exc_info.value) == "JSONL rows must be objects."


def test_apply_review_decisions_main_error_is_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI failures print a redacted JSON summary instead of traceback paths."""
    missing_review = tmp_path / "missing-review.jsonl"
    missing_decisions = tmp_path / "missing-decisions.jsonl"
    output_path = tmp_path / "review-with-decisions.jsonl"
    monkeypatch.setattr(
        "sys.argv",
        [
            "apply_naver_tampermonkey_review_decisions.py",
            "--review-ingest",
            str(missing_review),
            "--decisions",
            str(missing_decisions),
            "--output",
            str(output_path),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        applier.main()

    assert exc_info.value.code == 1
    stdout = capsys.readouterr().out
    summary = json.loads(stdout)
    assert summary["status"] == "error"
    assert summary["error_message"] == "Local file operation failed."
    assert str(tmp_path) not in stdout
    assert "/private/" not in stdout
