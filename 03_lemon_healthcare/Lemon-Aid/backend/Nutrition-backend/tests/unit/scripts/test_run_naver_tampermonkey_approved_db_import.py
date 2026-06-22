"""Tests for the approved Naver Tampermonkey DB import runner."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from src.models.db.supplement import SupplementProduct

from scripts import check_ocr_artifact_privacy as privacy_check
from scripts import dry_run_naver_tampermonkey_approved_db_import as dry_run
from scripts import export_naver_tampermonkey_db_write_approval_template as template_exporter
from scripts import run_naver_tampermonkey_approved_db_import as importer


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


def _prepare_evidence(
    tmp_path: Path,
    *,
    rows: list[dict[str, object]] | None = None,
    approval_overrides: dict[str, object] | None = None,
    privacy_overrides: dict[str, object] | None = None,
) -> dict[str, Path]:
    """Create matching approved, dry-run, privacy, and approval artifacts."""
    approved_path = tmp_path / "approved.jsonl"
    plan_path = tmp_path / "dry-run.jsonl"
    dry_summary_path = tmp_path / "dry-run.summary.json"
    privacy_path = tmp_path / "privacy.summary.json"
    approval_path = tmp_path / "approval-log.json"
    approved_rows = rows if rows is not None else [_approved_row()]
    _write_jsonl(approved_path, approved_rows)
    plan_rows, dry_summary = dry_run.build_dry_run_import_plan(input_path=approved_path)
    _write_jsonl(plan_path, plan_rows)
    _write_json(dry_summary_path, dry_summary)
    privacy_summary = privacy_check.check_artifact_privacy(
        paths=[approved_path, plan_path, dry_summary_path],
        strict_literal_keys=False,
    )
    if privacy_overrides:
        privacy_summary.update(privacy_overrides)
    _write_json(privacy_path, privacy_summary)
    approval_log: dict[str, object] = {
        "schema_version": importer.APPROVAL_LOG_SCHEMA_VERSION,
        "approved_for_db_write": True,
        "reviewer_id": "operator_1",
        "approved_at": "2026-05-24T14:40:00Z",
        "approved_input_sha256": importer._sha256_file(approved_path),
        "dry_run_plan_sha256": importer._sha256_file(plan_path),
        "dry_run_summary_sha256": importer._sha256_file(dry_summary_path),
        "privacy_summary_sha256": importer._sha256_file(privacy_path),
        "planned_product_upsert_count": dry_summary["planned_product_upsert_count"],
        "planned_ingredient_row_count": dry_summary["planned_ingredient_row_count"],
        "attest_dry_run_reviewed": True,
        "attest_privacy_scan_passed": True,
        "attest_reviewer_approved": True,
        "attest_not_clinical_recommendation": True,
    }
    if approval_overrides:
        approval_log.update(approval_overrides)
    _write_json(approval_path, approval_log)
    return {
        "approved": approved_path,
        "plan": plan_path,
        "dry_summary": dry_summary_path,
        "privacy": privacy_path,
        "approval": approval_path,
    }


def test_build_import_preflight_accepts_matching_evidence(tmp_path: Path) -> None:
    """Verify all evidence gates pass without opening a database session."""
    paths = _prepare_evidence(tmp_path)

    rows, summary = importer.build_import_preflight(
        approved_input_path=paths["approved"],
        dry_run_plan_path=paths["plan"],
        dry_run_summary_path=paths["dry_summary"],
        privacy_summary_path=paths["privacy"],
        approval_log_path=paths["approval"],
    )

    assert len(rows) == 1
    assert summary["ready_for_db_write"] is True
    assert summary["db_write_performed"] is False
    assert summary["planned_product_upsert_count"] == 1
    assert summary["planned_ingredient_row_count"] == 1
    serialized = json.dumps(summary, ensure_ascii=False).lower()
    assert '"raw_ocr_text"' not in serialized
    assert "/volumes/" not in serialized


def test_build_import_preflight_rejects_hash_mismatch(tmp_path: Path) -> None:
    """Verify reviewer approval must bind to exact evidence file hashes."""
    paths = _prepare_evidence(
        tmp_path,
        approval_overrides={"dry_run_plan_sha256": "0" * 64},
    )

    with pytest.raises(ValueError, match="dry_run_plan_sha256"):
        importer.build_import_preflight(
            approved_input_path=paths["approved"],
            dry_run_plan_path=paths["plan"],
            dry_run_summary_path=paths["dry_summary"],
            privacy_summary_path=paths["privacy"],
            approval_log_path=paths["approval"],
        )


def test_build_import_preflight_rejects_failed_privacy_summary(tmp_path: Path) -> None:
    """Verify DB write cannot proceed after privacy scan findings."""
    paths = _prepare_evidence(
        tmp_path,
        privacy_overrides={"passed": False, "finding_count": 1},
    )

    with pytest.raises(ValueError, match="Privacy summary"):
        importer.build_import_preflight(
            approved_input_path=paths["approved"],
            dry_run_plan_path=paths["plan"],
            dry_run_summary_path=paths["dry_summary"],
            privacy_summary_path=paths["privacy"],
            approval_log_path=paths["approval"],
        )


def test_build_import_preflight_rejects_model_only_db_write_reviewer(
    tmp_path: Path,
) -> None:
    """Verify DB-write approval requires an operator reviewer id."""
    paths = _prepare_evidence(
        tmp_path,
        approval_overrides={"reviewer_id": "ollama_gemma4"},
    )

    with pytest.raises(ValueError, match="reviewer_id must start with operator_"):
        importer.build_import_preflight(
            approved_input_path=paths["approved"],
            dry_run_plan_path=paths["plan"],
            dry_run_summary_path=paths["dry_summary"],
            privacy_summary_path=paths["privacy"],
            approval_log_path=paths["approval"],
        )


@pytest.mark.parametrize(
    "approved_at",
    [
        "2026-05-24T14:40:00",
        "2026-05-24T23:40:00+09:00",
        "not-a-date",
    ],
)
def test_build_import_preflight_rejects_non_utc_approval_timestamp(
    tmp_path: Path,
    approved_at: str,
) -> None:
    """Verify DB-write approval timestamps must be UTC ISO-8601."""
    paths = _prepare_evidence(
        tmp_path,
        approval_overrides={"approved_at": approved_at},
    )

    with pytest.raises(ValueError, match="approved_at must be UTC ISO-8601"):
        importer.build_import_preflight(
            approved_input_path=paths["approved"],
            dry_run_plan_path=paths["plan"],
            dry_run_summary_path=paths["dry_summary"],
            privacy_summary_path=paths["privacy"],
            approval_log_path=paths["approval"],
        )


def test_build_import_preflight_rejects_non_importable_template(tmp_path: Path) -> None:
    """Verify approval templates cannot be used as approval logs directly."""
    paths = _prepare_evidence(tmp_path)
    template, _summary = template_exporter.export_db_write_approval_template(
        approved_input_path=paths["approved"],
        dry_run_plan_path=paths["plan"],
        dry_run_summary_path=paths["dry_summary"],
        privacy_summary_path=paths["privacy"],
    )
    _write_json(paths["approval"], template)

    with pytest.raises(ValueError, match="Approval log contains unsupported"):
        importer.build_import_preflight(
            approved_input_path=paths["approved"],
            dry_run_plan_path=paths["plan"],
            dry_run_summary_path=paths["dry_summary"],
            privacy_summary_path=paths["privacy"],
            approval_log_path=paths["approval"],
        )


@pytest.mark.asyncio
async def test_run_import_defaults_to_preflight_only(tmp_path: Path) -> None:
    """Verify DB write is opt-in even when all evidence passes."""
    paths = _prepare_evidence(tmp_path)

    summary = await importer.run_import(
        approved_input_path=paths["approved"],
        dry_run_plan_path=paths["plan"],
        dry_run_summary_path=paths["dry_summary"],
        privacy_summary_path=paths["privacy"],
        approval_log_path=paths["approval"],
        execute_db_write=False,
    )

    assert summary["ready_for_db_write"] is True
    assert summary["preflight_only"] is True
    assert summary["execute_db_write_requested"] is False
    assert summary["db_write_performed"] is False
    assert summary["imported_product_count"] == 0


class _FakeSession:
    """Minimal async session double for import_approved_rows."""

    def __init__(self, existing_product: SupplementProduct | None = None) -> None:
        """Initialize fake session state."""
        self.existing_product = existing_product
        self.added: list[object] = []
        self.executed_count = 0
        self.flushed_count = 0
        self.committed = False
        self.rolled_back = False

    async def scalar(self, _statement: object) -> SupplementProduct | None:
        """Return the configured existing product."""
        return self.existing_product

    def add(self, value: object) -> None:
        """Record added ORM object."""
        self.added.append(value)

    async def execute(self, _statement: object) -> None:
        """Record child replacement delete execution."""
        self.executed_count += 1

    async def flush(self) -> None:
        """Assign product ids like an ORM flush would."""
        self.flushed_count += 1
        for value in self.added:
            if isinstance(value, SupplementProduct) and value.id is None:
                value.id = uuid4()

    async def commit(self) -> None:
        """Record commit."""
        self.committed = True

    async def rollback(self) -> None:
        """Record rollback."""
        self.rolled_back = True


@pytest.mark.asyncio
async def test_import_approved_rows_upserts_product_and_replaces_ingredients() -> None:
    """Verify DB import writes reviewed product values and replaces child rows."""
    existing = SupplementProduct(
        id=uuid4(),
        source_provider="naver_tampermonkey_review",
        source_product_id="a" * 64,
        product_name="Old",
        normalized_product_name="old",
        source_payload={},
        is_active=True,
    )
    session = _FakeSession(existing_product=existing)

    summary = await importer.import_approved_rows(
        session=session,  # type: ignore[arg-type]
        approved_rows=[_approved_row(product_name="New Omega")],
    )

    assert summary == {"imported_product_count": 1, "imported_ingredient_count": 1}
    assert existing.product_name == "New Omega"
    assert session.executed_count == 1
    assert session.committed is True
    assert session.rolled_back is False
    assert len(session.added) == 1


def test_main_error_is_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI failure summary avoids traceback and local path literals."""
    summary_path = tmp_path / "summary.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_naver_tampermonkey_approved_db_import.py",
            "--approved-input",
            str(tmp_path / "missing-approved.jsonl"),
            "--dry-run-plan",
            str(tmp_path / "missing-plan.jsonl"),
            "--dry-run-summary",
            str(tmp_path / "missing-summary.json"),
            "--privacy-summary",
            str(tmp_path / "missing-privacy.json"),
            "--approval-log",
            str(tmp_path / "missing-approval.json"),
            "--summary",
            str(summary_path),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        importer.main()

    stdout = capsys.readouterr().out
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert exc_info.value.code == 1
    assert summary["status"] == "error"
    assert summary["error_message"] == "Local file operation failed."
    assert "Traceback" not in stdout
    assert str(tmp_path) not in stdout
    assert str(tmp_path) not in json.dumps(summary, ensure_ascii=False)
