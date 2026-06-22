"""Revoke learning API grants and public security-definer execution.

Revision ID: 0010_revoke_learning_api_grants
Revises: 0009_harden_learning_vector_supabase_access
Create Date: 2026-05-25 10:30:00.000000

This migration is intentionally idempotent. The remote Supabase project can
drift when tables were created before the fail-closed grant policy landed, so
we re-apply the learning table revokes and remove client-role execute access
from public SECURITY DEFINER helper functions.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0010_revoke_learning_api_grants"
down_revision: str | Sequence[str] | None = "0009_harden_learning_vector_supabase_access"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Re-apply fail-closed Supabase API grants for learning/vector surfaces."""
    op.execute("""
        REVOKE ALL PRIVILEGES ON TABLE
            public.learning_image_objects,
            public.image_embedding_jobs,
            public.image_embedding_records
        FROM PUBLIC
        """)
    op.execute("""
        DO $$
        DECLARE
            role_name text;
        BEGIN
            FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
                    EXECUTE format(
                        'REVOKE ALL PRIVILEGES ON TABLE public.learning_image_objects, public.image_embedding_jobs, public.image_embedding_records FROM %I',
                        role_name
                    );
                END IF;
            END LOOP;
        END
        $$;
        """)
    op.execute("""
        DO $$
        DECLARE
            role_name text;
            function_identity text;
        BEGIN
            FOR function_identity IN
                SELECT p.oid::regprocedure::text
                FROM pg_proc p
                JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = 'public'
                  AND p.prosecdef
                  AND p.proname = 'rls_auto_enable'
            LOOP
                EXECUTE format('REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC', function_identity);
                FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
                    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
                        EXECUTE format(
                            'REVOKE EXECUTE ON FUNCTION %s FROM %I',
                            function_identity,
                            role_name
                        );
                    END IF;
                END LOOP;
            END LOOP;
        END
        $$;
        """)


def downgrade() -> None:
    """Do not restore client-role access to private learning/vector surfaces."""
