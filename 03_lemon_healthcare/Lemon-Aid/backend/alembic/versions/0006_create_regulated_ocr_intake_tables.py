"""Create regulated OCR intake tables.

Revision ID: 0006_create_regulated_ocr_intake
Revises: 0005_create_learning_vector_tables
Create Date: 2026-05-15 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_create_regulated_ocr_intake"
down_revision: str | Sequence[str] | None = "0005_create_learning_vector_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply this migration."""
    op.create_table(
        "regulated_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_subject_hash", sa.String(length=64), nullable=False),
        sa.Column("document_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("image_sha256", sa.String(length=64), nullable=False),
        sa.Column("image_mime_type", sa.String(length=32), nullable=False),
        sa.Column("image_size_bytes", sa.Integer(), nullable=False),
        sa.Column("ocr_provider", sa.String(length=64), nullable=True),
        sa.Column("ocr_confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("ocr_text_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "parsed_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "warning_codes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "consult_cta",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("algorithm_version", sa.String(length=64), nullable=False),
        sa.Column("raw_image_deleted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
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
            "length(owner_subject_hash) = 64",
            name=op.f("ck_regulated_documents_owner_subject_hash_length"),
        ),
        sa.CheckConstraint(
            "document_type IN ('prescription', 'lab_result')",
            name=op.f("ck_regulated_documents_regulated_document_type_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('requires_confirmation', 'confirmed', 'expired', 'failed')",
            name=op.f("ck_regulated_documents_regulated_document_status_allowed"),
        ),
        sa.CheckConstraint(
            "image_mime_type IN ('image/jpeg', 'image/png', 'image/webp')",
            name=op.f("ck_regulated_documents_regulated_document_image_mime_type_allowed"),
        ),
        sa.CheckConstraint(
            "image_size_bytes > 0",
            name=op.f("ck_regulated_documents_regulated_document_image_size_positive"),
        ),
        sa.CheckConstraint(
            "ocr_confidence IS NULL OR (ocr_confidence >= 0 AND ocr_confidence <= 1)",
            name=op.f("ck_regulated_documents_regulated_document_ocr_confidence_range"),
        ),
        sa.CheckConstraint(
            "length(image_sha256) = 64",
            name=op.f("ck_regulated_documents_regulated_document_image_sha_length"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_regulated_documents")),
    )
    op.create_index(
        "ix_regulated_documents_owner_created_at",
        "regulated_documents",
        ["owner_subject_hash", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_regulated_documents_owner_status_created_at",
        "regulated_documents",
        ["owner_subject_hash", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_regulated_documents_expires_at",
        "regulated_documents",
        ["expires_at"],
        unique=False,
    )

    op.create_table(
        "prescription_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("medication_name_text", sa.String(length=160), nullable=False),
        sa.Column("dose_text", sa.String(length=80), nullable=True),
        sa.Column("frequency_text", sa.String(length=120), nullable=True),
        sa.Column("period_text", sa.String(length=80), nullable=True),
        sa.Column("route_text", sa.String(length=80), nullable=True),
        sa.Column("prescribed_date_text", sa.String(length=40), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
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
            "medication_name_text <> ''",
            name=op.f("ck_prescription_items_prescription_medication_nonempty"),
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name=op.f("ck_prescription_items_prescription_item_confidence_range"),
        ),
        sa.CheckConstraint(
            "sort_order >= 0",
            name=op.f("ck_prescription_items_prescription_item_sort_order_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["regulated_documents.id"],
            name=op.f("fk_prescription_items_document_id_regulated_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prescription_items")),
    )
    op.create_index(
        "ix_prescription_items_document_id",
        "prescription_items",
        ["document_id"],
        unique=False,
    )

    op.create_table(
        "lab_result_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("test_name_text", sa.String(length=160), nullable=False),
        sa.Column("value_text", sa.String(length=80), nullable=True),
        sa.Column("unit_text", sa.String(length=40), nullable=True),
        sa.Column("reference_range_text", sa.String(length=120), nullable=True),
        sa.Column("measured_at_text", sa.String(length=40), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
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
            "test_name_text <> ''",
            name=op.f("ck_lab_result_items_lab_result_test_name_nonempty"),
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name=op.f("ck_lab_result_items_lab_result_item_confidence_range"),
        ),
        sa.CheckConstraint(
            "sort_order >= 0",
            name=op.f("ck_lab_result_items_lab_result_item_sort_order_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["regulated_documents.id"],
            name=op.f("fk_lab_result_items_document_id_regulated_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lab_result_items")),
    )
    op.create_index(
        "ix_lab_result_items_document_id",
        "lab_result_items",
        ["document_id"],
        unique=False,
    )


def downgrade() -> None:
    """Rollback this migration."""
    op.drop_index("ix_lab_result_items_document_id", table_name="lab_result_items")
    op.drop_table("lab_result_items")
    op.drop_index("ix_prescription_items_document_id", table_name="prescription_items")
    op.drop_table("prescription_items")
    op.drop_index("ix_regulated_documents_expires_at", table_name="regulated_documents")
    op.drop_index(
        "ix_regulated_documents_owner_status_created_at",
        table_name="regulated_documents",
    )
    op.drop_index("ix_regulated_documents_owner_created_at", table_name="regulated_documents")
    op.drop_table("regulated_documents")
