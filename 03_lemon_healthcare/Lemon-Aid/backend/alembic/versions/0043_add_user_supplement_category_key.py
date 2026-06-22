"""Add user-chosen supplement category key.

Revision ID: 0043_add_user_supplement_category_key
Revises: 0042_allow_daily_health_score_analysis_type
Create Date: 2026-06-13 00:00:00.000000

Stores only a curated category key the user selected from the existing
``supplement_categories`` catalog. It intentionally does not store raw OCR
text, provider payloads, image bytes, URLs, or secrets. The column is a soft
reference (no FK) validated in the registration service so catalog churn never
blocks a stored record.

Row-level security: ``user_supplements`` already has owner RLS policies and
FORCE ROW LEVEL SECURITY (migrations 0020/0023b/0023c). A new column is covered
by the existing row policies automatically, so no policy change is needed.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0043_add_user_supplement_category_key"
down_revision: str | Sequence[str] | None = "0042_allow_daily_health_score_analysis_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the nullable user-chosen supplement category key column."""
    op.add_column(
        "user_supplements",
        sa.Column("category_key", sa.String(length=120), nullable=True),
    )
    op.create_check_constraint(
        "category_key_nonempty",
        "user_supplements",
        "category_key IS NULL OR category_key <> ''",
    )


def downgrade() -> None:
    """Remove the user-chosen supplement category key column."""
    op.drop_constraint(
        "category_key_nonempty",
        "user_supplements",
        type_="check",
    )
    op.drop_column("user_supplements", "category_key")
