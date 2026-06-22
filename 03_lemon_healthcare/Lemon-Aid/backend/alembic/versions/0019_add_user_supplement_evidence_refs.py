"""Add confirmed supplement evidence references.

Revision ID: 0019_add_user_supplement_evidence_refs
Revises: 0018_create_learning_dataset_model_registry_tables
Create Date: 2026-05-28 00:00:00.000000

Confirmed supplement rows need bounded trace ids back to sanitized preview
evidence. The column stores only evidence span identifiers and intentionally
does not store raw OCR text, provider payloads, image bytes, URLs, or secrets.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019_add_user_supplement_evidence_refs"
down_revision: str | Sequence[str] | None = "0018_create_learning_dataset_model_registry_tables"
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
    """Add sanitized evidence reference ids to user supplements."""
    op.add_column(
        "user_supplements",
        sa.Column(
            "evidence_refs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    # Bare name on purpose: Base.metadata's naming convention wraps it into
    # ck_user_supplements_evidence_refs_array at execution time; passing the
    # already-prefixed name double-wraps it and diverges from the ORM model.
    # Existing environments are corrected by 0044.
    op.create_check_constraint(
        "evidence_refs_array",
        "user_supplements",
        "jsonb_typeof(evidence_refs) = 'array'",
    )


def downgrade() -> None:
    """Remove user supplement evidence reference ids."""
    _drop_check_by_definition("user_supplements", "jsonb_typeof(evidence_refs)")
    op.drop_column("user_supplements", "evidence_refs")
