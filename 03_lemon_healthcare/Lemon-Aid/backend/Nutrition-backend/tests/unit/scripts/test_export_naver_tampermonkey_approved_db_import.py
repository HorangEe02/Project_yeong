"""Tests for exporting approved Tampermonkey review rows to DB import candidates."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scripts import export_naver_tampermonkey_approved_db_import as approved_export


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
        "product": {
            "product_id": "1234567890",
            "product_dir_hash": "c" * 64,
        },
        "category_key": "omega_3",
        "category_display": {"ko": "오메가3", "en": "Omega-3"},
        "language_targets": ["ko", "en"],
        "chronic_fixture_tags": ["cardiovascular"],
        "caution_tags": ["anticoagulant_review"],
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
        "review_task": {
            "status": "needs_human_review",
            "priority": "normal",
            "reasons": ["llm_ingredient_candidates_available"],
            "db_import_ready": False,
            "blocked_reasons": ["human_review_required"],
        },
    }
    row.update(overrides)
    return row


def _decision(**overrides: object) -> dict[str, object]:
    """Return an approved human review decision."""
    row: dict[str, object] = {
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
    }
    row.update(overrides)
    return row


def test_export_approved_review_rows_to_db_import_candidates(tmp_path: Path) -> None:
    """Verify only human-approved review rows become DB import candidates."""
    input_path = tmp_path / "review-ingest.jsonl"
    _write_jsonl(input_path, [_review_row(review_decision=_decision())])

    rows, summary = approved_export.export_approved_db_import_rows(input_path=input_path)

    assert summary["approved_row_count"] == 1
    assert summary["skipped_unapproved_count"] == 0
    assert rows[0]["schema_version"] == approved_export.SCHEMA_VERSION
    assert rows[0]["source_provider"] == "naver_tampermonkey_review"
    assert rows[0]["product_name"] == "Omega-3 1000"
    assert rows[0]["normalized_product_name"] == "omega-3 1000"
    assert rows[0]["category"] == "omega_3"
    assert rows[0]["source_manifest_version"] == "naver-tm-review-ingest-v1"
    assert rows[0]["is_clinical_recommendation"] is False
    assert rows[0]["clinical_recommendation_forbidden"] is True
    assert rows[0]["ingredients"] == [
        {
            "standard_name": "Omega-3",
            "nutrient_code": "omega_3",
            "amount": 1000.0,
            "unit": "mg",
            "source": "human_reviewed",
            "sort_order": 0,
            "source_payload": {
                "reviewer_id": "operator_1",
                "reviewed_at": "2026-05-24T14:30:00+09:00",
                "source_review_task_id": "d" * 64,
            },
        }
    ]
    assert rows[0]["import_gate"] == {
        "ready_for_db_import": True,
        "human_review_approved": True,
        "pii_screening_completed": True,
    }
    serialized = json.dumps(rows, ensure_ascii=False).lower()
    assert "raw_ocr_text" not in serialized
    assert "provider_payload" not in serialized
    assert "/volumes/" not in serialized


def test_export_skips_unapproved_rows_by_default(tmp_path: Path) -> None:
    """Verify unreviewed tasks do not become import candidates."""
    input_path = tmp_path / "review-ingest.jsonl"
    _write_jsonl(input_path, [_review_row()])

    rows, summary = approved_export.export_approved_db_import_rows(input_path=input_path)

    assert rows == []
    assert summary["input_row_count"] == 1
    assert summary["approved_row_count"] == 0
    assert summary["skipped_unapproved_count"] == 1


def test_export_can_require_all_rows_approved(tmp_path: Path) -> None:
    """Verify strict mode fails when review rows remain unapproved."""
    input_path = tmp_path / "review-ingest.jsonl"
    _write_jsonl(input_path, [_review_row()])

    with pytest.raises(ValueError, match="All review ingest rows"):
        approved_export.export_approved_db_import_rows(
            input_path=input_path,
            require_all_approved=True,
        )


def test_export_rejects_approved_rows_without_attestation(tmp_path: Path) -> None:
    """Verify approval cannot omit raw-text and PII safety attestations."""
    input_path = tmp_path / "review-ingest.jsonl"
    decision = _decision(attest_no_raw_ocr_text=False)
    _write_jsonl(input_path, [_review_row(review_decision=decision)])

    with pytest.raises(ValueError, match="attest_no_raw_ocr_text"):
        approved_export.export_approved_db_import_rows(input_path=input_path)


def test_export_rejects_model_only_reviewer_id(tmp_path: Path) -> None:
    """Verify direct approved export keeps the human reviewer gate."""
    input_path = tmp_path / "review-ingest.jsonl"
    _write_jsonl(
        input_path,
        [
            _review_row(
                review_decision=_decision(reviewer_id="ollama_gemma4"),
            )
        ],
    )

    with pytest.raises(ValueError, match="operator_ prefix"):
        approved_export.export_approved_db_import_rows(input_path=input_path)


@pytest.mark.parametrize(
    "reviewed_at",
    [
        "2026-05-24T14:30:00",
        "not-a-date",
    ],
)
def test_export_rejects_non_timezone_aware_reviewed_at(
    tmp_path: Path,
    reviewed_at: str,
) -> None:
    """Verify direct approved export requires an unambiguous review timestamp."""
    input_path = tmp_path / "review-ingest.jsonl"
    _write_jsonl(input_path, [_review_row(review_decision=_decision(reviewed_at=reviewed_at))])

    with pytest.raises(ValueError, match="timezone-aware ISO datetime field: reviewed_at"):
        approved_export.export_approved_db_import_rows(input_path=input_path)


def test_export_rejects_non_human_ingredient_source(tmp_path: Path) -> None:
    """Verify approved DB import cannot preserve OCR or LLM ingredient source."""
    input_path = tmp_path / "review-ingest.jsonl"
    decision = _decision()
    ingredients = [dict(item) for item in decision["ingredients"]]  # type: ignore[index]
    ingredients[0]["source"] = "ollama_structured"
    decision["ingredients"] = ingredients
    _write_jsonl(input_path, [_review_row(review_decision=decision)])

    with pytest.raises(ValueError, match="source must be human_reviewed"):
        approved_export.export_approved_db_import_rows(input_path=input_path)


def test_export_rejects_duplicate_approved_ingredients(tmp_path: Path) -> None:
    """Verify approved DB import candidates cannot duplicate child identities."""
    input_path = tmp_path / "review-ingest.jsonl"
    decision = _decision()
    ingredient = dict(decision["ingredients"][0])  # type: ignore[index]
    duplicate = {**ingredient, "display_name": " omega-3 "}
    decision["ingredients"] = [ingredient, duplicate]
    _write_jsonl(input_path, [_review_row(review_decision=decision)])

    with pytest.raises(ValueError, match="unique per product"):
        approved_export.export_approved_db_import_rows(input_path=input_path)


@pytest.mark.parametrize(
    "display_name",
    [
        "g X30포(",
        "정x 3개입(",
        "1000mg",
        "60 capsules",
    ],
)
def test_export_rejects_packaging_quantity_ingredient_names(
    tmp_path: Path,
    display_name: str,
) -> None:
    """Verify approved DB import candidates reject package-count ingredients."""
    input_path = tmp_path / "review-ingest.jsonl"
    decision = _decision()
    ingredients = [dict(item) for item in decision["ingredients"]]  # type: ignore[index]
    ingredients[0]["display_name"] = display_name
    decision["ingredients"] = ingredients
    _write_jsonl(input_path, [_review_row(review_decision=decision)])

    with pytest.raises(ValueError, match="packaging quantity"):
        approved_export.export_approved_db_import_rows(input_path=input_path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("display_name", "<img src=x onerror=alert(1)>"),
        ("manufacturer", "javascript:alert(1)"),
        ("manufacturer", "https://example.test/product"),
    ],
)
def test_export_rejects_executable_review_decision_text(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    """Verify approved DB export blocks HTML, script protocols, and URLs."""
    input_path = tmp_path / "review-ingest.jsonl"
    _write_jsonl(input_path, [_review_row(review_decision=_decision(**{field: value}))])

    with pytest.raises(ValueError, match="executable or URL-like"):
        approved_export.export_approved_db_import_rows(input_path=input_path)


def test_export_rejects_non_numeric_ingredient_amount(tmp_path: Path) -> None:
    """Verify direct export never converts bool/string amounts into numbers."""
    for index, value in enumerate(("1000", True)):
        input_path = tmp_path / f"review-ingest-{index}.jsonl"
        decision = _decision()
        ingredients = [dict(item) for item in decision["ingredients"]]  # type: ignore[index]
        ingredients[0]["amount"] = value
        decision["ingredients"] = ingredients
        _write_jsonl(input_path, [_review_row(review_decision=decision)])

        with pytest.raises(ValueError, match="non-negative number"):
            approved_export.export_approved_db_import_rows(input_path=input_path)


def test_export_rejects_uncleared_pii_rows_even_when_approved(tmp_path: Path) -> None:
    """Verify approved DB import still requires PII clearance."""
    input_path = tmp_path / "review-ingest.jsonl"
    _write_jsonl(
        input_path,
        [
            _review_row(
                section="review",
                contains_personal_data=None,
                pii_screening_status="pending_local_screening",
                review_decision=_decision(),
            )
        ],
    )

    with pytest.raises(ValueError, match="PII clearance"):
        approved_export.export_approved_db_import_rows(input_path=input_path)


def test_export_rejects_raw_and_local_path_literals(tmp_path: Path) -> None:
    """Verify unsafe payload fields cannot enter approved import rows."""
    input_path = tmp_path / "review-ingest.jsonl"
    _write_jsonl(
        input_path,
        [
            _review_row(
                review_decision=_decision(),
                raw_provider_payload={"text": "do not persist"},
            )
        ],
    )

    with pytest.raises(ValueError, match="raw_provider_payload"):
        approved_export.export_approved_db_import_rows(input_path=input_path)

    input_path_2 = tmp_path / "review-ingest-local-path.jsonl"
    _write_jsonl(
        input_path_2,
        [
            _review_row(
                review_decision=_decision(display_name="/Volumes/Corsair EX400U Media/a.jpg")
            )
        ],
    )

    with pytest.raises(ValueError, match="local path literal"):
        approved_export.export_approved_db_import_rows(input_path=input_path_2)

    input_path_3 = tmp_path / "review-ingest-private-path.jsonl"
    _write_jsonl(
        input_path_3,
        [_review_row(review_decision=_decision(display_name="/private/tmp/a.jpg"))],
    )

    with pytest.raises(ValueError, match="local path literal"):
        approved_export.export_approved_db_import_rows(input_path=input_path_3)


def test_main_error_is_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI failures do not print tracebacks or local paths."""
    output_path = tmp_path / "approved-db-import.jsonl"
    summary_path = tmp_path / "approved-db-import.summary.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "export_naver_tampermonkey_approved_db_import.py",
            "--input",
            str(tmp_path / "missing-review-ingest.jsonl"),
            "--output",
            str(output_path),
            "--summary",
            str(summary_path),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        approved_export.main()

    printed = capsys.readouterr().out
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert exc_info.value.code == 1
    assert "Traceback" not in printed
    assert str(tmp_path) not in printed
    assert str(tmp_path) not in json.dumps(summary, ensure_ascii=False)
    assert summary["status"] == "error"
    assert summary["error_code"] == "local_file_error"
    assert summary["input_name"] == "missing-review-ingest.jsonl"
    assert summary["output_name"] == "approved-db-import.jsonl"
    assert summary["raw_ocr_text_stored"] is False
    assert summary["local_path_literals_stored"] is False
