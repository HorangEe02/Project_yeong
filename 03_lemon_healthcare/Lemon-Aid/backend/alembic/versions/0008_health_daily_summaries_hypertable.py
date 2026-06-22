"""Convert health_daily_summaries to a TimescaleDB hypertable (opt-in).

Revision ID: 0008_health_daily_summaries_hypertable
Revises: 0007_health_daily_summaries_composite_pk
Create Date: 2026-05-19 00:30:00.000000

This migration is intentionally **opt-in**: it converts
``health_daily_summaries`` into a TimescaleDB hypertable *only when* the
target PostgreSQL instance has the ``timescaledb`` extension available.
Standard PostgreSQL instances (e.g. CI's ``postgres:16``) emit a NOTICE
and the migration completes as a no-op. Production Postgres instances
running ``timescale/timescaledb:latest-pgN`` install the extension and
call ``create_hypertable`` with ``migrate_data => TRUE``.

Downgrade is deliberately a no-op: hypertable → regular-table reversal
is destructive and chunk-level data movement is not idempotent. Use a
database snapshot (PITR / pg_dump) for emergency revert. See
``docs/Nutrition-docs/dev-guides/timescaledb-activation.md`` for the
full operational runbook.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0008_health_daily_summaries_hypertable"
down_revision: str | Sequence[str] | None = "0007_health_daily_summaries_composite_pk"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Conditionally convert health_daily_summaries to a hypertable.

    Uses a ``DO`` block so the call to ``create_hypertable`` is parsed and
    executed only inside the branch that already verified the extension is
    available. Standard Postgres images therefore never error out — they
    just emit a NOTICE and continue.
    """
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb'
            ) THEN
                CREATE EXTENSION IF NOT EXISTS timescaledb;
                PERFORM create_hypertable(
                    'health_daily_summaries',
                    'measured_date',
                    if_not_exists => TRUE,
                    migrate_data => TRUE
                );
            ELSE
                RAISE NOTICE 'timescaledb extension not available; skipping hypertable conversion';
            END IF;
        END
        $$;
        """)


def downgrade() -> None:
    """No-op downgrade.

    Hypertable downgrade is destructive (chunks must be copied back into a
    regular table and the hypertable dropped). We deliberately do not
    automate that here so an accidental ``alembic downgrade`` cannot lose
    data. Use a database snapshot or PITR for emergency revert.
    """
