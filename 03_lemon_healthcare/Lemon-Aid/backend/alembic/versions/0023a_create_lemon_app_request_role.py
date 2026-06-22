"""Create the non-superuser request role ``lemon_app`` and grant table access.

Revision ID: 0023a_create_lemon_app_request_role
Revises: 0022_harden_audit_logs_and_default_privileges
Create Date: 2026-05-31 00:00:00.000000

Step 1 of the FORCE RLS rollout (docs/2026-05-31-force-rls-rollout-design.md §3.4).

The live request path currently connects as ``lemon``, which owns every table AND
is a superuser — superusers bypass RLS *and* FORCE RLS, so row policies can never
take effect under that role. This migration creates a dedicated, least-privilege
request role ``lemon_app`` (NOSUPERUSER, NOBYPASSRLS) and grants it CRUD on
user-data tables and SELECT on catalog tables.

This step is intentionally inert on its own: no policy is created and FORCE is not
enabled here, and the application keeps connecting as ``lemon`` until a later,
separately-approved step flips ``DATABASE_URL`` to ``lemon_app``. Creating the
role early lets grants/policies be staged and reviewed without changing behavior.

Password: the role is created WITH LOGIN but NO password here; the operator sets a
password out-of-band (``ALTER ROLE lemon_app PASSWORD ...`` from a secret) before
the app is pointed at it. Creating a password in a migration would commit a secret.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0023a_create_lemon_app_request_role"
down_revision: str | Sequence[str] | None = "0022_harden_audit_logs_and_default_privileges"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "lemon_app"

# User-data tables: request role needs full CRUD (row policies added in 0023b
# constrain *which* rows). Catalog tables get SELECT only.
USER_DATA_TABLES = (
    # Type A — plaintext owner_subject
    "user_supplements",
    "supplement_analysis_runs",
    "meal_records",
    "health_daily_summaries",
    "health_metric_samples",
    "health_sync_batches",
    "body_profile_snapshots",
    "analysis_results",
    "consent_records",
    "food_image_analysis_runs",
    # Type B — hashed owner_subject_hash
    "regulated_documents",
    "media_objects",
    "medical_record_collections",
    "learning_image_objects",
    "image_embedding_jobs",
    "image_embedding_records",
    "learning_dataset_items",
    "annotation_tasks",
    "deletion_requests",
    "patient_status_snapshots",
    # Type C — FK children
    "user_supplement_ingredients",
    "supplement_image_evidence",
    "meal_food_items",
    "media_processing_runs",
    "patient_conditions",
    "patient_medications",
    "prescription_items",
    "lab_result_items",
)
CATALOG_TABLES = (
    "supplement_products",
    "supplement_product_ingredients",
    "consent_policies",
    "users",
    "model_registry",
    "model_training_runs",
    "model_eval_results",
    "learning_dataset_versions",
    "audit_logs",
)


def upgrade() -> None:
    """Create lemon_app and grant least-privilege table access."""
    op.execute(f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                CREATE ROLE {APP_ROLE} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
            END IF;
        END
        $$;
        """)
    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
    for table_name in USER_DATA_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON public.{table_name} TO {APP_ROLE}")
    for table_name in CATALOG_TABLES:
        op.execute(f"GRANT SELECT ON public.{table_name} TO {APP_ROLE}")
    # Sequences backing the granted tables' serial/identity PKs.
    op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE}")


def downgrade() -> None:
    """Revoke grants and drop the request role.

    Safe to roll back as long as the application is not already connecting as
    ``lemon_app`` (it should not be until a later, separate step).
    """
    op.execute(f"REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM {APP_ROLE}")
    op.execute(f"REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM {APP_ROLE}")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {APP_ROLE}")
    op.execute(f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                DROP ROLE {APP_ROLE};
            END IF;
        END
        $$;
        """)
