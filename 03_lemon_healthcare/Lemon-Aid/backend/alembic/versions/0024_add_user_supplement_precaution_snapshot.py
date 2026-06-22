"""Add confirmed supplement precaution snapshot.

Revision ID: 0024_add_user_supplement_precaution_snapshot
Revises: 0023c_force_row_level_security
Create Date: 2026-06-01 00:00:00.000000

The snapshot stores only user-confirmed precaution sentences from the reviewed
label result. It intentionally does not store raw OCR text, provider payloads,
image bytes, URLs, or secrets.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024_add_user_supplement_precaution_snapshot"
down_revision: str | Sequence[str] | None = "0023c_force_row_level_security"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _drop_check_by_definition(table: str, definition_needle: str) -> None:
    """Drop the CHECK constraint on ``table`` matching ``definition_needle``.

    Locates the constraint by its CHECK definition rather than its name, so the
    downgrade works whether the live name is the convention-correct one or a
    historical double-wrapped variant (the divergence 0044 normalizes). It does
    not depend on 0044 having run. Idempotent: a no-op when no matching
    constraint is present. ``table`` must remain a hardcoded constant; the
    resolved name goes through ``format(... %I ...)``.
    """
    needle = definition_needle.replace("'", "''")
    op.execute(f"""
        DO $$
        DECLARE
            v_name text;
        BEGIN
            SELECT conname
            INTO v_name
            FROM pg_constraint
            WHERE conrelid = 'public.{table}'::regclass
              AND contype = 'c'
              AND pg_get_constraintdef(oid) ILIKE '%{needle}%'
            LIMIT 1;

            IF v_name IS NOT NULL THEN
                EXECUTE format(
                    'ALTER TABLE public.{table} DROP CONSTRAINT %I',
                    v_name
                );
            END IF;
        END $$;
        """)


def upgrade() -> None:
    """Add sanitized user-confirmed precaution sentences to supplements."""
    op.add_column(
        "user_supplements",
        sa.Column(
            "precaution_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    # Bare name on purpose: Base.metadata's naming convention wraps it into
    # ck_user_supplements_precaution_snapshot_array at execution time; passing
    # the already-prefixed name double-wraps it and diverges from the ORM model.
    # Existing environments are corrected by 0044.
    op.create_check_constraint(
        "precaution_snapshot_array",
        "user_supplements",
        "jsonb_typeof(precaution_snapshot) = 'array'",
    )


def downgrade() -> None:
    """Remove user-confirmed precaution sentence snapshots."""
    _drop_check_by_definition("user_supplements", "jsonb_typeof(precaution_snapshot)")
    op.drop_column("user_supplements", "precaution_snapshot")
