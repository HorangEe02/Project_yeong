"""Allow daily_health_score in the analysis_results type check constraint.

Revision ID: 0042_allow_daily_health_score_analysis_type
Revises: 0041_harden_ai_agent_chat_table_security
Create Date: 2026-06-12

The opt-in daily health score persistence (Settings.persist_daily_health_score,
decision #7) stores dashboard-computed scores as analysis_results rows with
analysis_type='daily_health_score'. The 0002 check constraint only allowed the
original three request-driven types, so the new value must be added before any
row can be written. No raw OCR text, provider payloads, or image bytes are
involved; RLS posture of analysis_results (0023b/0023c) is unchanged.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0042_allow_daily_health_score_analysis_type"
down_revision: str | Sequence[str] | None = "0041_harden_ai_agent_chat_table_security"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Bare name on purpose: alembic's naming convention wraps it into
# ck_analysis_results_analysis_type_allowed at execution time; passing the
# already-prefixed name double-wraps it (caught on the first live upgrade).
CONSTRAINT_NAME = "analysis_type_allowed"
TABLE_NAME = "analysis_results"
OLD_TYPES = "('activity_score', 'weight_prediction', 'nutrition_analysis')"
NEW_TYPES = "('activity_score', 'weight_prediction', 'nutrition_analysis', 'daily_health_score')"


def upgrade() -> None:
    """Recreate the type check constraint with daily_health_score included."""
    op.drop_constraint(CONSTRAINT_NAME, TABLE_NAME, type_="check")
    op.create_check_constraint(
        "analysis_type_allowed",
        TABLE_NAME,
        f"analysis_type IN {NEW_TYPES}",
    )


def downgrade() -> None:
    """Restore the original three-type constraint.

    daily_health_score rows would violate the restored constraint, so they are
    removed first. These rows are derived snapshots the dashboard can recompute;
    no user-entered data is lost.
    """
    op.execute(f"DELETE FROM {TABLE_NAME} WHERE analysis_type = 'daily_health_score'")
    op.drop_constraint(CONSTRAINT_NAME, TABLE_NAME, type_="check")
    op.create_check_constraint(
        "analysis_type_allowed",
        TABLE_NAME,
        f"analysis_type IN {OLD_TYPES}",
    )
