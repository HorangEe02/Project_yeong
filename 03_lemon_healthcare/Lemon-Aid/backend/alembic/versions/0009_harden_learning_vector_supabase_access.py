"""Harden learning vector tables for Supabase Data API exposure.

Revision ID: 0009_harden_learning_vector_supabase_access
Revises: 0008_health_daily_summaries_hypertable
Create Date: 2026-05-25 00:00:00.000000

The learning/vector pipeline stores private object references, owner hashes,
embedding jobs, and embedding metadata. These tables are used by the backend
through a direct PostgreSQL connection and must not be reachable from Supabase
client APIs by default. This migration keeps the public schema layout intact
while making the Data API path fail closed.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0009_harden_learning_vector_supabase_access"
down_revision: str | Sequence[str] | None = "0008_health_daily_summaries_hypertable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEARNING_VECTOR_TABLES = (
    "learning_image_objects",
    "image_embedding_jobs",
    "image_embedding_records",
)


def upgrade() -> None:
    """Enable RLS and remove Supabase API-role grants from learning tables."""
    op.execute("""
        ALTER TABLE public.learning_image_objects
        DROP CONSTRAINT IF EXISTS ck_learning_image_objects_learning_image_object_status_allowed
        """)
    op.execute("""
        ALTER TABLE public.learning_image_objects
        ADD CONSTRAINT ck_learning_image_objects_learning_image_object_status_allowed
        CHECK (
            status IN (
                'awaiting_confirmation',
                'pending_auto_filter',
                'pending_manual_review',
                'approved_for_embedding',
                'ready',
                'embedded',
                'deleted',
                'cancelled',
                'failed',
                'rejected_by_auto_filter',
                'rejected_by_review'
            )
        )
        """)

    for table_name in LEARNING_VECTOR_TABLES:
        op.execute(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            COMMENT ON TABLE public.{table_name} IS
            'Internal learning/vector pipeline table. Direct backend PostgreSQL access only; Supabase Data API grants are intentionally revoked and RLS is fail-closed.';
            """)

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


def downgrade() -> None:
    """Keep the fail-closed posture on downgrade.

    Re-opening client-role grants or disabling RLS would weaken the privacy
    boundary and should be a reviewed forward migration, not an automatic
    rollback side effect.
    """
