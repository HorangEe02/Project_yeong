"""inspection_logs ETL 모듈 — 단위·통합 테스트 (v4.3).

전제: features.equipment.inspection_db.init_inspection_db 가 checklist_templates 6 시드.
격리: tmp_path 로 inspection.db 격리.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════


@pytest.fixture
def tmp_inspection_db(monkeypatch, tmp_path):
    """격리 inspection.db. ETL 모듈의 경로 상수 monkeypatch."""
    db_path = tmp_path / "inspection.db"

    from features.equipment import inspection_db as idb
    monkeypatch.setattr(idb, "INSPECTION_DB_PATH", db_path)
    idb.init_inspection_db(db_path=db_path)

    # inspection_etl 모듈도 동일 경로 가리키도록 monkeypatch
    from features.equipment import inspection_etl as iet
    monkeypatch.setattr(iet, "INSPECTION_DB_PATH", db_path)

    return db_path


def _basic_csv(*, equipment_id="PR-101", template_code="프레스 일상점검",
               inspection_date=None, inspector="박지훈", status="PASS",
               results_json='[]', note="") -> bytes:
    insp_date = inspection_date or date.today().isoformat()
    rows = [
        "equipment_id,equipment_name,template_code,inspection_date,inspector,overall_status,results_json,note",
        f'{equipment_id},프레스 #1,{template_code},{insp_date},{inspector},{status},"{results_json}",{note}',
    ]
    return ("\n".join(rows) + "\n").encode("utf-8")


# ═══════════════════════════════════════════════════════════
# 단위 — header 정규화·검증
# ═══════════════════════════════════════════════════════════


def test_normalize_header_alias_korean():
    from features.equipment.inspection_etl import _normalize_header
    assert _normalize_header("설비ID") == "equipment_id"
    assert _normalize_header("점검일") == "inspection_date"
    assert _normalize_header("결과") == "overall_status"
    assert _normalize_header("﻿설비ID") == "equipment_id"  # BOM 허용
    assert _normalize_header("UNKNOWN_COLUMN") is None


def test_missing_required_columns_returns_error(tmp_inspection_db):
    from features.equipment.inspection_etl import ingest_csv

    csv = b"equipment_id,inspector\nPR-101,kim\n"
    result = ingest_csv(csv, source="test")
    assert result.rows_error == 1
    assert result.error_payload[0].error_code == "MISSING_COLUMN"


# ═══════════════════════════════════════════════════════════
# 통합 — INSERT / UPDATE / SKIP
# ═══════════════════════════════════════════════════════════


def test_basic_ingest_inserts_row(tmp_inspection_db):
    from features.equipment.inspection_etl import ingest_csv
    result = ingest_csv(_basic_csv(), source="test")
    assert result.rows_inserted == 1
    assert result.rows_error == 0

    with sqlite3.connect(tmp_inspection_db) as conn:
        cnt = conn.execute("SELECT COUNT(*) FROM inspection_logs").fetchone()[0]
        lineage = conn.execute(
            "SELECT data_class, source_system FROM inspection_logs"
        ).fetchone()
    assert cnt == 1
    assert lineage[0] == "synthetic"
    assert lineage[1] == "seed_equipment"


def test_duplicate_natural_key_skips(tmp_inspection_db):
    from features.equipment.inspection_etl import ingest_csv
    csv = _basic_csv()
    r1 = ingest_csv(csv, source="test")
    r2 = ingest_csv(csv, source="test")
    assert r1.rows_inserted == 1
    assert r2.rows_skipped == 1
    assert r2.rows_inserted == 0


def test_duplicate_natural_key_with_changed_results_updates(tmp_inspection_db):
    from features.equipment.inspection_etl import ingest_csv

    r1 = ingest_csv(_basic_csv(status="PASS"), source="test")
    r2 = ingest_csv(_basic_csv(status="WARN", note="유압 누유"), source="test")
    assert r1.rows_inserted == 1
    assert r2.rows_updated == 1

    with sqlite3.connect(tmp_inspection_db) as conn:
        row = conn.execute(
            "SELECT overall_status, note FROM inspection_logs"
        ).fetchone()
    assert row[0] == "WARN"
    assert row[1] == "유압 누유"


def test_future_date_rejected(tmp_inspection_db):
    from features.equipment.inspection_etl import ingest_csv
    future = (date.today() + timedelta(days=5)).isoformat()
    result = ingest_csv(_basic_csv(inspection_date=future), source="test")
    assert result.rows_error == 1
    assert result.error_payload[0].error_code == "INVALID_DATE"


def test_invalid_status_rejected(tmp_inspection_db):
    from features.equipment.inspection_etl import ingest_csv
    result = ingest_csv(_basic_csv(status="INVALID"), source="test")
    assert result.rows_error == 1
    assert result.error_payload[0].error_code == "INVALID_STATUS"


def test_unknown_template_rejected(tmp_inspection_db):
    from features.equipment.inspection_etl import ingest_csv
    result = ingest_csv(_basic_csv(template_code="존재하지않는템플릿"), source="test")
    assert result.rows_error == 1
    assert result.error_payload[0].error_code == "UNKNOWN_TEMPLATE"


def test_empty_inspector_rejected(tmp_inspection_db):
    from features.equipment.inspection_etl import ingest_csv
    result = ingest_csv(_basic_csv(inspector=""), source="test")
    assert result.rows_error == 1
    assert result.error_payload[0].error_code == "INSPECTOR_EMPTY"


def test_dry_run_does_not_persist(tmp_inspection_db):
    from features.equipment.inspection_etl import ingest_csv
    result = ingest_csv(_basic_csv(), source="test", dry_run=True)
    assert result.rows_inserted == 1
    assert result.dry_run is True

    with sqlite3.connect(tmp_inspection_db) as conn:
        cnt = conn.execute("SELECT COUNT(*) FROM inspection_logs").fetchone()[0]
    assert cnt == 0, "dry_run 시 DB 변동 금지"


def test_ingest_log_persists(tmp_inspection_db):
    from features.equipment.inspection_etl import ingest_csv, list_ingest_logs
    ingest_csv(_basic_csv(), source="test", actor="tester", file_name="x.csv")

    logs = list_ingest_logs(limit=5)
    assert len(logs) == 1
    assert logs[0]["source_label"] == "test"
    assert logs[0]["actor"] == "tester"
    assert logs[0]["file_name"] == "x.csv"
    assert logs[0]["rows_inserted"] == 1


def test_csv_upload_writes_real_lineage(tmp_inspection_db):
    from features.equipment.inspection_etl import ingest_csv

    ingest_csv(_basic_csv(inspector="실사용자"), source="csv_upload")
    with sqlite3.connect(tmp_inspection_db) as conn:
        row = conn.execute(
            "SELECT data_class, source_system, source_label FROM inspection_logs"
        ).fetchone()
    assert row[0] == "real"
    assert row[1] == "csv_upload"
    assert row[2] == "csv_upload"


# ═══════════════════════════════════════════════════════════
# PWA 단건 제출
# ═══════════════════════════════════════════════════════════


def test_submit_single_inserts(tmp_inspection_db):
    from features.equipment.inspection_etl import submit_single
    log_id, dedup = submit_single(
        equipment_id="PR-101",
        template_id=1,
        inspector="박지훈",
        inspection_date=date.today().isoformat(),
        results=[{"item_no": 1, "passed": True, "score": 95}],
        overall_status="PASS",
    )
    assert log_id > 0
    assert dedup is False


def test_submit_single_duplicate_marks_dedup(tmp_inspection_db):
    from features.equipment.inspection_etl import submit_single
    today = date.today().isoformat()
    _, d1 = submit_single(
        equipment_id="PR-101", template_id=1, inspector="박지훈",
        inspection_date=today, results=[], overall_status="PASS",
    )
    _, d2 = submit_single(
        equipment_id="PR-101", template_id=1, inspector="박지훈",
        inspection_date=today, results=[], overall_status="PASS",
    )
    assert d1 is False
    assert d2 is True


def test_submit_single_deduplicates_by_client_uuid(tmp_inspection_db):
    """Offline queue retries should deduplicate by client_uuid before natural key."""
    from features.equipment.inspection_etl import submit_single

    today = date.today().isoformat()
    first_id, first_dedup = submit_single(
        equipment_id="PR-101",
        template_id=1,
        inspector="박지훈",
        inspection_date=today,
        results=[],
        overall_status="PASS",
        client_uuid="field-device-uuid-1",
    )
    second_id, second_dedup = submit_single(
        equipment_id="PR-999",
        template_id=1,
        inspector="박지훈",
        inspection_date=today,
        results=[],
        overall_status="WARN",
        client_uuid="field-device-uuid-1",
    )

    assert first_dedup is False
    assert second_dedup is True
    assert second_id == first_id
    with sqlite3.connect(tmp_inspection_db) as conn:
        rows = conn.execute(
            "SELECT equipment_id, client_uuid FROM inspection_logs"
        ).fetchall()
    assert rows == [("PR-101", "field-device-uuid-1")]
