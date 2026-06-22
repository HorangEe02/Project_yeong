"""Add chatbot unknown backlog and AnswerCard evidence fields.

Revision ID: 0033_add_chatbot_unknown_backlog
Revises: 0032_create_medical_source_governance_tables
Create Date: 2026-05-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0033_add_chatbot_unknown_backlog"
down_revision: str | None = "0032_create_medical_source_governance_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add unknown backlog storage and evidence structure fields."""
    empty_jsonb = sa.text("'[]'::jsonb")
    for column_name in (
        "specific_examples",
        "checklist",
        "caution_conditions",
        "must_not_say",
    ):
        op.add_column(
            "medical_evidence_items",
            sa.Column(
                column_name,
                postgresql.JSONB(astext_type=sa.Text()),
                server_default=empty_jsonb,
                nullable=False,
            ),
        )

    op.create_table(
        "chatbot_unknown_knowledge_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("answerability", sa.String(length=48), nullable=False),
        sa.Column("primary_intent", sa.String(length=80), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column(
            "related_conditions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=empty_jsonb,
            nullable=False,
        ),
        sa.Column(
            "missing_topics",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=empty_jsonb,
            nullable=False,
        ),
        sa.Column("retrieval_status", sa.String(length=48), nullable=False),
        sa.Column(
            "retrieval_warnings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=empty_jsonb,
            nullable=False,
        ),
        sa.Column("needed_evidence_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
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
            "answerability = 'unknown_no_reviewed_source'",
            name=op.f("ck_chatbot_unknown_knowledge_events_answerability"),
        ),
        sa.CheckConstraint(
            "retrieval_status IN ('no_match', 'stale_only', 'not_reviewed_only')",
            name=op.f("ck_chatbot_unknown_knowledge_events_retrieval_status"),
        ),
        sa.CheckConstraint(
            "status IN ('open', 'reviewed', 'dismissed')",
            name=op.f("ck_chatbot_unknown_knowledge_events_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chatbot_unknown_knowledge_events")),
    )
    op.create_index(
        "ix_chatbot_unknown_knowledge_events_status_category_created",
        "chatbot_unknown_knowledge_events",
        ["status", "category", "created_at"],
    )


def downgrade() -> None:
    """Remove unknown backlog storage and evidence structure fields."""
    op.drop_index(
        "ix_chatbot_unknown_knowledge_events_status_category_created",
        table_name="chatbot_unknown_knowledge_events",
    )
    op.drop_table("chatbot_unknown_knowledge_events")
    for column_name in (
        "must_not_say",
        "caution_conditions",
        "checklist",
        "specific_examples",
    ):
        op.drop_column("medical_evidence_items", column_name)
