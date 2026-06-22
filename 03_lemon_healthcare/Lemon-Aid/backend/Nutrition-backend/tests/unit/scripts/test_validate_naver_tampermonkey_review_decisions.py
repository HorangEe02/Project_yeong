"""Tests for validating Naver Tampermonkey review UI decisions."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scripts import validate_naver_tampermonkey_review_decisions as validator


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


def _approved_decision(**overrides: object) -> dict[str, object]:
    """Return a valid approved decision."""
    row: dict[str, object] = {
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
                "source": "human_reviewed",
            }
        ],
    }
    row.update(overrides)
    return row


def test_validate_allows_pending_rows_by_default(tmp_path: Path) -> None:
    """Verify in-progress review queues can be validated before completion."""
    input_path = tmp_path / "review.jsonl"
    _write_jsonl(input_path, [_review_row()])

    summary = validator.validate_review_decisions(input_path=input_path)

    assert summary["row_count"] == 1
    assert summary["pending_count"] == 1
    assert summary["decision_status_counts"] == {"pending": 1}
    assert summary["raw_ocr_text_stored"] is False
    assert summary["free_text_review_notes_stored"] is False


def test_validate_can_require_reviewed_rows(tmp_path: Path) -> None:
    """Verify strict mode catches missing review decisions."""
    input_path = tmp_path / "review.jsonl"
    _write_jsonl(input_path, [_review_row()])

    with pytest.raises(ValueError, match="requires every row"):
        validator.validate_review_decisions(input_path=input_path, require_reviewed=True)


def test_validate_accepts_approved_decisions_with_attestations(tmp_path: Path) -> None:
    """Verify approved rows require reviewed ingredients and safety attestations."""
    input_path = tmp_path / "review.jsonl"
    _write_jsonl(input_path, [_review_row(review_decision=_approved_decision())])

    summary = validator.validate_review_decisions(
        input_path=input_path,
        require_reviewed=True,
    )

    assert summary["decision_status_counts"] == {"approved": 1}
    assert summary["approved_ingredient_count"] == 1
    assert summary["clinical_recommendations_stored"] is False


def test_validate_rejects_model_only_reviewer_id(tmp_path: Path) -> None:
    """Verify model-only reviewer ids cannot satisfy the human review gate."""
    input_path = tmp_path / "review.jsonl"
    _write_jsonl(
        input_path,
        [
            _review_row(
                review_decision=_approved_decision(reviewer_id="ollama_gemma4"),
            )
        ],
    )

    with pytest.raises(ValueError, match="operator_ prefix"):
        validator.validate_review_decisions(input_path=input_path)


@pytest.mark.parametrize(
    "reviewed_at",
    [
        "2026-05-24T14:30:00",
        "not-a-date",
    ],
)
def test_validate_rejects_non_timezone_aware_reviewed_at(
    tmp_path: Path,
    reviewed_at: str,
) -> None:
    """Verify review decisions require an unambiguous reviewed_at timestamp."""
    input_path = tmp_path / "review.jsonl"
    _write_jsonl(
        input_path,
        [_review_row(review_decision=_approved_decision(reviewed_at=reviewed_at))],
    )

    with pytest.raises(ValueError, match="timezone-aware ISO datetime field: reviewed_at"):
        validator.validate_review_decisions(input_path=input_path)


def test_validate_rejects_approved_decision_without_attestation(tmp_path: Path) -> None:
    """Verify approval cannot omit safety attestations."""
    input_path = tmp_path / "review.jsonl"
    decision = _approved_decision(attest_not_clinical_recommendation=False)
    _write_jsonl(input_path, [_review_row(review_decision=decision)])

    with pytest.raises(ValueError, match="attest_not_clinical_recommendation"):
        validator.validate_review_decisions(input_path=input_path)


def test_validate_rejects_non_human_ingredient_source(tmp_path: Path) -> None:
    """Verify approved ingredients cannot keep OCR or LLM provenance."""
    input_path = tmp_path / "review.jsonl"
    decision = _approved_decision()
    ingredients = [dict(item) for item in decision["ingredients"]]  # type: ignore[index]
    ingredients[0]["source"] = "ollama_structured"
    decision["ingredients"] = ingredients
    _write_jsonl(input_path, [_review_row(review_decision=decision)])

    with pytest.raises(ValueError, match="source must be human_reviewed"):
        validator.validate_review_decisions(input_path=input_path)


def test_validate_rejects_duplicate_approved_ingredients(tmp_path: Path) -> None:
    """Verify approved decisions cannot duplicate the same ingredient identity."""
    input_path = tmp_path / "review.jsonl"
    decision = _approved_decision()
    ingredient = dict(decision["ingredients"][0])  # type: ignore[index]
    duplicate = {**ingredient, "display_name": " omega-3 "}
    decision["ingredients"] = [ingredient, duplicate]
    _write_jsonl(input_path, [_review_row(review_decision=decision)])

    with pytest.raises(ValueError, match="unique per product"):
        validator.validate_review_decisions(input_path=input_path)


@pytest.mark.parametrize(
    "display_name",
    [
        "g X30포(",
        "정x 3개입(",
        "1000mg",
        "60 capsules",
    ],
)
def test_validate_rejects_packaging_quantity_ingredient_names(
    tmp_path: Path,
    display_name: str,
) -> None:
    """Verify approved ingredients cannot be package counts or dosage-only text."""
    input_path = tmp_path / "review.jsonl"
    decision = _approved_decision()
    ingredients = [dict(item) for item in decision["ingredients"]]  # type: ignore[index]
    ingredients[0]["display_name"] = display_name
    decision["ingredients"] = ingredients
    _write_jsonl(input_path, [_review_row(review_decision=decision)])

    with pytest.raises(ValueError, match="packaging quantity"):
        validator.validate_review_decisions(input_path=input_path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("display_name", "<script>alert(1)</script>"),
        ("manufacturer", "javascript:alert(1)"),
        ("manufacturer", "https://example.test/product"),
    ],
)
def test_validate_rejects_executable_review_decision_text(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    """Verify review decisions cannot carry HTML, script protocols, or URLs."""
    input_path = tmp_path / "review.jsonl"
    _write_jsonl(input_path, [_review_row(review_decision=_approved_decision(**{field: value}))])

    with pytest.raises(ValueError, match="executable or URL-like"):
        validator.validate_review_decisions(input_path=input_path)


def test_validate_rejects_string_or_bool_ingredient_amount(tmp_path: Path) -> None:
    """Verify approved ingredient amounts stay numeric, not free text."""
    for index, value in enumerate(("1000", True)):
        input_path = tmp_path / f"review-{index}.jsonl"
        decision = _approved_decision()
        ingredients = [dict(item) for item in decision["ingredients"]]  # type: ignore[index]
        ingredients[0]["amount"] = value
        decision["ingredients"] = ingredients
        _write_jsonl(input_path, [_review_row(review_decision=decision)])

        with pytest.raises(ValueError, match="non-negative number"):
            validator.validate_review_decisions(input_path=input_path)


def test_validate_rejects_approved_pii_pending_rows(tmp_path: Path) -> None:
    """Verify PII-pending review rows cannot be approved."""
    input_path = tmp_path / "review.jsonl"
    _write_jsonl(
        input_path,
        [
            _review_row(
                section="review",
                contains_personal_data=None,
                pii_screening_status="pending_local_screening",
                review_decision=_approved_decision(),
            )
        ],
    )

    with pytest.raises(ValueError, match="PII clearance"):
        validator.validate_review_decisions(input_path=input_path)


def test_validate_rejected_decisions_require_reason_codes(tmp_path: Path) -> None:
    """Verify rejected decisions stay structured and reason-coded."""
    input_path = tmp_path / "review.jsonl"
    _write_jsonl(
        input_path,
        [
            _review_row(
                review_decision={
                    "status": "rejected",
                    "reviewer_id": "operator_1",
                    "reviewed_at": "2026-05-24T14:30:00+09:00",
                    "reason_codes": ["not_supplement_label"],
                }
            )
        ],
    )

    summary = validator.validate_review_decisions(
        input_path=input_path,
        require_reviewed=True,
    )

    assert summary["decision_status_counts"] == {"rejected": 1}


def test_validate_rejects_free_text_notes_and_raw_fields(tmp_path: Path) -> None:
    """Verify review decisions cannot carry free-text notes or raw OCR keys."""
    input_path = tmp_path / "review.jsonl"
    _write_jsonl(
        input_path,
        [
            _review_row(
                review_decision={
                    "status": "rejected",
                    "reviewer_id": "operator_1",
                    "reviewed_at": "2026-05-24T14:30:00+09:00",
                    "reason_codes": ["not_supplement_label"],
                    "review_note": "free text is not part of the import contract",
                }
            )
        ],
    )

    with pytest.raises(ValueError, match="free-text"):
        validator.validate_review_decisions(input_path=input_path)

    input_path_2 = tmp_path / "review-raw.jsonl"
    _write_jsonl(
        input_path_2,
        [_review_row(review_decision=_approved_decision(raw_ocr_text="do not persist"))],
    )

    with pytest.raises(ValueError, match="raw_ocr_text"):
        validator.validate_review_decisions(input_path=input_path_2)


def test_validate_rejects_local_path_literals(tmp_path: Path) -> None:
    """Verify local operator paths cannot enter review decisions."""
    input_path = tmp_path / "review.jsonl"
    _write_jsonl(
        input_path,
        [
            _review_row(
                review_decision=_approved_decision(
                    display_name="/Volumes/Corsair EX400U Media/a.jpg"
                )
            )
        ],
    )

    with pytest.raises(ValueError, match="local path literal"):
        validator.validate_review_decisions(input_path=input_path)

    input_path_2 = tmp_path / "review-private-local.jsonl"
    _write_jsonl(
        input_path_2,
        [_review_row(review_decision=_approved_decision(display_name="/private/tmp/a.jpg"))],
    )

    with pytest.raises(ValueError, match="local path literal"):
        validator.validate_review_decisions(input_path=input_path_2)


def test_validate_rejects_non_object_rows_without_path_leak(tmp_path: Path) -> None:
    """Verify direct validation errors do not include the input path."""
    input_path = tmp_path / "review.jsonl"
    input_path.write_text("[]\n", encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        validator.validate_review_decisions(input_path=input_path)

    assert str(tmp_path) not in str(exc_info.value)
    assert str(input_path) not in str(exc_info.value)
    assert str(exc_info.value) == "JSONL rows must be objects."


def test_main_error_is_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI failures do not print tracebacks or local paths."""
    input_path = tmp_path / "missing-review-ingest.jsonl"
    summary_path = tmp_path / "validation-summary.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate_naver_tampermonkey_review_decisions.py",
            "--input",
            str(input_path),
            "--summary",
            str(summary_path),
            "--require-reviewed",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        validator.main()

    printed = capsys.readouterr().out
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert exc_info.value.code == 1
    assert "Traceback" not in printed
    assert str(tmp_path) not in printed
    assert str(tmp_path) not in json.dumps(summary, ensure_ascii=False)
    assert summary["status"] == "error"
    assert summary["error_code"] == "local_file_read_error"
    assert summary["error_message"] == "Local file read failed."
    assert summary["require_reviewed"] is True
    assert summary["raw_model_response_stored"] is False
    assert summary["local_path_literals_stored"] is False
