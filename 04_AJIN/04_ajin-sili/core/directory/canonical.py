"""Canonical directory service — single source of truth for headcount.

Resolves the 3-way mismatch (config.py 649 / employees.db 329 / auth.db users 34)
by making employees.db the master and computing counts dynamically.

Usage:
    from core.directory.canonical import CanonicalDirectory
    cd = CanonicalDirectory()
    cd.get_total_headcount()         # active + (synthetic or real)
    cd.get_active_count()            # only is_active = 1
    cd.get_real_count()              # is_synthetic = 0
    cd.resolve_user_to_employee(uid) # users.user_id → Employee row
    report = cd.reconcile()          # 3-way gap report

Migration 0001 must be applied first (is_synthetic column).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.directory.migrations import EMPLOYEES_DB, AUTH_DB


@dataclass(frozen=True)
class HeadcountSummary:
    total_active: int
    synthetic_count: int
    real_count: int

    def to_dict(self) -> dict:
        return {
            "total_active": self.total_active,
            "synthetic_count": self.synthetic_count,
            "real_count": self.real_count,
        }


@dataclass(frozen=True)
class ReconciliationReport:
    """3-way gap snapshot.

    `config_total` reflects the legacy COMPANY_INFO["total_employees"] value,
    kept for diagnostic comparison only; CanonicalDirectory does not consult it.
    """
    employees_active: int
    employees_synthetic: int
    employees_real: int
    auth_users_active: int
    config_total: Optional[int]
    has_gap: bool

    def to_dict(self) -> dict:
        return {
            "employees_active": self.employees_active,
            "employees_synthetic": self.employees_synthetic,
            "employees_real": self.employees_real,
            "auth_users_active": self.auth_users_active,
            "config_total": self.config_total,
            "has_gap": self.has_gap,
        }


class CanonicalDirectory:
    """employees.db = master. All KPI counts derive from here."""

    def __init__(
        self,
        employees_db: Path = EMPLOYEES_DB,
        auth_db: Path = AUTH_DB,
    ) -> None:
        self.employees_db = Path(employees_db)
        self.auth_db = Path(auth_db)

    # ─── connection helpers ───────────────────────────────────

    def _emp(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.employees_db))
        conn.row_factory = sqlite3.Row
        return conn

    def _auth(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.auth_db))
        conn.row_factory = sqlite3.Row
        return conn

    # ─── headcount queries ────────────────────────────────────

    def get_total_headcount(self, include_synthetic: bool = True) -> int:
        """Active employee count. include_synthetic=False → real only."""
        sql = "SELECT COUNT(*) FROM employees WHERE is_active = 1"
        if not include_synthetic:
            sql += " AND is_synthetic = 0"
        with self._emp() as conn:
            return int(conn.execute(sql).fetchone()[0])

    def get_active_count(self) -> int:
        return self.get_total_headcount(include_synthetic=True)

    def get_real_count(self) -> int:
        return self.get_total_headcount(include_synthetic=False)

    def get_synthetic_count(self) -> int:
        with self._emp() as conn:
            return int(conn.execute(
                "SELECT COUNT(*) FROM employees WHERE is_active = 1 AND is_synthetic = 1"
            ).fetchone()[0])

    def headcount_summary(self) -> HeadcountSummary:
        total = self.get_active_count()
        syn = self.get_synthetic_count()
        return HeadcountSummary(
            total_active=total,
            synthetic_count=syn,
            real_count=total - syn,
        )

    # ─── user → employee resolution ────────────────────────────

    def resolve_user_to_employee(self, user_id: int) -> Optional[dict]:
        """auth.db users.user_id → employees row (dict). Returns None if no FK."""
        with self._auth() as auth:
            row = auth.execute(
                "SELECT employee_id FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if not row or not row["employee_id"]:
            return None
        with self._emp() as emp:
            erow = emp.execute(
                "SELECT * FROM employees WHERE employee_id = ?",
                (row["employee_id"],),
            ).fetchone()
        return dict(erow) if erow else None

    def resolve_employee_id_to_user_id(self, employee_id: str) -> Optional[int]:
        with self._auth() as auth:
            row = auth.execute(
                "SELECT user_id FROM users WHERE employee_id = ?",
                (employee_id,),
            ).fetchone()
        return int(row["user_id"]) if row else None

    # ─── reconciliation ───────────────────────────────────────

    def reconcile(self) -> ReconciliationReport:
        """Compare 3 sources. Returns gap report; does not mutate.

        Logs to headcount_snapshot via `take_snapshot()` separately.
        """
        summary = self.headcount_summary()
        with self._auth() as auth:
            users_active = int(auth.execute(
                "SELECT COUNT(*) FROM users WHERE is_active = 1"
            ).fetchone()[0])

        config_total: Optional[int] = None
        try:
            from config import COMPANY_INFO  # type: ignore
            config_total = int(COMPANY_INFO.get("total_employees", 0)) or None
        except Exception:
            config_total = None

        has_gap = (
            (config_total is not None and config_total != summary.total_active)
            or users_active != summary.total_active
        )
        return ReconciliationReport(
            employees_active=summary.total_active,
            employees_synthetic=summary.synthetic_count,
            employees_real=summary.real_count,
            auth_users_active=users_active,
            config_total=config_total,
            has_gap=has_gap,
        )

    def take_snapshot(self, snapshot_date: Optional[str] = None) -> dict:
        """Insert (or replace) one row in headcount_snapshot. Returns the row."""
        summary = self.headcount_summary()
        with self._emp() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO headcount_snapshot
                   (snapshot_date, total_active, synthetic_count, real_count, computed_at)
                   VALUES (COALESCE(?, date('now')), ?, ?, ?, datetime('now'))""",
                (snapshot_date, summary.total_active, summary.synthetic_count, summary.real_count),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM headcount_snapshot WHERE snapshot_date = COALESCE(?, date('now'))",
                (snapshot_date,),
            ).fetchone()
        return dict(row) if row else summary.to_dict()


_default: Optional[CanonicalDirectory] = None


def default() -> CanonicalDirectory:
    """Process-wide singleton for convenience."""
    global _default
    if _default is None:
        _default = CanonicalDirectory()
    return _default
