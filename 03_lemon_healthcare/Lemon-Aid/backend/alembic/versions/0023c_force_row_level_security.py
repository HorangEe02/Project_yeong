"""Enable FORCE ROW LEVEL SECURITY on all policy-covered tables.

Revision ID: 0023c_force_row_level_security
Revises: 0023b_create_rls_owner_policies
Create Date: 2026-05-31 00:00:00.000000

Step 3 (final) of the FORCE RLS rollout (docs/2026-05-31-force-rls-rollout-design.md).

⚠️ DO NOT APPLY until the application is verified to connect as the non-superuser
``lemon_app`` role in the target environment. FORCE makes the *table owner* also
subject to RLS policies; combined with the request role, only owner-scoped rows
are visible. Apply order per the design:
  1. 0023a (role + grants)  — inert
  2. 0023b (policies)        — inert under superuser
  3. point DATABASE_URL at lemon_app in STAGING; run integration tests
  4. THIS migration (FORCE)  — enforcement begins
  5. production after staging is green

Rollback: ``downgrade`` flips FORCE back off (NO FORCE), restoring the prior
ENABLE+REVOKE posture without dropping policies or the role.

The table set mirrors the policy coverage in 0023b plus the catalog tables (FORCE
on a catalog table is safe because its policy is ``USING (true)`` for the request
role and the owner/superuser path is unaffected by maintenance connections).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0023c_force_row_level_security"
down_revision: str | Sequence[str] | None = "0023b_create_rls_owner_policies"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Every table that received a lemon_app policy in 0023b.
FORCED_TABLES = (
    # Type A
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
    # Type B
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
    # Type C
    "user_supplement_ingredients",
    "supplement_image_evidence",
    "meal_food_items",
    "media_processing_runs",
    "patient_conditions",
    "patient_medications",
    "prescription_items",
    "lab_result_items",
    # Type D (catalog; policy = read-all for request role)
    "supplement_products",
    "supplement_product_ingredients",
    "consent_policies",
    "learning_dataset_versions",
)


def upgrade() -> None:
    """Force RLS so even the table owner is subject to row policies."""
    for table_name in FORCED_TABLES:
        op.execute(f"ALTER TABLE public.{table_name} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    """Disable FORCE, restoring the ENABLE+REVOKE-only posture (policies retained)."""
    for table_name in FORCED_TABLES:
        op.execute(f"ALTER TABLE public.{table_name} NO FORCE ROW LEVEL SECURITY")
