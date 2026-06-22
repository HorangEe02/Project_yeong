"""Configure private Supabase Storage bucket for learning images.

Revision ID: 0012_configure_learning_private_storage_bucket
Revises: 0011_add_learning_review_metadata
Create Date: 2026-05-25 12:45:00.000000

The learning image pipeline stores original user-uploaded images only in a
private Storage/S3-compatible bucket after explicit opt-in and review gates.
This migration is idempotent and skips non-Supabase Postgres instances that do
not have the storage schema installed.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0012_configure_learning_private_storage_bucket"
down_revision: str | Sequence[str] | None = "0011_add_learning_review_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEARNING_STORAGE_BUCKET = "learning-images"
LEARNING_STORAGE_FILE_SIZE_LIMIT_BYTES = 20 * 1024 * 1024


def upgrade() -> None:
    """Create or harden the private learning image Storage bucket."""
    op.execute(f"""
        DO $$
        BEGIN
            IF to_regclass('storage.buckets') IS NULL THEN
                RAISE NOTICE 'storage.buckets not found; skipping {LEARNING_STORAGE_BUCKET} bucket setup';
                RETURN;
            END IF;

            INSERT INTO storage.buckets (
                id,
                name,
                public,
                file_size_limit,
                allowed_mime_types
            )
            VALUES (
                '{LEARNING_STORAGE_BUCKET}',
                '{LEARNING_STORAGE_BUCKET}',
                false,
                {LEARNING_STORAGE_FILE_SIZE_LIMIT_BYTES},
                ARRAY['image/jpeg', 'image/png', 'image/webp']::text[]
            )
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                public = false,
                file_size_limit = EXCLUDED.file_size_limit,
                allowed_mime_types = EXCLUDED.allowed_mime_types,
                updated_at = now();
        END
        $$;
        """)


def downgrade() -> None:
    """Remove only the dedicated learning image Storage bucket if present."""
    op.execute(f"""
        DO $$
        BEGIN
            IF to_regclass('storage.buckets') IS NOT NULL THEN
                DELETE FROM storage.buckets
                WHERE id = '{LEARNING_STORAGE_BUCKET}';
            END IF;
        END
        $$;
        """)
