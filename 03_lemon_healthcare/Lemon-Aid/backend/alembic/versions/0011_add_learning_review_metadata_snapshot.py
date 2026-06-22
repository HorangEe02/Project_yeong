"""Add sanitized learning review metadata snapshot.

Revision ID: 0011_add_learning_review_metadata
Revises: 0010_revoke_learning_api_grants
Create Date: 2026-05-25 12:30:00.000000

Manual review needs a durable structured metadata candidate after user
confirmation. This column stores only sanitized, user-confirmed metadata; raw
OCR text, raw image bytes, provider payloads, and credentials remain forbidden.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_add_learning_review_metadata"
down_revision: str | Sequence[str] | None = "0010_revoke_learning_api_grants"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add sanitized metadata snapshot storage for manual learning review."""
    op.add_column(
        "learning_image_objects",
        sa.Column(
            "review_metadata_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.alter_column(
        "learning_image_objects",
        "review_metadata_snapshot",
        server_default=None,
    )


def downgrade() -> None:
    """Remove manual review metadata snapshot storage."""
    op.drop_column("learning_image_objects", "review_metadata_snapshot")
