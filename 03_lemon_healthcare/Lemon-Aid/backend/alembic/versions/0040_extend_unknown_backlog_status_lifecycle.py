"""Extend unknown backlog status lifecycle.

Revision ID: 0040_extend_unknown_backlog_status_lifecycle
Revises: 0039_seed_lithium_supplement_boundary
Create Date: 2026-06-01
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0040_extend_unknown_backlog_status_lifecycle"
down_revision: str | Sequence[str] | None = "0039_seed_lithium_supplement_boundary"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "chatbot_unknown_knowledge_events"
CONSTRAINT_NAME = "ck_chatbot_unknown_knowledge_events_status"


def upgrade() -> None:
    """Allow privacy-safe unknown topics to move through review operations."""
    op.drop_constraint(op.f(CONSTRAINT_NAME), TABLE_NAME, type_="check")
    op.create_check_constraint(
        op.f(CONSTRAINT_NAME),
        TABLE_NAME,
        "status IN ('open', 'reviewing', 'promoted', 'dismissed', 'deprecated')",
    )


def downgrade() -> None:
    """Restore the previous compact status contract."""
    op.execute("""
        UPDATE chatbot_unknown_knowledge_events
        SET status = CASE
            WHEN status = 'reviewing' THEN 'open'
            WHEN status = 'promoted' THEN 'reviewed'
            WHEN status = 'deprecated' THEN 'dismissed'
            ELSE status
        END
        WHERE status IN ('reviewing', 'promoted', 'deprecated');
        """)
    op.drop_constraint(op.f(CONSTRAINT_NAME), TABLE_NAME, type_="check")
    op.create_check_constraint(
        op.f(CONSTRAINT_NAME),
        TABLE_NAME,
        "status IN ('open', 'reviewed', 'dismissed')",
    )
