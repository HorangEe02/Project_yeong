"""Tests for exporting Tampermonkey DB-write approval templates."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scripts import check_ocr_artifact_privacy as privacy_check
from scripts import dry_run_naver_tampermonkey_approved_db_import as dry_run
from scripts import export_naver_tampermonkey_db_write_approval_template as exporter


def _write_json(path: Path, value: dict[str, object]) -> None:
    """Write one JSON object."""
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write JSONL test rows."""
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
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
            "reviewer_id": "operator_1",
            "reviewed_at": "2026-05-24T14:30:00+09:00",
        },
        "ingredients": [
            {
                "standard_name": "Omega-3",
                "nutrient_code": "omega_3",
                "amount": 1000.0,
                "unit": "mg",
                "sort_order": 0,
                "source_payload": {
                    "reviewer_id": "operator_1",
                    "reviewed_at": "2026-05-24T14:30:00+09:00",
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


def _prepare_evidence(tmp_path: Path) -> dict[str, Path]:
    """Create matching approved, dry-run, and privacy artifacts."""
    approved_path = tmp_path / "approved.jsonl"
    plan_path = tmp_path / "dry-run.jsonl"
    dry_summary_path = tmp_path / "dry-run.summary.json"
    privacy_path = tmp_path / "privacy.summary.json"
    _write_jsonl(approved_path, [_approved_row()])
    plan_rows, dry_summary = dry_run.build_dry_run_import_plan(input_path=approved_path)
    _write_jsonl(plan_path, plan_rows)
    _write_json(dry_summary_path, dry_summary)
    privacy_summary = privacy_check.check_artifact_privacy(
        paths=[approved_path, plan_path, dry_summary_path],
        strict_literal_keys=False,
    )
    _write_json(privacy_path, privacy_summary)
    return {
        "approved": approved_path,
        "plan": plan_path,
        "dry_summary": dry_summary_path,
        "privacy": privacy_path,
    }


def test_export_db_write_approval_template_is_non_importable(tmp_path: Path) -> None:
    """Verify template binds evidence but cannot be used as approval as-is."""
    paths = _prepare_evidence(tmp_path)

    template, summary = exporter.export_db_write_approval_template(
        approved_input_path=paths["approved"],
        dry_run_plan_path=paths["plan"],
        dry_run_summary_path=paths["dry_summary"],
        privacy_summary_path=paths["privacy"],
    )

    assert template["schema_version"] == exporter.SCHEMA_VERSION
    assert template["approval_log_schema_version"] == "naver-tampermonkey-db-write-approval-v1"
    assert template["approved_for_db_write"] is False
    assert template["reviewer_id"] == "operator_REQUIRED_SAFE_TOKEN"
    assert template["reviewer_id_required_prefix"] == "operator_"
    assert template["attest_dry_run_reviewed"] is False
    assert template["template_importable"] is False
    assert len(str(template["approved_input_sha256"])) == 64
    assert summary["template_importable"] is False
    assert summary["db_write_performed"] is False
    serialized = json.dumps({"template": template, "summary": summary}, ensure_ascii=False).lower()
    assert '"raw_ocr_text"' not in serialized
    assert "/volumes/" not in serialized


def test_export_db_write_approval_template_rejects_plan_drift(tmp_path: Path) -> None:
    """Verify template export fails when dry-run plan no longer matches input."""
    paths = _prepare_evidence(tmp_path)
    _write_jsonl(paths["plan"], [])

    with pytest.raises(ValueError, match="Dry-run plan"):
        exporter.export_db_write_approval_template(
            approved_input_path=paths["approved"],
            dry_run_plan_path=paths["plan"],
            dry_run_summary_path=paths["dry_summary"],
            privacy_summary_path=paths["privacy"],
        )


def test_export_db_write_approval_template_rejects_failed_privacy_summary(
    tmp_path: Path,
) -> None:
    """Verify approval templates require a passing privacy summary."""
    paths = _prepare_evidence(tmp_path)
    privacy_summary = json.loads(paths["privacy"].read_text(encoding="utf-8"))
    privacy_summary["passed"] = False
    privacy_summary["finding_count"] = 1
    _write_json(paths["privacy"], privacy_summary)

    with pytest.raises(ValueError, match="Privacy summary"):
        exporter.export_db_write_approval_template(
            approved_input_path=paths["approved"],
            dry_run_plan_path=paths["plan"],
            dry_run_summary_path=paths["dry_summary"],
            privacy_summary_path=paths["privacy"],
        )


def test_export_db_write_approval_template_main_error_is_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI failures print redacted JSON without local path literals."""
    output_path = tmp_path / "approval-template.json"
    summary_path = tmp_path / "approval-template.summary.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "export_naver_tampermonkey_db_write_approval_template.py",
            "--approved-input",
            str(tmp_path / "missing-approved.jsonl"),
            "--dry-run-plan",
            str(tmp_path / "missing-plan.jsonl"),
            "--dry-run-summary",
            str(tmp_path / "missing-summary.json"),
            "--privacy-summary",
            str(tmp_path / "missing-privacy.json"),
            "--output",
            str(output_path),
            "--summary",
            str(summary_path),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        exporter.main()

    stdout = capsys.readouterr().out
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert exc_info.value.code == 1
    assert summary["status"] == "error"
    assert summary["error_message"] == "Local file operation failed."
    assert "Traceback" not in stdout
    assert str(tmp_path) not in stdout
    assert str(tmp_path) not in json.dumps(summary, ensure_ascii=False)
