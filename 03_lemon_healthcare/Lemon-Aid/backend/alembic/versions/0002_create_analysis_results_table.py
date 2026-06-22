"""Create analysis results table.

Revision ID: 0002_create_analysis_results
Revises: 0001_create_users
Create Date: 2026-05-11 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_create_analysis_results"
down_revision: str | Sequence[str] | None = "0001_create_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply this migration."""
    op.create_table(
        "analysis_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_subject", sa.String(length=512), nullable=False),
        sa.Column("analysis_type", sa.String(length=32), nullable=False),
        sa.Column("algorithm_version", sa.String(length=64), nullable=False),
        sa.Column("kdris_source_manifest_version", sa.String(length=32), nullable=True),
        sa.Column("input_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "analysis_type IN ('activity_score', 'weight_prediction', 'nutrition_analysis')",
            name=op.f("ck_analysis_results_analysis_type_allowed"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_results")),
    )
    op.create_index(
        "ix_analysis_results_owner_created_at",
        "analysis_results",
        ["owner_subject", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_analysis_results_owner_type_created_at",
        "analysis_results",
        ["owner_subject", "analysis_type", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Rollback this migration."""
    op.drop_index("ix_analysis_results_owner_type_created_at", table_name="analysis_results")
    op.drop_index("ix_analysis_results_owner_created_at", table_name="analysis_results")
    op.drop_table("analysis_results")
