"""Create per-row RLS policies for the request role (not yet FORCEd).

Revision ID: 0023b_create_rls_owner_policies
Revises: 0023a_create_lemon_app_request_role
Create Date: 2026-05-31 00:00:00.000000

Step 2 of the FORCE RLS rollout (docs/2026-05-31-force-rls-rollout-design.md §3).

Creates owner-scoped policies for ``lemon_app`` across the four table archetypes,
keyed on transaction-local GUCs the backend sets per request
(``app.current_subject`` / ``app.current_subject_hash``). Proven against a
throwaway DB in backend/scripts/db_poc/force_rls_poc.sql.

Still inert in production until 0023c enables FORCE and the app connects as
``lemon_app``: ``lemon`` is a superuser and bypasses these policies, so behavior
is unchanged after this migration. ``current_setting(..., true)`` returns NULL
when the GUC is unset, which matches no owner → fail-closed (0 rows), never a
leak.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0023b_create_rls_owner_policies"
down_revision: str | Sequence[str] | None = "0023a_create_lemon_app_request_role"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "lemon_app"
POLICY = "lemon_app_owner_rw"
CATALOG_POLICY = "lemon_app_catalog_read"

# Type A — plaintext owner_subject column.
PLAINTEXT_OWNER_TABLES = (
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
)
# Type B — hashed owner_subject_hash column.
HASHED_OWNER_TABLES = (
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
)
# Type C — FK child → (parent table, local FK column, parent owner column).
CHILD_TABLES: tuple[tuple[str, str, str, str], ...] = (
    ("user_supplement_ingredients", "user_supplements", "user_supplement_id", "owner_subject"),
    ("supplement_image_evidence", "supplement_analysis_runs", "analysis_run_id", "owner_subject"),
    ("meal_food_items", "meal_records", "meal_id", "owner_subject"),
    ("media_processing_runs", "media_objects", "media_object_id", "owner_subject_hash"),
    (
        "patient_conditions",
        "medical_record_collections",
        "medical_collection_id",
        "owner_subject_hash",
    ),
    (
        "patient_medications",
        "medical_record_collections",
        "medical_collection_id",
        "owner_subject_hash",
    ),
    ("prescription_items", "regulated_documents", "document_id", "owner_subject_hash"),
    ("lab_result_items", "regulated_documents", "document_id", "owner_subject_hash"),
)
# Type D — catalog tables (public read for the request role; writes stay owner-only).
CATALOG_TABLES = (
    "supplement_products",
    "supplement_product_ingredients",
    "consent_policies",
    "learning_dataset_versions",
)

_GUC_PLAINTEXT = "current_setting('app.current_subject', true)"
_GUC_HASH = "current_setting('app.current_subject_hash', true)"


def _parent_guc(owner_col: str) -> str:
    """Return the GUC expression matching a parent owner column type."""
    return _GUC_HASH if owner_col == "owner_subject_hash" else _GUC_PLAINTEXT


def upgrade() -> None:
    """Create owner-scoped + catalog policies for the request role."""
    for table_name in PLAINTEXT_OWNER_TABLES:
        op.execute(f"""
            CREATE POLICY {POLICY} ON public.{table_name}
              FOR ALL TO {APP_ROLE}
              USING (owner_subject = {_GUC_PLAINTEXT})
              WITH CHECK (owner_subject = {_GUC_PLAINTEXT})
            """)
    for table_name in HASHED_OWNER_TABLES:
        op.execute(f"""
            CREATE POLICY {POLICY} ON public.{table_name}
              FOR ALL TO {APP_ROLE}
              USING (owner_subject_hash = {_GUC_HASH})
              WITH CHECK (owner_subject_hash = {_GUC_HASH})
            """)
    for table_name, parent, fk_col, owner_col in CHILD_TABLES:
        guc = _parent_guc(owner_col)
        op.execute(f"""
            CREATE POLICY {POLICY} ON public.{table_name}
              FOR ALL TO {APP_ROLE}
              USING (EXISTS (
                  SELECT 1 FROM public.{parent} parent
                  WHERE parent.id = public.{table_name}.{fk_col}
                    AND parent.{owner_col} = {guc}))
              WITH CHECK (EXISTS (
                  SELECT 1 FROM public.{parent} parent
                  WHERE parent.id = public.{table_name}.{fk_col}
                    AND parent.{owner_col} = {guc}))
            """)
    for table_name in CATALOG_TABLES:
        op.execute(f"""
            CREATE POLICY {CATALOG_POLICY} ON public.{table_name}
              FOR SELECT TO {APP_ROLE}
              USING (true)
            """)


def downgrade() -> None:
    """Drop every policy created in upgrade()."""
    for table_name in (*PLAINTEXT_OWNER_TABLES, *HASHED_OWNER_TABLES):
        op.execute(f"DROP POLICY IF EXISTS {POLICY} ON public.{table_name}")
    for table_name, *_ in CHILD_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {POLICY} ON public.{table_name}")
    for table_name in CATALOG_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {CATALOG_POLICY} ON public.{table_name}")
