"""Create reminder preference table.

Revision ID: 0031_create_reminder_preferences
Revises: 0030_create_agent_memory_tables
Create Date: 2026-05-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0031_create_reminder_preferences"
down_revision: str | None = "0030_create_agent_memory_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create current-user reminder preference table."""
    op.create_table(
        "reminder_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_subject", sa.String(length=512), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("time_of_day", sa.String(length=5), nullable=False),
        sa.Column("timezone", sa.String(length=80), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("message", sa.String(length=240), nullable=False),
        sa.Column("preference_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
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
            (
                "category IN ("
                "'supplement_reminder', 'meal_check_in', "
                "'daily_coaching_prompt', 'safety_follow_up'"
                ")"
            ),
            name=op.f("ck_reminder_preferences_reminder_category_allowed"),
        ),
        sa.CheckConstraint(
            "time_of_day ~ '^[0-2][0-9]:[0-5][0-9]$'",
            name=op.f("ck_reminder_preferences_reminder_time_of_day_format"),
        ),
        sa.CheckConstraint(
            "message <> ''",
            name=op.f("ck_reminder_preferences_reminder_message_nonempty"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reminder_preferences")),
    )
    op.create_index(
        "ix_reminder_preferences_owner_enabled",
        "reminder_preferences",
        ["owner_subject", "enabled"],
    )
    op.create_index(
        "ix_reminder_preferences_owner_category",
        "reminder_preferences",
        ["owner_subject", "category"],
    )


def downgrade() -> None:
    """Drop current-user reminder preference table."""
    op.drop_index("ix_reminder_preferences_owner_category", table_name="reminder_preferences")
    op.drop_index("ix_reminder_preferences_owner_enabled", table_name="reminder_preferences")
    op.drop_table("reminder_preferences")
