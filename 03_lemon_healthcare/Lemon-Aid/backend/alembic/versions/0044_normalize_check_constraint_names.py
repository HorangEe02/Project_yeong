"""Normalize double-wrapped check-constraint names on supplement tables.

Revision ID: 0044_normalize_check_constraint_names
Revises: 0043_add_user_supplement_category_key
Create Date: 2026-06-13 00:00:00.000000

Migrations 0019, 0021, and 0024 passed already-prefixed check-constraint names
(e.g. ``ck_user_supplements_precaution_snapshot_array``) to
``op.create_check_constraint``. ``Base.metadata`` carries a naming convention
(``ck_%(table_name)s_%(constraint_name)s``) that Alembic re-applies at execution
time, so those names were double-wrapped — and, when over 63 chars, truncated
and hashed by SQLAlchemy — producing live constraint names like
``ck_user_supplements_ck_user_supplements_precaution_snap_c42d``. Those names
diverge from what the ORM models declare, which breaks ``alembic`` autogenerate
drift detection and any drop-by-model-name.

Those source migrations have been corrected to pass the bare constraint token, so
fresh databases already build the convention-correct name. This migration brings
already-migrated environments back in line by renaming each drifted constraint to
the name SQLAlchemy emits for the bare token. The source constraint is located by
its CHECK definition rather than its (version-sensitive) drifted name, and the
rename only fires when the drifted name is present and the target name is not, so
the migration is idempotent and safe to run on fresh or already-corrected
databases.

No data is read or written and no grants/policies change; only constraint
metadata names are touched.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0044_normalize_check_constraint_names"
down_revision: str | Sequence[str] | None = "0043_add_user_supplement_category_key"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Each tuple: (table, CHECK-definition substring to locate the constraint,
# target physical constraint name SQLAlchemy emits for the bare token).
#
# The definition substring is chosen to match exactly one CHECK per table. The
# ingredient needle is ``daily_value_percent IS NULL`` — the distinguishing
# clause of the non-negative check — rather than the bare column name, so a
# future second CHECK referencing the same column cannot be matched by mistake.
#
# The two ingredient targets differ in length: the product-ingredients name
# exceeds PostgreSQL's 63-char identifier limit, so SQLAlchemy truncates it and
# appends a deterministic hash suffix (``_230f``); the user-ingredients name fits
# and is kept whole. Both values match the names rendered from Base.metadata.
_RENAMES: tuple[tuple[str, str, str], ...] = (
    (
        "user_supplements",
        "jsonb_typeof(precaution_snapshot)",
        "ck_user_supplements_precaution_snapshot_array",
    ),
    (
        "user_supplements",
        "jsonb_typeof(evidence_refs)",
        "ck_user_supplements_evidence_refs_array",
    ),
    (
        "supplement_product_ingredients",
        "daily_value_percent IS NULL",
        "ck_supplement_product_ingredients_daily_value_percent_n_230f",
    ),
    (
        "user_supplement_ingredients",
        "daily_value_percent IS NULL",
        "ck_user_supplement_ingredients_daily_value_percent_nonnegative",
    ),
)


def _normalize_sql(table: str, definition_needle: str, target: str) -> str:
    """Build an idempotent constraint-normalization DO block.

    Args:
        table: Unqualified table name in the ``public`` schema.
        definition_needle: Substring of ``pg_get_constraintdef`` that uniquely
            identifies the target CHECK constraint on the table.
        target: Convention-correct physical constraint name to converge on.

    Returns:
        A PL/pgSQL ``DO`` block that locates the constraint by its CHECK
        definition (never its version-sensitive name) and converges it on
        ``target``:

        * drifted present, target absent  -> rename drifted to target;
        * drifted present, target present -> drop the drifted duplicate (a
          partial manual fix can leave both; the convention-correct one wins);
        * no non-target match             -> no-op.

        Idempotent and safe on fresh, already-corrected, and already-migrated
        databases. ``table`` is interpolated directly and MUST remain a
        hardcoded constant from ``_RENAMES``; the dynamic constraint names go
        through ``format(... %I ...)``.
    """
    needle = definition_needle.replace("'", "''")
    target_sql = target.replace("'", "''")
    return f"""
        DO $$
        DECLARE
            v_old text;
            v_has_target boolean;
        BEGIN
            SELECT conname
            INTO v_old
            FROM pg_constraint
            WHERE conrelid = 'public.{table}'::regclass
              AND contype = 'c'
              AND conname <> '{target_sql}'
              AND pg_get_constraintdef(oid) ILIKE '%{needle}%'
            LIMIT 1;

            IF v_old IS NULL THEN
                RETURN;  -- already normalized, or constraint absent
            END IF;

            SELECT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conrelid = 'public.{table}'::regclass
                  AND conname = '{target_sql}'
            ) INTO v_has_target;

            IF v_has_target THEN
                EXECUTE format(
                    'ALTER TABLE public.{table} DROP CONSTRAINT %I',
                    v_old
                );
            ELSE
                EXECUTE format(
                    'ALTER TABLE public.{table} RENAME CONSTRAINT %I TO %I',
                    v_old,
                    '{target_sql}'
                );
            END IF;
        END $$;
    """


def upgrade() -> None:
    """Normalize drifted, double-wrapped check constraints to convention names."""
    for table, definition_needle, target in _RENAMES:
        op.execute(_normalize_sql(table, definition_needle, target))


def downgrade() -> None:
    """Intentionally a no-op.

    This migration only normalizes constraint names; re-introducing the buggy
    double-wrapped names on downgrade would serve no purpose. The no-op is safe
    because the corrected 0019/0021/0024 downgrades locate their constraint by
    CHECK definition (not by name), so they drop it whether the live name is the
    convention-correct one or a historical double-wrapped variant — they do not
    depend on this migration having run. Those source migrations own creating
    and dropping these constraints.
    """
