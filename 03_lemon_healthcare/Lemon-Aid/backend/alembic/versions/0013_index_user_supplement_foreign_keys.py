"""Index user supplement foreign keys.

Revision ID: 0013_index_user_supplement_foreign_keys
Revises: 0012_configure_learning_private_storage_bucket
Create Date: 2026-05-25 13:55:00.000000

Supabase performance advisor flagged two user_supplements foreign keys without
covering indexes. These indexes keep confirmed supplement joins and SET NULL
referential actions from degrading as user-confirmed data grows.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0013_index_user_supplement_foreign_keys"
down_revision: str | Sequence[str] | None = "0012_configure_learning_private_storage_bucket"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add covering indexes for user_supplements foreign keys."""
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_user_supplements_source_analysis_run_id
        ON public.user_supplements (source_analysis_run_id)
        """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_user_supplements_matched_product_id
        ON public.user_supplements (matched_product_id)
        """)


def downgrade() -> None:
    """Drop user_supplements foreign-key covering indexes."""
    op.execute("DROP INDEX IF EXISTS public.ix_user_supplements_matched_product_id")
    op.execute("DROP INDEX IF EXISTS public.ix_user_supplements_source_analysis_run_id")
