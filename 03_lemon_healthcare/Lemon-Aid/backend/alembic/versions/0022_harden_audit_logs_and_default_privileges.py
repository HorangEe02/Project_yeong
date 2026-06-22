"""Close the audit_logs RLS gap and revoke default privileges for future tables.

Revision ID: 0022_harden_audit_logs_and_default_privileges
Revises: 0021_add_ingredient_daily_value_percent
Create Date: 2026-05-31 00:00:00.000000

Two fail-closed hardening steps that extend the posture established by
0009/0014/0020:

1. ``audit_logs`` holds per-actor audit trail rows (``actor_subject`` plus hashed
   IP / user-agent) and was the only user-linked table still missing RLS — every
   other public table is already either RLS-enabled or non-sensitive
   (``alembic_version``). This enables RLS + revokes client-role grants on it,
   mirroring 0020 exactly.

2. ``ALTER DEFAULT PRIVILEGES`` so that *future* tables created by the owning
   role do not automatically grant access to ``PUBLIC`` / ``anon`` /
   ``authenticated`` / ``service_role``. Today's safety is REVOKE-per-table; a new
   table added later would silently inherit the default ``PUBLIC`` grant and, if
   the schema were ever exposed through the Supabase Data API, become readable.
   Revoking the default closes that recurring re-exposure vector.

Backend access continues via the table-owning role, which bypasses RLS, so
direct-asyncpg request-path queries are unaffected. No data is modified. RLS is
intentionally ENABLE (not FORCE): the request path connects as the table owner,
and FORCE would subject the owner to the (deliberately absent) policies and lock
the backend out. Non-owner client roles get an implicit deny via the revoked
grants, which is the intended fail-closed boundary for Data-API exposure.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0022_harden_audit_logs_and_default_privileges"
down_revision: str | Sequence[str] | None = "0021_add_ingredient_daily_value_percent"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BACKEND_ONLY_TABLES = ("audit_logs",)

# Hardcoded constant identifiers (no user input) for the REVOKE statements.
_TABLE_LIST_SQL = ", ".join(f"public.{table_name}" for table_name in BACKEND_ONLY_TABLES)

# Client roles that the Supabase Data API (PostREST) would connect as.
_CLIENT_ROLES = ("anon", "authenticated", "service_role")


def upgrade() -> None:
    """Enable RLS on audit_logs and revoke default privileges for new tables."""
    for table_name in BACKEND_ONLY_TABLES:
        op.execute(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            COMMENT ON TABLE public.{table_name} IS
            'Backend-only audit table. Direct backend PostgreSQL access only; Supabase Data API grants are intentionally revoked and RLS is fail-closed.';
            """)

    op.execute(f"REVOKE ALL PRIVILEGES ON TABLE {_TABLE_LIST_SQL} FROM PUBLIC")
    op.execute(f"""
        DO $$
        DECLARE
            role_name text;
        BEGIN
            FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
                    EXECUTE format(
                        'REVOKE ALL PRIVILEGES ON TABLE {_TABLE_LIST_SQL} FROM %I',
                        role_name
                    );
                END IF;
            END LOOP;
        END
        $$;
        """)

    # Revoke the default PUBLIC grant on tables/sequences created hereafter by the
    # current (owning) role, then revoke from client roles if they exist. This is
    # scoped to the owner role's future objects; existing tables are unaffected.
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM PUBLIC")
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM PUBLIC")
    op.execute("""
        DO $$
        DECLARE
            role_name text;
        BEGIN
            FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
                    EXECUTE format(
                        'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM %I',
                        role_name
                    );
                    EXECUTE format(
                        'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM %I',
                        role_name
                    );
                END IF;
            END LOOP;
        END
        $$;
        """)


def downgrade() -> None:
    """Keep the fail-closed posture on downgrade.

    Re-opening client-role grants, disabling RLS, or restoring default PUBLIC
    privileges would weaken the privacy boundary and should be a reviewed forward
    migration, not an automatic rollback side effect. This mirrors the
    0009/0010/0014/0020 downgrade policy.
    """
