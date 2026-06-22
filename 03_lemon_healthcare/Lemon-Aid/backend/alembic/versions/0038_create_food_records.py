"""Create food records table.

Revision ID: 0038_create_food_records
Revises: 0037_create_user_medications
Create Date: 2026-05-31
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0038_create_food_records"
down_revision: str | Sequence[str] | None = "0037_create_user_medications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create privacy-scoped food record storage."""
    op.create_table(
        "food_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_subject_hash", sa.String(length=128), nullable=False),
        sa.Column("recorded_date", sa.Date(), nullable=False),
        sa.Column("meal_type", sa.String(length=24), nullable=False),
        sa.Column(
            "display_items",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("amount_text", sa.String(length=120), nullable=True),
        sa.Column(
            "estimated_tags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "rough_nutrient_axes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("user_confirmed", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "source",
            sa.String(length=40),
            server_default=sa.text("'manual'"),
            nullable=False,
        ),
        sa.Column("food_db_match_id", sa.String(length=120), nullable=True),
        sa.Column("match_confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("nutrient_estimates", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
            "meal_type IN ('breakfast', 'lunch', 'dinner', 'snack', 'extra')",
            name=op.f("ck_food_records_meal_type_allowed"),
        ),
        sa.CheckConstraint(
            "source IN ('manual', 'food_user_input', 'food_ocr_confirmed')",
            name=op.f("ck_food_records_source_allowed"),
        ),
        sa.CheckConstraint(
            "match_confidence IS NULL OR (match_confidence >= 0 AND match_confidence <= 1)",
            name=op.f("ck_food_records_match_confidence_range"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_food_records")),
    )
    op.create_index(
        "ix_food_records_owner_date",
        "food_records",
        ["owner_subject_hash", "recorded_date"],
        unique=False,
    )
    op.create_index(
        "ix_food_records_owner_meal_date",
        "food_records",
        ["owner_subject_hash", "meal_type", "recorded_date"],
        unique=False,
    )
    op.execute("""
        COMMENT ON TABLE food_records IS
            'User-confirmed food records for app context and chatbot grounding. No raw OCR or prompts.';
        """)


def downgrade() -> None:
    """Drop food record storage."""
    op.drop_index("ix_food_records_owner_meal_date", table_name="food_records")
    op.drop_index("ix_food_records_owner_date", table_name="food_records")
    op.drop_table("food_records")
