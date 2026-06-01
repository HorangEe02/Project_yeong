"""Canonical directory — single source of truth for employee headcount.

Sprint 1 P0 (Feature A guideline §4.4 데이터 정합성 단일화).

Resolves the 3-way mismatch documented at plan §1:
  - config.py COMPANY_INFO["total_employees"] = 649
  - employees.db row count = 329
  - auth.db users count = 34

employees.db is the master. users.employee_id is the FK.
Migrations 0001 add is_synthetic / canonical_employee_id plus shared
data_class / source_system / source_label / source_updated_at lineage columns,
headcount_snapshot, and search_history tables.
"""
