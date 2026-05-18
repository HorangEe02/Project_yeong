"""initial: users, user_profiles, consent_records, access_audit_logs, supplements.

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-19

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-04-database-models.md Step 8
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=False)

    op.create_table(
        "user_profiles",
        sa.Column(
            "user_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("age", sa.Integer, nullable=False),
        sa.Column("sex", sa.String(8), nullable=False),
        sa.Column("height_cm", sa.Float, nullable=False),
        sa.Column("weight_kg", sa.Float, nullable=False),
        sa.Column("is_pregnant", sa.Boolean, nullable=False),
        sa.Column("is_lactating", sa.Boolean, nullable=False),
        sa.Column("is_smoker", sa.Boolean, nullable=False),
        sa.Column("chronic_diseases", sa.JSON, nullable=False),
        sa.Column("medications", sa.JSON, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "consent_records",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("consent_type", sa.String(32), nullable=False),
        sa.Column("purpose", sa.String(255), nullable=False),
        sa.Column("data_categories", sa.JSON, nullable=False),
        sa.Column("retention_period_days", sa.Integer, nullable=False),
        sa.Column("policy_version", sa.String(32), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_consent_records_user_id", "consent_records", ["user_id"], unique=False)

    op.create_table(
        "access_audit_logs",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("actor_user_id", PgUUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(32), nullable=False),
        sa.Column("resource_id", sa.String(64), nullable=True),
        sa.Column("ip_address_hash", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("success", sa.Boolean, nullable=False),
        sa.Column("error_code", sa.String(32), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_access_audit_logs_actor_user_id",
        "access_audit_logs",
        ["actor_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_access_audit_logs_occurred_at",
        "access_audit_logs",
        ["occurred_at"],
        unique=False,
    )

    op.create_table(
        "supplements",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("product_name", sa.String(200), nullable=True),
        sa.Column("manufacturer", sa.String(100), nullable=True),
        sa.Column("ingredients", sa.JSON, nullable=False),
        sa.Column("ocr_engine", sa.String(50), nullable=False),
        sa.Column("llm_engine", sa.String(50), nullable=False),
        sa.Column("image_hash", sa.String(12), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_supplements_user_id", "supplements", ["user_id"], unique=False)
    op.create_index(
        "ix_supplements_registered_at",
        "supplements",
        ["registered_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_supplements_registered_at", table_name="supplements")
    op.drop_index("ix_supplements_user_id", table_name="supplements")
    op.drop_table("supplements")

    op.drop_index("ix_access_audit_logs_occurred_at", table_name="access_audit_logs")
    op.drop_index("ix_access_audit_logs_actor_user_id", table_name="access_audit_logs")
    op.drop_table("access_audit_logs")

    op.drop_index("ix_consent_records_user_id", table_name="consent_records")
    op.drop_table("consent_records")

    op.drop_table("user_profiles")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
