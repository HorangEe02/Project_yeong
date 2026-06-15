"""Feature A Sprint 1 P0 — 단위/통합 테스트.

Coverage:
  - core.directory.migrations: idempotent ALTER, IF NOT EXISTS 처리
  - core.directory.canonical: headcount, reconcile, snapshot
  - features.search.adapters.csv_erp_adapter: CSV parse + iter + lookup
  - features.search.adapters.sync_runner: insert / unchanged / dry-run

격리된 tmp DB 사용 — 운영 data/*.db 미오염.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from textwrap import dedent

import pytest

from core.directory import migrations as dir_migrations
from core.directory.canonical import CanonicalDirectory
from features.search.adapters import sync_runner
from features.search.adapters.csv_erp_adapter import CsvErpAdapter
from features.search.adapters.erp_adapter import (
    EmployeeRecord,
    ErpAdapter,
    MockErpAdapter,
    get_erp_adapter,
    reset_erp_adapter,
)


# ─────────────────────────────────────────────────────────
# Fixtures — 격리된 employees / auth / audit DB
# ─────────────────────────────────────────────────────────


def _seed_employees_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    conn.executescript(dedent(
        """
        CREATE TABLE employees (
            employee_id     TEXT PRIMARY KEY,
            name            TEXT NOT NULL,
            position        TEXT NOT NULL,
            position_level  INTEGER NOT NULL,
            division        TEXT NOT NULL,
            department      TEXT NOT NULL,
            email           TEXT,
            phone           TEXT,
            plant           TEXT,
            hire_date       TEXT,
            is_active       INTEGER DEFAULT 1
        );
        INSERT INTO employees (employee_id, name, position, position_level, division, department, is_active)
        VALUES
            ('AJ-001', '김합성', '사원', 1, '관리본부', '인사팀', 1),
            ('AJ-002', '이합성', '대리', 3, '관리본부', '인사팀', 1),
            ('AJ-003', '박합성', '과장', 4, '품질본부', '품질보증팀', 0);
        """
    ))
    conn.commit()
    conn.close()


def _seed_auth_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    conn.executescript(dedent(
        """
        CREATE TABLE users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL UNIQUE,
            username TEXT,
            is_active INTEGER DEFAULT 1
        );
        INSERT INTO users (employee_id, username) VALUES
            ('AJ-001', 'kim'),
            ('AJ-002', 'lee');
        """
    ))
    conn.commit()
    conn.close()


def _seed_audit_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    conn.executescript(dedent(
        """
        CREATE TABLE api_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            endpoint TEXT NOT NULL,
            method TEXT NOT NULL DEFAULT 'GET',
            status_code INTEGER DEFAULT 200,
            timestamp TEXT DEFAULT (datetime('now'))
        );
        """
    ))
    conn.commit()
    conn.close()


@pytest.fixture
def tmp_dbs(tmp_path: Path, monkeypatch):
    """Isolated employees/auth/audit DBs + monkeypatched paths."""
    emp = tmp_path / "employees.db"
    auth = tmp_path / "auth.db"
    audit = tmp_path / "audit.db"
    _seed_employees_db(emp)
    _seed_auth_db(auth)
    _seed_audit_db(audit)

    monkeypatch.setattr(dir_migrations, "EMPLOYEES_DB", emp)
    monkeypatch.setattr(dir_migrations, "AUTH_DB", auth)
    monkeypatch.setattr(dir_migrations, "AUDIT_DB", audit)
    return {"employees": emp, "auth": auth, "audit": audit}


# ─────────────────────────────────────────────────────────
# Migration idempotency
# ─────────────────────────────────────────────────────────


def test_migration_applies_all_three_dbs(tmp_dbs):
    result = dir_migrations.apply_all()
    assert result["employees"] >= 6
    assert result["auth"] >= 1
    assert result["audit"] >= 4


def test_migration_is_idempotent(tmp_dbs):
    dir_migrations.apply_all()  # first run
    # second run must not raise; ALTER ADD COLUMN should be skipped.
    # IF NOT EXISTS statements always "succeed" (counted) — ALTERs are now skipped.
    # Total statement count after Feature B added mail_audit_log = 8 (3 ALTER + 1 idx + 1 CREATE + 3 idx).
    # 2회차에서 ALTER 3개는 skip 되므로 audit 결과 <= 8.
    result = dir_migrations.apply_all()
    assert result["audit"] <= len(dir_migrations.AUDIT_MIGRATIONS)


def test_migration_adds_is_synthetic_column(tmp_dbs):
    dir_migrations.apply_all()
    conn = sqlite3.connect(str(tmp_dbs["employees"]))
    cols = {row[1] for row in conn.execute("PRAGMA table_info(employees)").fetchall()}
    conn.close()
    assert "is_synthetic" in cols
    assert "source_system" in cols
    assert "canonical_employee_id" in cols
    assert "data_class" in cols
    assert "source_label" in cols
    assert "source_updated_at" in cols


def test_migration_adds_audit_latency_column(tmp_dbs):
    dir_migrations.apply_all()
    conn = sqlite3.connect(str(tmp_dbs["audit"]))
    cols = {row[1] for row in conn.execute("PRAGMA table_info(api_audit_log)").fetchall()}
    conn.close()
    assert "latency_ms" in cols
    assert "intent" in cols
    assert "result_count" in cols


def test_migration_creates_headcount_and_search_history(tmp_dbs):
    dir_migrations.apply_all()
    conn = sqlite3.connect(str(tmp_dbs["employees"]))
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    assert "headcount_snapshot" in tables
    assert "search_history" in tables


# ─────────────────────────────────────────────────────────
# CanonicalDirectory
# ─────────────────────────────────────────────────────────


def test_canonical_total_headcount_excludes_inactive(tmp_dbs):
    dir_migrations.apply_all()
    cd = CanonicalDirectory(employees_db=tmp_dbs["employees"], auth_db=tmp_dbs["auth"])
    # seed: 3 rows, 1 inactive → 2 active
    assert cd.get_total_headcount() == 2


def test_canonical_synthetic_real_split(tmp_dbs):
    dir_migrations.apply_all()
    # Mark AJ-001 as real (is_synthetic = 0)
    conn = sqlite3.connect(str(tmp_dbs["employees"]))
    conn.execute("UPDATE employees SET is_synthetic = 0 WHERE employee_id = 'AJ-001'")
    conn.commit()
    conn.close()

    cd = CanonicalDirectory(employees_db=tmp_dbs["employees"], auth_db=tmp_dbs["auth"])
    summary = cd.headcount_summary()
    assert summary.total_active == 2
    assert summary.real_count == 1
    assert summary.synthetic_count == 1


def test_canonical_reconcile_detects_gap(tmp_dbs):
    dir_migrations.apply_all()
    cd = CanonicalDirectory(employees_db=tmp_dbs["employees"], auth_db=tmp_dbs["auth"])
    report = cd.reconcile()
    # 2 active employees vs 2 active users → no auth gap.
    # But config.py has total_employees=649 → has_gap True.
    assert report.employees_active == 2
    assert report.auth_users_active == 2
    # config_total comes from import; production may be 649 or None.
    if report.config_total is not None:
        assert report.has_gap == (report.config_total != report.employees_active)


def test_canonical_resolve_user_to_employee(tmp_dbs):
    dir_migrations.apply_all()
    cd = CanonicalDirectory(employees_db=tmp_dbs["employees"], auth_db=tmp_dbs["auth"])
    emp = cd.resolve_user_to_employee(1)  # user_id=1 → AJ-001
    assert emp is not None
    assert emp["employee_id"] == "AJ-001"
    assert emp["name"] == "김합성"


def test_canonical_take_snapshot_inserts_row(tmp_dbs):
    dir_migrations.apply_all()
    cd = CanonicalDirectory(employees_db=tmp_dbs["employees"], auth_db=tmp_dbs["auth"])
    snap = cd.take_snapshot()
    assert snap["total_active"] == 2
    # Idempotent — same date INSERT OR REPLACE
    cd.take_snapshot()
    conn = sqlite3.connect(str(tmp_dbs["employees"]))
    n = conn.execute("SELECT COUNT(*) FROM headcount_snapshot").fetchone()[0]
    conn.close()
    assert n == 1


# ─────────────────────────────────────────────────────────
# CsvErpAdapter
# ─────────────────────────────────────────────────────────


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    p = tmp_path / "erp.csv"
    p.write_text(
        "canonical_id,name,email,department,position,position_level,is_active\n"
        "ERP-001,홍길동,hong@x,품질팀,과장,4,1\n"
        "ERP-002,임꺽정,im@x,정비팀,대리,3,1\n"
        "ERP-003,장보고,jang@x,영업팀,부장,6,0\n",
        encoding="utf-8",
    )
    return p


def test_csv_adapter_iter_employees(sample_csv):
    a = CsvErpAdapter(csv_path=sample_csv)
    records = list(a.iter_employees())
    assert len(records) == 3
    assert records[0].canonical_employee_id == "ERP-001"
    assert records[0].department == "품질팀"
    assert records[2].is_active is False  # 장보고


def test_csv_adapter_lookup_by_canonical(sample_csv):
    a = CsvErpAdapter(csv_path=sample_csv)
    rec = a.fetch_employee_by_canonical_id("ERP-002")
    assert rec is not None
    assert rec.name == "임꺽정"
    assert a.fetch_employee_by_canonical_id("ERP-9999") is None


def test_csv_adapter_extras_permission_branching(sample_csv):
    a = CsvErpAdapter(csv_path=sample_csv)
    # role_level ≥ 5 → FULL
    ext_full = a.fetch_extras("T", "V", 5, None, None)
    assert ext_full.permission == "FULL"
    # same department → PARTIAL
    ext_partial = a.fetch_extras("T", "V", 1, "X", "X")
    assert ext_partial.permission == "PARTIAL"
    # other → DENIED
    ext_denied = a.fetch_extras("T", "V", 1, "X", "Y")
    assert ext_denied.permission == "DENIED"


def test_csv_adapter_missing_csv_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        CsvErpAdapter(csv_path=tmp_path / "does_not_exist.csv")


# ─────────────────────────────────────────────────────────
# Adapter contract — Mock vs Csv 동일 EmployeeExtras 스키마
# ─────────────────────────────────────────────────────────


def test_mock_vs_csv_extras_contract(sample_csv):
    mock = MockErpAdapter()
    csv_a = CsvErpAdapter(csv_path=sample_csv)
    m = mock.fetch_extras("T", "V", 5, "X", "X").to_dict()
    c = csv_a.fetch_extras("T", "V", 5, "X", "X").to_dict()
    assert set(m.keys()) == set(c.keys())


# ─────────────────────────────────────────────────────────
# get_erp_adapter env branching
# ─────────────────────────────────────────────────────────


def test_get_erp_adapter_mock_default(monkeypatch):
    monkeypatch.delenv("AJIN_ERP_MODE", raising=False)
    reset_erp_adapter()
    a = get_erp_adapter()
    assert isinstance(a, MockErpAdapter)


def test_get_erp_adapter_csv_branch(monkeypatch, sample_csv):
    monkeypatch.setenv("AJIN_ERP_MODE", "csv")
    monkeypatch.setenv("AJIN_ERP_CSV_PATH", str(sample_csv))
    reset_erp_adapter()
    a = get_erp_adapter()
    assert isinstance(a, CsvErpAdapter)
    assert len(list(a.iter_employees())) == 3


def test_get_erp_adapter_unknown_mode_raises(monkeypatch):
    monkeypatch.setenv("AJIN_ERP_MODE", "rest")  # Sprint 2 까지 미지원
    reset_erp_adapter()
    with pytest.raises(ValueError):
        get_erp_adapter()


# ─────────────────────────────────────────────────────────
# sync_runner — upsert + idempotency
# ─────────────────────────────────────────────────────────


class _StaticAdapter(ErpAdapter):
    """Test double — yields a fixed set of EmployeeRecords."""

    def __init__(self, records):
        self._records = records

    def fetch_extras(self, *a, **kw):  # pragma: no cover — sync runner unused
        raise NotImplementedError

    def fetch_employee_by_canonical_id(self, canonical_id):  # pragma: no cover
        for r in self._records:
            if r.canonical_employee_id == canonical_id:
                return r
        return None

    def iter_employees(self):
        return iter(self._records)


def test_sync_runner_inserts_new_rows(tmp_dbs):
    dir_migrations.apply_all()
    recs = [
        EmployeeRecord(
            canonical_employee_id="ERP-001",
            name="홍길동",
            email="hong@x",
            department="품질팀",
            division="품질본부",
            position="과장",
            position_level=4,
            is_active=True,
        ),
        EmployeeRecord(
            canonical_employee_id="ERP-002",
            name="임꺽정",
            department="정비팀",
            division="생산본부",
            position="대리",
            position_level=3,
            is_active=True,
        ),
    ]
    report = sync_runner.run(adapter=_StaticAdapter(recs), db_path=tmp_dbs["employees"])
    assert report.inserted == 2
    assert report.updated == 0
    assert report.errors == []
    # row 확인 — ERP CSV rows are real and no longer use the legacy source_system='erp'.
    conn = sqlite3.connect(str(tmp_dbs["employees"]))
    rows = conn.execute(
        "SELECT canonical_employee_id, source_system, is_synthetic, data_class "
        "FROM employees WHERE source_system = 'erp_csv'"
    ).fetchall()
    conn.close()
    assert len(rows) == 2
    assert all(r[1] == "erp_csv" and r[2] == 0 and r[3] == "real" for r in rows)


def test_sync_runner_idempotent(tmp_dbs):
    dir_migrations.apply_all()
    recs = [
        EmployeeRecord(
            canonical_employee_id="ERP-001",
            name="홍길동",
            department="품질팀",
            division="품질본부",
            position="과장",
            position_level=4,
            is_active=True,
        ),
    ]
    sync_runner.run(adapter=_StaticAdapter(recs), db_path=tmp_dbs["employees"])
    r2 = sync_runner.run(adapter=_StaticAdapter(recs), db_path=tmp_dbs["employees"])
    assert r2.inserted == 0
    assert r2.unchanged == 1


def test_sync_runner_dry_run_does_not_commit(tmp_dbs):
    dir_migrations.apply_all()
    recs = [
        EmployeeRecord(
            canonical_employee_id="ERP-001",
            name="홍길동",
            department="품질팀",
            division="품질본부",
            position="과장",
            position_level=4,
            is_active=True,
        ),
    ]
    r = sync_runner.run(
        adapter=_StaticAdapter(recs),
        dry_run=True,
        db_path=tmp_dbs["employees"],
    )
    assert r.inserted == 1
    # DB should NOT have the row
    conn = sqlite3.connect(str(tmp_dbs["employees"]))
    n = conn.execute(
        "SELECT COUNT(*) FROM employees WHERE canonical_employee_id = 'ERP-001'"
    ).fetchone()[0]
    conn.close()
    assert n == 0


def test_sync_runner_skips_malformed_records(tmp_dbs):
    dir_migrations.apply_all()
    recs = [
        EmployeeRecord(canonical_employee_id="", name="bad"),  # empty id
        EmployeeRecord(canonical_employee_id="ERP-X", name=""),  # empty name
    ]
    r = sync_runner.run(adapter=_StaticAdapter(recs), db_path=tmp_dbs["employees"])
    assert r.skipped == 2
    assert r.inserted == 0
