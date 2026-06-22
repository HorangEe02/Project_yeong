"""Create user medications table.

Revision ID: 0037_create_user_medications
Revises: 0036_create_chatbot_unknown_backlog_summary_view
Create Date: 2026-05-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0037_create_user_medications"
down_revision: str | Sequence[str] | None = "0036_create_chatbot_unknown_backlog_summary_view"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create privacy-scoped saved medication storage."""
    op.create_table(
        "user_medications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_subject_hash", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("normalized_name", sa.String(length=160), nullable=True),
        sa.Column("medication_class", sa.String(length=80), nullable=True),
        sa.Column(
            "condition_tags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "confirmation_status",
            sa.String(length=32),
            server_default=sa.text("'user_confirmed'"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "last_confirmed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
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
            "display_name <> ''",
            name=op.f("ck_user_medications_display_name_nonempty"),
        ),
        sa.CheckConstraint(
            "normalized_name IS NULL OR normalized_name <> ''",
            name=op.f("ck_user_medications_normalized_name_nonempty"),
        ),
        sa.CheckConstraint(
            "medication_class IS NULL OR medication_class <> ''",
            name=op.f("ck_user_medications_medication_class_nonempty"),
        ),
        sa.CheckConstraint(
            "confirmation_status IN ('user_confirmed')",
            name=op.f("ck_user_medications_confirmation_status_allowed"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_medications")),
    )
    op.create_index(
        "ix_user_medications_owner_active",
        "user_medications",
        ["owner_subject_hash", "is_active"],
        unique=False,
    )
    op.create_index(
        "ix_user_medications_owner_normalized",
        "user_medications",
        ["owner_subject_hash", "normalized_name"],
        unique=False,
    )
    op.execute("""
        COMMENT ON TABLE user_medications IS
            'User-confirmed medication names for chatbot context. Structured fields only.';
        """)


def downgrade() -> None:
    """Drop user medication storage."""
    op.drop_index("ix_user_medications_owner_normalized", table_name="user_medications")
    op.drop_index("ix_user_medications_owner_active", table_name="user_medications")
    op.drop_table("user_medications")
