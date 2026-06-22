"""Create medical source governance tables.

Revision ID: 0032_create_medical_source_governance_tables
Revises: 0031_create_reminder_preferences
Create Date: 2026-05-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0032_create_medical_source_governance_tables"
down_revision: str | None = "0031_create_reminder_preferences"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create reviewed medical source governance tables."""
    op.create_table(
        "medical_sources",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("source_family", sa.String(length=80), nullable=False),
        sa.Column("publisher", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("canonical_url", sa.String(length=1024), nullable=True),
        sa.Column("jurisdiction", sa.String(length=32), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("default_review_status", sa.String(length=32), nullable=False),
        sa.Column("owner", sa.String(length=120), nullable=False),
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
                "source_type IN ("
                "'guideline', 'public_health', 'regulator', "
                "'reference_intake', 'paper', 'internal_review'"
                ")"
            ),
            name=op.f("ck_medical_sources_source_type"),
        ),
        sa.CheckConstraint(
            "default_review_status IN ('draft', 'reviewed', 'deprecated', 'paper_candidate')",
            name=op.f("ck_medical_sources_default_review_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_medical_sources")),
    )
    op.create_index(
        "ix_medical_sources_family_status",
        "medical_sources",
        ["source_family", "default_review_status"],
    )

    op.create_table(
        "medical_source_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", sa.String(length=80), nullable=False),
        sa.Column("version_label", sa.String(length=80), nullable=False),
        sa.Column("published_at", sa.Date(), nullable=True),
        sa.Column("reviewed_at", sa.Date(), nullable=False),
        sa.Column("expires_at", sa.Date(), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("reviewer", sa.String(length=120), nullable=False),
        sa.Column("review_note", sa.Text(), nullable=True),
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
            "review_status IN ('draft', 'reviewed', 'deprecated', 'paper_candidate')",
            name=op.f("ck_medical_source_versions_review_status"),
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["medical_sources.id"],
            name=op.f("fk_medical_source_versions_source_id_medical_sources"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_medical_source_versions")),
    )
    op.create_index(
        "ix_medical_source_versions_source_status_expires",
        "medical_source_versions",
        ["source_id", "review_status", "expires_at"],
    )

    op.create_table(
        "medical_evidence_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic", sa.String(length=120), nullable=False),
        sa.Column("audience", sa.String(length=80), nullable=False),
        sa.Column("claim_summary", sa.Text(), nullable=False),
        sa.Column("allowed_user_wording", sa.Text(), nullable=False),
        sa.Column("blocked_wording", sa.Text(), nullable=False),
        sa.Column("applicability_note", sa.Text(), nullable=True),
        sa.Column("caution_level", sa.String(length=32), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("algorithm_version", sa.String(length=80), nullable=True),
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
            "caution_level IN ('info', 'caution', 'professional_review', 'blocked')",
            name=op.f("ck_medical_evidence_items_caution_level"),
        ),
        sa.CheckConstraint(
            "review_status IN ('draft', 'reviewed', 'deprecated', 'paper_candidate')",
            name=op.f("ck_medical_evidence_items_review_status"),
        ),
        sa.ForeignKeyConstraint(
            ["source_version_id"],
            ["medical_source_versions.id"],
            name=op.f("fk_medical_evidence_items_source_version_id_medical_source_versions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_medical_evidence_items")),
    )
    op.create_index(
        "ix_medical_evidence_items_topic_audience_status",
        "medical_evidence_items",
        ["topic", "audience", "review_status"],
    )

    op.create_table(
        "medical_policy_boundaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("boundary_code", sa.String(length=120), nullable=False),
        sa.Column("topic", sa.String(length=120), nullable=False),
        sa.Column("trigger_intent", sa.String(length=120), nullable=False),
        sa.Column("response_status", sa.String(length=32), nullable=False),
        sa.Column("required_warning_code", sa.String(length=120), nullable=False),
        sa.Column("allowed_response_pattern", sa.Text(), nullable=False),
        sa.Column("blocked_response_pattern", sa.Text(), nullable=False),
        sa.Column("source_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("review_status", sa.String(length=32), nullable=False),
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
            "response_status IN ('blocked', 'professional_review', 'caution', 'needs_more_info')",
            name=op.f("ck_medical_policy_boundaries_response_status"),
        ),
        sa.CheckConstraint(
            "review_status IN ('draft', 'reviewed', 'deprecated')",
            name=op.f("ck_medical_policy_boundaries_review_status"),
        ),
        sa.ForeignKeyConstraint(
            ["source_version_id"],
            ["medical_source_versions.id"],
            name=op.f("fk_medical_policy_boundaries_source_version_id_medical_source_versions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_medical_policy_boundaries")),
    )
    op.create_index(
        "ix_medical_policy_boundaries_code_status",
        "medical_policy_boundaries",
        ["boundary_code", "review_status"],
    )

    op.create_table(
        "medical_rag_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("chunk_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding_status", sa.String(length=32), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.Date(), nullable=False),
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
            "embedding_status IN ('not_indexed', 'indexed', 'stale', 'disabled')",
            name=op.f("ck_medical_rag_chunks_embedding_status"),
        ),
        sa.CheckConstraint(
            "review_status IN ('draft', 'reviewed', 'deprecated')",
            name=op.f("ck_medical_rag_chunks_review_status"),
        ),
        sa.ForeignKeyConstraint(
            ["evidence_item_id"],
            ["medical_evidence_items.id"],
            name=op.f("fk_medical_rag_chunks_evidence_item_id_medical_evidence_items"),
        ),
        sa.ForeignKeyConstraint(
            ["source_version_id"],
            ["medical_source_versions.id"],
            name=op.f("fk_medical_rag_chunks_source_version_id_medical_source_versions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_medical_rag_chunks")),
    )
    op.create_index(
        "ix_medical_rag_chunks_status_embedding_expires",
        "medical_rag_chunks",
        ["review_status", "embedding_status", "expires_at"],
    )
    op.create_index(
        "ix_medical_rag_chunks_chunk_hash",
        "medical_rag_chunks",
        ["chunk_hash"],
        unique=True,
    )


def downgrade() -> None:
    """Drop reviewed medical source governance tables."""
    op.drop_index("ix_medical_rag_chunks_chunk_hash", table_name="medical_rag_chunks")
    op.drop_index(
        "ix_medical_rag_chunks_status_embedding_expires",
        table_name="medical_rag_chunks",
    )
    op.drop_table("medical_rag_chunks")
    op.drop_index(
        "ix_medical_policy_boundaries_code_status",
        table_name="medical_policy_boundaries",
    )
    op.drop_table("medical_policy_boundaries")
    op.drop_index(
        "ix_medical_evidence_items_topic_audience_status",
        table_name="medical_evidence_items",
    )
    op.drop_table("medical_evidence_items")
    op.drop_index(
        "ix_medical_source_versions_source_status_expires",
        table_name="medical_source_versions",
    )
    op.drop_table("medical_source_versions")
    op.drop_index("ix_medical_sources_family_status", table_name="medical_sources")
    op.drop_table("medical_sources")
