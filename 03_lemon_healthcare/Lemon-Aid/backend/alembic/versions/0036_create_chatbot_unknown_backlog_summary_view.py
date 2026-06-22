"""Create chatbot unknown backlog summary view.

Revision ID: 0036_create_chatbot_unknown_backlog_summary_view
Revises: 0035_seed_chatbot_policy_boundaries
Create Date: 2026-05-29
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0036_create_chatbot_unknown_backlog_summary_view"
down_revision: str | None = "0035_seed_chatbot_policy_boundaries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create a privacy-safe operational triage view for unknown events."""
    op.execute("""
        CREATE OR REPLACE VIEW chatbot_unknown_knowledge_backlog_summary
        WITH (security_invoker = true) AS
        SELECT
            e.status,
            e.category,
            e.primary_intent,
            COALESCE(missing_topic.value, 'unknown_topic') AS missing_topic,
            e.needed_evidence_type,
            e.retrieval_status,
            COUNT(*)::integer AS event_count,
            MAX(e.created_at) AS latest_event_at
        FROM chatbot_unknown_knowledge_events AS e
        LEFT JOIN LATERAL jsonb_array_elements_text(e.missing_topics) AS missing_topic(value)
            ON true
        GROUP BY
            e.status,
            e.category,
            e.primary_intent,
            COALESCE(missing_topic.value, 'unknown_topic'),
            e.needed_evidence_type,
            e.retrieval_status
        """)
    op.execute("""
        COMMENT ON VIEW chatbot_unknown_knowledge_backlog_summary IS
            'Privacy-safe aggregate of chatbot unknown knowledge gaps. Contains structured topic metadata only.';
        """)


def downgrade() -> None:
    """Drop the unknown backlog summary view."""
    op.execute("DROP VIEW IF EXISTS chatbot_unknown_knowledge_backlog_summary;")
