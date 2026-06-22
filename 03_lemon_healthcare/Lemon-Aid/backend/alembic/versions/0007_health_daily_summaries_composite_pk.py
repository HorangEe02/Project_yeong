"""Expand health_daily_summaries primary key to (id, measured_date).

Revision ID: 0007_health_daily_summaries_composite_pk
Revises: 0006_create_regulated_ocr_intake
Create Date: 2026-05-19 00:00:00.000000

This migration prepares ``health_daily_summaries`` for an opt-in TimescaleDB
hypertable conversion (PR-P). TimescaleDB requires every UNIQUE/PRIMARY KEY
constraint on a hypertable to include the time partitioning column. The
existing single-column UUID PK violated that rule, so we widen it to a
composite ``(id, measured_date)`` PK. No external table references the row
``id``, and service-layer access uses ``(owner_subject, measured_date,
source_platform)`` natural-key queries, so this constraint swap is a
metadata-only change with zero data movement.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0007_health_daily_summaries_composite_pk"
down_revision: str | Sequence[str] | None = "0006_create_regulated_ocr_intake"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "health_daily_summaries"
PK_NAME = "pk_health_daily_summaries"


def upgrade() -> None:
    """Replace the id-only PK with a composite (id, measured_date) PK."""
    op.drop_constraint(PK_NAME, TABLE_NAME, type_="primary")
    op.create_primary_key(PK_NAME, TABLE_NAME, ["id", "measured_date"])


def downgrade() -> None:
    """Restore the id-only PK without touching row data."""
    op.drop_constraint(PK_NAME, TABLE_NAME, type_="primary")
    op.create_primary_key(PK_NAME, TABLE_NAME, ["id"])
