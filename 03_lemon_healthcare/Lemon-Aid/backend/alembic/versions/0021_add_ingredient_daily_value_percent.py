"""Add daily-value percent (%DV / 영양성분기준치) to ingredient tables.

Revision ID: 0021_add_ingredient_daily_value_percent
Revises: 0020_harden_supplement_user_tables_rls
Create Date: 2026-05-30 00:00:00.000000

Supplement labels frequently express each ingredient's amount alongside a
percentage of the daily reference intake (영양성분기준치 / %DV). The schema
previously captured only the absolute ``amount`` + ``unit`` and had no typed
column for the percentage, so that signal was lost. This migration adds an
optional, non-negative ``daily_value_percent`` Numeric column to both the
reference catalog ingredient table and the user-confirmed ingredient table.
The column is additive and nullable; existing rows are unaffected and no data
is modified.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021_add_ingredient_daily_value_percent"
down_revision: str | Sequence[str] | None = "0020_harden_supplement_user_tables_rls"
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
    """Add nullable, non-negative daily_value_percent to ingredient tables."""
    op.add_column(
        "supplement_product_ingredients",
        sa.Column("daily_value_percent", sa.Numeric(7, 3), nullable=True),
    )
    # Bare name on purpose: Base.metadata's naming convention prefixes it with
    # ck_<table>_ at execution time; passing the already-prefixed name
    # double-wraps it and diverges from the ORM model. Existing environments are
    # corrected by 0044.
    op.create_check_constraint(
        "daily_value_percent_nonnegative",
        "supplement_product_ingredients",
        "daily_value_percent IS NULL OR daily_value_percent >= 0",
    )

    op.add_column(
        "user_supplement_ingredients",
        sa.Column("daily_value_percent", sa.Numeric(7, 3), nullable=True),
    )
    op.create_check_constraint(
        "daily_value_percent_nonnegative",
        "user_supplement_ingredients",
        "daily_value_percent IS NULL OR daily_value_percent >= 0",
    )


def downgrade() -> None:
    """Remove the daily_value_percent columns from ingredient tables."""
    _drop_check_by_definition("user_supplement_ingredients", "daily_value_percent IS NULL")
    op.drop_column("user_supplement_ingredients", "daily_value_percent")

    _drop_check_by_definition("supplement_product_ingredients", "daily_value_percent IS NULL")
    op.drop_column("supplement_product_ingredients", "daily_value_percent")
