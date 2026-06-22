"""Create users table.

Revision ID: 0001_create_users
Revises: None
Create Date: 2026-05-11 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_create_users"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply this migration."""
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sex", sa.String(length=16), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("height_cm", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("base_weight_kg", sa.Numeric(precision=5, scale=2), nullable=False),
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
        sa.CheckConstraint("base_weight_kg > 0", name=op.f("ck_users_base_weight_kg_positive")),
        sa.CheckConstraint("height_cm > 0", name=op.f("ck_users_height_cm_positive")),
        sa.CheckConstraint("sex IN ('male', 'female')", name=op.f("ck_users_sex_allowed")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(op.f("ix_users_sex"), "users", ["sex"], unique=False)


def downgrade() -> None:
    """Rollback this migration."""
    op.drop_index(op.f("ix_users_sex"), table_name="users")
    op.drop_table("users")
