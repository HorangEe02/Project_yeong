"""Harden supplement, analysis, and consent tables for Supabase Data API exposure.

Revision ID: 0020_harden_supplement_user_tables_rls
Revises: 0019_add_user_supplement_evidence_refs
Create Date: 2026-05-30 00:00:00.000000

The core supplement domain tables, the generic ``analysis_results`` table, and the
privacy/consent tables hold user-linked health data (``owner_subject`` scoped) plus
curated product reference rows. They are accessed by the backend through a direct
PostgreSQL connection and must not be reachable from Supabase client APIs by
default.

This migration mirrors the already-reviewed fail-closed posture applied to the
learning/vector tables (0009/0010) and the media tables (0014): it enables row
level security and revokes client-role grants while keeping the public schema
layout intact. Backend access continues via the table-owning role, which bypasses
RLS, so direct-asyncpg request-path queries are unaffected. No data is modified.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0020_harden_supplement_user_tables_rls"
down_revision: str | Sequence[str] | None = "0019_add_user_supplement_evidence_refs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BACKEND_ONLY_SUPPLEMENT_TABLES = (
    "supplement_products",
    "supplement_product_ingredients",
    "supplement_analysis_runs",
    "user_supplements",
    "user_supplement_ingredients",
    "analysis_results",
    "consent_records",
    "consent_policies",
    "deletion_requests",
)

# Hardcoded constant identifiers (no user input) joined for the REVOKE statements.
_TABLE_LIST_SQL = ",\n            ".join(
    f"public.{table_name}" for table_name in BACKEND_ONLY_SUPPLEMENT_TABLES
)
_TABLE_LIST_INLINE = ", ".join(
    f"public.{table_name}" for table_name in BACKEND_ONLY_SUPPLEMENT_TABLES
)


def upgrade() -> None:
    """Enable RLS and remove Supabase API-role grants from supplement/user tables."""
    for table_name in BACKEND_ONLY_SUPPLEMENT_TABLES:
        op.execute(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            COMMENT ON TABLE public.{table_name} IS
            'Backend-only supplement/health table. Direct backend PostgreSQL access only; Supabase Data API grants are intentionally revoked and RLS is fail-closed.';
            """)

    op.execute(f"""
        REVOKE ALL PRIVILEGES ON TABLE
            {_TABLE_LIST_SQL}
        FROM PUBLIC
        """)
    op.execute(f"""
        DO $$
        DECLARE
            role_name text;
        BEGIN
            FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
                    EXECUTE format(
                        'REVOKE ALL PRIVILEGES ON TABLE {_TABLE_LIST_INLINE} FROM %I',
                        role_name
                    );
                END IF;
            END LOOP;
        END
        $$;
        """)


def downgrade() -> None:
    """Keep the fail-closed posture on downgrade.

    Re-opening client-role grants or disabling RLS would weaken the privacy
    boundary and should be a reviewed forward migration, not an automatic
    rollback side effect. This mirrors the 0009/0010/0014 downgrade policy.
    """
