-- Migration 0001 — Canonical Directory & KPI Measurement Infrastructure
-- Date: 2026-05-17
-- Plan: Brand-New-update/FEATURE_A_GUIDELINE.md Sprint 1 P0
--
-- Targets 3 DB files. Runner: core/directory/migrations.py applies idempotently
-- (SQLite ADD COLUMN is not idempotent — runner catches OperationalError).
--
-- Reference only; the runner is the source of truth.

-- ─────────────────────────────────────────────────────────
-- employees.db — synthetic / source / canonical id columns
-- ─────────────────────────────────────────────────────────
ALTER TABLE employees ADD COLUMN is_synthetic INTEGER NOT NULL DEFAULT 1;
ALTER TABLE employees ADD COLUMN source_system TEXT NOT NULL DEFAULT 'seed';
ALTER TABLE employees ADD COLUMN canonical_employee_id TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_emp_canonical
  ON employees(canonical_employee_id) WHERE canonical_employee_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_emp_synthetic
  ON employees(is_synthetic);

-- ─────────────────────────────────────────────────────────
-- auth.db — users.employee_id already exists (NOT NULL UNIQUE).
-- Only ensure index for join.
-- ─────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_users_emp ON users(employee_id);

-- ─────────────────────────────────────────────────────────
-- audit.db — KPI measurement columns
-- ─────────────────────────────────────────────────────────
ALTER TABLE api_audit_log ADD COLUMN latency_ms INTEGER;
ALTER TABLE api_audit_log ADD COLUMN intent TEXT;
ALTER TABLE api_audit_log ADD COLUMN result_count INTEGER;
CREATE INDEX IF NOT EXISTS idx_audit_latency
  ON api_audit_log(timestamp, latency_ms);

-- ─────────────────────────────────────────────────────────
-- employees.db — headcount snapshot for KPI freeze
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS headcount_snapshot (
  snapshot_date TEXT PRIMARY KEY,
  total_active INTEGER NOT NULL,
  synthetic_count INTEGER NOT NULL,
  real_count INTEGER NOT NULL,
  computed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ─────────────────────────────────────────────────────────
-- employees.db — search history persistence
-- (replaces Streamlit session-state store in
--  features/search/employee/search_history.py)
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS search_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  query TEXT NOT NULL,
  intent TEXT,
  clicked_rank INTEGER,
  action_invoked TEXT,
  latency_ms INTEGER,
  result_count INTEGER,
  ts TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_sh_user_ts ON search_history(user_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_sh_intent_ts ON search_history(intent, ts DESC);
