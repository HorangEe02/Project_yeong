"""Tests for dry-running approved Tampermonkey DB import candidates."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scripts import dry_run_naver_tampermonkey_approved_db_import as dry_run


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write JSONL test rows."""
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _approved_row(**overrides: object) -> dict[str, object]:
    """Return a minimal approved DB import row."""
    row: dict[str, object] = {
        "schema_version": "naver-tampermonkey-approved-db-import-v1",
        "source_provider": "naver_tampermonkey_review",
        "source_product_id": "a" * 64,
        "product_name": "Omega-3 1000",
        "normalized_product_name": "omega-3 1000",
        "manufacturer": "Reviewed Nutrition",
        "category": "omega_3",
        "source_manifest_version": "naver-tm-review-ingest-v1",
        "is_active": True,
        "is_clinical_recommendation": False,
        "clinical_recommendation_forbidden": True,
        "source_payload": {
            "fixture_id": "naver-tm-detail-000001",
            "review_task_id": "d" * 64,
            "image_sha256": "b" * 64,
            "image_ref_hash": "c" * 64,
            "language_targets": ["en", "ko"],
            "reviewer_id": "operator_1",
            "reviewed_at": "2026-05-24T14:30:00+09:00",
            "ocr_observation_count": 1,
            "ingredient_candidate_count": 1,
        },
        "ingredients": [
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
        ],
        "import_gate": {
            "ready_for_db_import": True,
            "human_review_approved": True,
            "pii_screening_completed": True,
        },
    }
    row.update(overrides)
    return row


def test_build_dry_run_import_plan_maps_to_orm_tables_without_db_write(
    tmp_path: Path,
) -> None:
    """Verify approved rows produce dry-run operations for ORM-backed tables."""
    input_path = tmp_path / "approved.jsonl"
    _write_jsonl(input_path, [_approved_row()])

    plan_rows, summary = dry_run.build_dry_run_import_plan(input_path=input_path)

    assert summary["schema_version"] == dry_run.SCHEMA_VERSION
    assert summary["planned_product_upsert_count"] == 1
    assert summary["planned_ingredient_row_count"] == 1
    assert summary["product_table"] == "supplement_products"
    assert summary["ingredient_table"] == "supplement_product_ingredients"
    assert summary["dry_run_only"] is True
    assert summary["db_write_performed"] is False
    product = plan_rows[0]["product"]
    assert isinstance(product, dict)
    assert product["table"] == "supplement_products"
    assert product["operation"] == "upsert"
    assert product["conflict_target"] == ["source_provider", "source_product_id"]
    assert product["product_name"] == "Omega-3 1000"
    assert "source_payload_hash" in product
    ingredient_plan = plan_rows[0]["ingredient_replace_plan"]
    assert isinstance(ingredient_plan, dict)
    assert ingredient_plan["table"] == "supplement_product_ingredients"
    assert ingredient_plan["ingredient_count"] == 1
    serialized = json.dumps(plan_rows, ensure_ascii=False).lower()
    assert "raw_ocr_text" not in serialized
    assert "provider_payload" not in serialized
    assert "/volumes/" not in serialized


def test_build_dry_run_import_plan_accepts_empty_approved_file(tmp_path: Path) -> None:
    """Verify current no-approved-row artifact remains a valid dry-run input."""
    input_path = tmp_path / "approved.jsonl"
    _write_jsonl(input_path, [])

    rows, summary = dry_run.build_dry_run_import_plan(input_path=input_path)

    assert rows == []
    assert summary["input_row_count"] == 0
    assert summary["planned_product_upsert_count"] == 0
    assert summary["db_write_performed"] is False


def test_build_dry_run_import_plan_rejects_duplicate_source_keys(tmp_path: Path) -> None:
    """Verify duplicate product conflict keys fail before DB import."""
    input_path = tmp_path / "approved.jsonl"
    _write_jsonl(input_path, [_approved_row(), _approved_row(product_name="Other")])

    with pytest.raises(ValueError, match="Duplicate source_provider"):
        dry_run.build_dry_run_import_plan(input_path=input_path)


def test_build_dry_run_import_plan_rejects_orm_length_violations(tmp_path: Path) -> None:
    """Verify reviewed values still must fit SupplementProduct column lengths."""
    input_path = tmp_path / "approved.jsonl"
    _write_jsonl(input_path, [_approved_row(product_name="x" * 241)])

    with pytest.raises(ValueError, match="product_name length"):
        dry_run.build_dry_run_import_plan(input_path=input_path)


def test_build_dry_run_import_plan_rejects_failed_import_gate(tmp_path: Path) -> None:
    """Verify approved import rows must keep all import gate flags true."""
    input_path = tmp_path / "approved.jsonl"
    row = _approved_row(
        import_gate={
            "ready_for_db_import": True,
            "human_review_approved": True,
            "pii_screening_completed": False,
        }
    )
    _write_jsonl(input_path, [row])

    with pytest.raises(ValueError, match="pii_screening_completed"):
        dry_run.build_dry_run_import_plan(input_path=input_path)


def test_build_dry_run_import_plan_rejects_raw_and_local_path_literals(
    tmp_path: Path,
) -> None:
    """Verify raw fields and local path literals cannot enter dry-run plans."""
    input_path = tmp_path / "approved.jsonl"
    _write_jsonl(input_path, [_approved_row(raw_ocr_text="do not persist")])

    with pytest.raises(ValueError, match="raw_ocr_text"):
        dry_run.build_dry_run_import_plan(input_path=input_path)

    input_path_2 = tmp_path / "approved-local.jsonl"
    _write_jsonl(input_path_2, [_approved_row(product_name="/Volumes/Corsair/a.jpg")])

    with pytest.raises(ValueError, match="local path literal"):
        dry_run.build_dry_run_import_plan(input_path=input_path_2)

    input_path_3 = tmp_path / "approved-private-local.jsonl"
    _write_jsonl(input_path_3, [_approved_row(product_name="/private/tmp/a.jpg")])

    with pytest.raises(ValueError, match="local path literal"):
        dry_run.build_dry_run_import_plan(input_path=input_path_3)


def test_build_dry_run_import_plan_rejects_non_object_rows_without_path_leak(
    tmp_path: Path,
) -> None:
    """Verify direct dry-run errors do not include the input path."""
    input_path = tmp_path / "approved.jsonl"
    input_path.write_text("[]\n", encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        dry_run.build_dry_run_import_plan(input_path=input_path)

    assert str(tmp_path) not in str(exc_info.value)
    assert str(input_path) not in str(exc_info.value)
    assert str(exc_info.value) == "JSONL rows must be objects."


def test_build_dry_run_import_plan_rejects_invalid_ingredient_amount(
    tmp_path: Path,
) -> None:
    """Verify ingredient amounts must fit the ORM Numeric(14, 6) boundary."""
    input_path = tmp_path / "approved.jsonl"
    row = _approved_row(
        ingredients=[
            {
                "standard_name": "Omega-3",
                "amount": "1.1234567",
                "sort_order": 0,
                "source_payload": {"reviewer_id": "operator_1"},
            }
        ]
    )
    _write_jsonl(input_path, [row])

    with pytest.raises(ValueError, match="Numeric"):
        dry_run.build_dry_run_import_plan(input_path=input_path)


def test_build_dry_run_import_plan_rejects_duplicate_ingredients(
    tmp_path: Path,
) -> None:
    """Verify handcrafted approved imports cannot duplicate child identities."""
    input_path = tmp_path / "approved.jsonl"
    base_ingredient = {
        "standard_name": "Omega-3",
        "nutrient_code": "omega_3",
        "amount": 1000.0,
        "unit": "mg",
        "sort_order": 0,
        "source_payload": {"reviewer_id": "operator_1"},
    }
    duplicate_ingredient = {
        **base_ingredient,
        "standard_name": " omega-3 ",
        "sort_order": 1,
    }
    _write_jsonl(
        input_path,
        [_approved_row(ingredients=[base_ingredient, duplicate_ingredient])],
    )

    with pytest.raises(ValueError, match="unique per product"):
        dry_run.build_dry_run_import_plan(input_path=input_path)


@pytest.mark.parametrize(
    "standard_name",
    [
        "g X30포(",
        "정x 3개입(",
        "1000mg",
        "60 capsules",
    ],
)
def test_build_dry_run_import_plan_rejects_packaging_quantity_ingredient_names(
    tmp_path: Path,
    standard_name: str,
) -> None:
    """Verify handcrafted approved imports cannot bypass package-count checks."""
    input_path = tmp_path / "approved.jsonl"
    row = _approved_row(
        ingredients=[
            {
                "standard_name": standard_name,
                "nutrient_code": "omega_3",
                "amount": 1000.0,
                "unit": "mg",
                "sort_order": 0,
                "source_payload": {"reviewer_id": "operator_1"},
            }
        ]
    )
    _write_jsonl(input_path, [row])

    with pytest.raises(ValueError, match="packaging quantity"):
        dry_run.build_dry_run_import_plan(input_path=input_path)


@pytest.mark.parametrize(
    "override",
    [
        {"product_name": "<script>alert(1)</script>"},
        {
            "ingredients": [
                {
                    "standard_name": "javascript:alert(1)",
                    "nutrient_code": "omega_3",
                    "amount": 1000.0,
                    "unit": "mg",
                    "sort_order": 0,
                    "source_payload": {"reviewer_id": "operator_1"},
                }
            ]
        },
        {
            "ingredients": [
                {
                    "standard_name": "Omega-3",
                    "nutrient_code": "omega_3",
                    "amount": 1000.0,
                    "unit": "https://example.test/unit",
                    "sort_order": 0,
                    "source_payload": {"reviewer_id": "operator_1"},
                }
            ]
        },
    ],
)
def test_build_dry_run_import_plan_rejects_executable_reviewed_text(
    tmp_path: Path,
    override: dict[str, object],
) -> None:
    """Verify handcrafted approved imports cannot carry executable text."""
    input_path = tmp_path / "approved.jsonl"
    _write_jsonl(input_path, [_approved_row(**override)])

    with pytest.raises(ValueError, match="executable or URL-like"):
        dry_run.build_dry_run_import_plan(input_path=input_path)


def test_main_error_is_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI failures do not print tracebacks or local paths."""
    input_path = tmp_path / "missing-approved.jsonl"
    output_path = tmp_path / "dry-run-plan.jsonl"
    summary_path = tmp_path / "dry-run-summary.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "dry_run_naver_tampermonkey_approved_db_import.py",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--summary",
            str(summary_path),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        dry_run.main()

    printed = capsys.readouterr().out
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert exc_info.value.code == 1
    assert "Traceback" not in printed
    assert str(tmp_path) not in printed
    assert str(tmp_path) not in json.dumps(summary, ensure_ascii=False)
    assert summary["status"] == "error"
    assert summary["error_code"] == "local_file_read_error"
    assert summary["error_message"] == "Local file read failed."
    assert summary["db_write_performed"] is False
    assert summary["local_path_literals_stored"] is False
    assert not output_path.exists()
