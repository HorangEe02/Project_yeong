"""tests/test_admin_bulk_create.py — v4.8 F.

features.admin.bulk_create 의 CSV 파싱 + dry_run + 자연키 SKIP + role_level
검증. 실 auth.db 를 건드리지 않도록 dry_run=True 만 사용.
"""
from __future__ import annotations

import pytest

from features.admin.bulk_create import (
    CSV_COLUMNS,
    ingest_users_csv,
    parse_csv,
)


SAMPLE_CSV = (
    "username,email,name,department,position,role_level,phone\n"
    "hong,hong@ajin.com,홍길동,IT전략팀,주임,1,010-1111-1111\n"
    "jane,jane@ajin.com,제인,IT전략팀,대리,2,\n"
).encode("utf-8")


def test_csv_columns_are_canonical():
    assert CSV_COLUMNS == [
        "username", "email", "name", "department", "position", "role_level", "phone",
    ]


def test_parse_csv_returns_normalized_rows():
    rows = parse_csv(SAMPLE_CSV)
    assert len(rows) == 2
    assert rows[0]["username"] == "hong"
    assert rows[0]["role_level"] == "1"
    # 헤더 케이스 정규화 (lowercase + strip).
    assert all(k == k.strip().lower() for k in rows[0].keys())


def test_dry_run_valid_rows_zero_errors():
    res = ingest_users_csv(SAMPLE_CSV, dry_run=True)
    assert res.dry_run is True
    assert res.rows_total == 2
    assert res.rows_inserted == 0  # dry_run 이므로
    assert res.rows_error == 0
    assert res.error_payload == []


def test_dry_run_invalid_role_level_flags_error():
    bad_csv = (
        "username,email,name,department,position,role_level,phone\n"
        "bad,bad@a.com,Bad,IT전략팀,주임,99,\n"
    ).encode("utf-8")
    res = ingest_users_csv(bad_csv, dry_run=True)
    assert res.rows_total == 1
    assert res.rows_error == 1
    assert res.error_payload[0].error_code == "validation"
    assert "role_level" in res.error_payload[0].error_msg


def test_dry_run_invalid_department_flags_error():
    bad_csv = (
        "username,email,name,department,position,role_level,phone\n"
        "bad,bad@a.com,Bad,NONEXISTDEPT,주임,1,\n"
    ).encode("utf-8")
    res = ingest_users_csv(bad_csv, dry_run=True)
    assert res.rows_total == 1
    assert res.rows_error == 1
    assert "부서" in res.error_payload[0].error_msg


def test_dry_run_missing_email_flags_error():
    bad_csv = (
        "username,email,name,department,position,role_level,phone\n"
        "bad,,Bad,IT전략팀,주임,1,\n"
    ).encode("utf-8")
    res = ingest_users_csv(bad_csv, dry_run=True)
    assert res.rows_total == 1
    assert res.rows_error == 1


def test_dry_run_bad_email_format_flags_error():
    bad_csv = (
        "username,email,name,department,position,role_level,phone\n"
        "bad,not-an-email,Bad,IT전략팀,주임,1,\n"
    ).encode("utf-8")
    res = ingest_users_csv(bad_csv, dry_run=True)
    assert res.rows_total == 1
    assert res.rows_error == 1


def test_parse_csv_handles_bom():
    csv_with_bom = b"\xef\xbb\xbf" + SAMPLE_CSV
    rows = parse_csv(csv_with_bom)
    assert len(rows) == 2
    assert rows[0]["username"] == "hong"


def test_ingest_empty_csv_returns_zero():
    csv_only_header = "username,email,name,department,position,role_level,phone\n".encode("utf-8")
    res = ingest_users_csv(csv_only_header, dry_run=True)
    assert res.rows_total == 0
    assert res.rows_error == 0


def test_bulk_csv_writes_real_lineage(tmp_path, monkeypatch):
    from core.auth import database as auth_db

    db_path = tmp_path / "auth.db"
    monkeypatch.setattr(auth_db, "AUTH_DB_PATH", db_path)
    auth_db.init_auth_db()

    res = ingest_users_csv(SAMPLE_CSV, dry_run=False, actor_employee_id="HR-0001")
    assert res.rows_inserted == 2

    conn = auth_db.get_auth_db()
    try:
        rows = conn.execute(
            "SELECT data_class, source_system, source_label FROM users WHERE source_system='bulk_csv'"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 2
    assert all(row["data_class"] == "real" for row in rows)
    assert all(row["source_label"] == "bulk_csv:HR-0001" for row in rows)
