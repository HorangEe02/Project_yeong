"""ERP → employees.db sync runner (Sprint 1 P0 PoC).

Reads `EmployeeRecord` from the configured ErpAdapter (env AJIN_ERP_MODE)
and upserts into employees.db, marking rows as real ERP CSV data
(`source_system='erp_csv'`, `is_synthetic=0`). Matches existing rows by
`canonical_employee_id`.

Usage:
    # nightly full sync (env: AJIN_ERP_MODE=csv, AJIN_ERP_CSV_PATH=...)
    python -m features.search.adapters.sync_runner

    # dry-run — print planned changes, do not commit
    python -m features.search.adapters.sync_runner --dry-run

Exits non-zero on error. Sprint 2 wires this into Celery beat (nightly 01:00).
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from dataclasses import dataclass, field
from typing import Iterable

from core.data_lineage import ensure_lineage_columns, lineage_values
from core.directory.migrations import EMPLOYEES_DB
from features.search.adapters.erp_adapter import (
    EmployeeRecord,
    ErpAdapter,
    get_erp_adapter,
)

logger = logging.getLogger(__name__)


@dataclass
class SyncReport:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.inserted + self.updated + self.unchanged + self.skipped

    def to_dict(self) -> dict:
        return {
            "inserted": self.inserted,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "skipped": self.skipped,
            "errors": self.errors,
            "total": self.total,
        }


# 컬럼 매핑: EmployeeRecord 필드 → employees 테이블 컬럼
RECORD_TO_COLUMN = {
    "name": "name",
    "email": "email",
    "phone": "phone",
    "department": "department",
    "division": "division",
    "position": "position",
    "position_level": "position_level",
    "plant": "plant",
    "hire_date": "hire_date",
    "is_active": "is_active",
}


def _record_to_row(rec: EmployeeRecord) -> dict[str, object]:
    """EmployeeRecord → INSERT/UPDATE dict (NULL 컬럼 제외 X — 명시값 전달)."""
    lineage = lineage_values("real", "erp_csv", "ERP CSV sync")
    row: dict[str, object] = {
        "canonical_employee_id": rec.canonical_employee_id,
        "is_synthetic": 0,
        **lineage,
    }
    for rec_field, col in RECORD_TO_COLUMN.items():
        v = getattr(rec, rec_field)
        if rec_field == "is_active":
            row[col] = 1 if v else 0
        elif v is not None:
            row[col] = v
    return row


def _upsert(conn: sqlite3.Connection, rec: EmployeeRecord, dry_run: bool) -> str:
    """단건 upsert. 반환: 'insert' | 'update' | 'unchanged'."""
    row = _record_to_row(rec)
    existing = conn.execute(
        "SELECT * FROM employees WHERE canonical_employee_id = ?",
        (rec.canonical_employee_id,),
    ).fetchone()

    if existing is None:
        if dry_run:
            return "insert"
        # 신규 INSERT — 내부 employee_id 는 canonical 그대로 사용 (PoC).
        # Sprint 2: 사번 정책 결정 후 매핑 테이블 도입.
        row["employee_id"] = rec.canonical_employee_id
        # NOT NULL 컬럼 채우기 (position, position_level, division, department)
        row.setdefault("position", "사원")
        row.setdefault("position_level", 1)
        row.setdefault("division", row.get("department") or "미지정")
        row.setdefault("department", "미지정")
        cols = list(row.keys())
        placeholders = ",".join(["?"] * len(cols))
        conn.execute(
            f"INSERT INTO employees ({','.join(cols)}) VALUES ({placeholders})",
            tuple(row[c] for c in cols),
        )
        return "insert"

    # 기존 행 — 변경 사항만 UPDATE
    changes: dict[str, object] = {}
    existing_cols = set(existing.keys())
    for k, v in row.items():
        if k == "canonical_employee_id":
            continue
        current = existing[k] if k in existing_cols else None
        if current != v:
            changes[k] = v

    if not changes:
        return "unchanged"

    if dry_run:
        return "update"

    set_clause = ",".join(f"{k} = ?" for k in changes.keys())
    conn.execute(
        f"UPDATE employees SET {set_clause} WHERE canonical_employee_id = ?",
        (*changes.values(), rec.canonical_employee_id),
    )
    return "update"


def run(
    adapter: ErpAdapter | None = None,
    dry_run: bool = False,
    db_path=EMPLOYEES_DB,
) -> SyncReport:
    """Full sync. adapter 미지정 시 env 분기 (`get_erp_adapter`) 사용."""
    adapter = adapter or get_erp_adapter()
    report = SyncReport()

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        ensure_lineage_columns(conn, "employees")
        records: Iterable[EmployeeRecord] = adapter.iter_employees()
        for rec in records:
            try:
                if not rec.canonical_employee_id or not rec.name:
                    report.skipped += 1
                    continue
                outcome = _upsert(conn, rec, dry_run=dry_run)
                if outcome == "insert":
                    report.inserted += 1
                elif outcome == "update":
                    report.updated += 1
                else:
                    report.unchanged += 1
            except Exception as e:
                msg = f"{rec.canonical_employee_id}: {e}"
                report.errors.append(msg)
                logger.warning("upsert 실패: %s", msg)
        if not dry_run:
            conn.commit()
    finally:
        conn.close()

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ERP → employees.db sync runner")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="변경 사항을 출력만 하고 commit 하지 않음",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="DEBUG 로그 출력"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    try:
        report = run(dry_run=args.dry_run)
    except Exception as e:
        logger.error("sync 실패: %s", e)
        return 2

    print(f"--- ERP sync {'(dry-run)' if args.dry_run else ''} ---")
    print(f"inserted:  {report.inserted}")
    print(f"updated:   {report.updated}")
    print(f"unchanged: {report.unchanged}")
    print(f"skipped:   {report.skipped}")
    print(f"errors:    {len(report.errors)}")
    for e in report.errors[:10]:
        print(f"  ! {e}")
    return 0 if not report.errors else 1


if __name__ == "__main__":
    sys.exit(main())
