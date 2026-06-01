"""Add users.photo_url column (base64 data URL for digital employee badge).

Revision ID: 20260526_0003
Revises: 20260518_0002
Create Date: 2026-05-26

Photo data URL (data:image/jpeg;base64,...) stored directly in auth.users.
256x256 JPEG (~30-70KB) — acceptable inline storage size for demo scale.
Future migration: Supabase Storage bucket + object_path reference.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260526_0003"
down_revision = "20260518_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent — IF NOT EXISTS via inspector check.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("users")}
    if "photo_url" not in cols:
        op.add_column(
            "users",
            sa.Column(
                "photo_url",
                sa.Text(),
                nullable=False,
                server_default=sa.text("''"),
            ),
        )


def downgrade() -> None:
    op.drop_column("users", "photo_url")
