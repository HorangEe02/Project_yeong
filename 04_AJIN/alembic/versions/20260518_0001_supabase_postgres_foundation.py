"""Supabase/PostgreSQL foundation tables.

Revision ID: 20260518_0001
Revises:
Create Date: 2026-05-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260518_0001"
down_revision = None
branch_labels = None
depends_on = None


def _now_col() -> sa.Column:
    """Return a portable created-at timestamp column."""
    return sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"))


def _updated_col() -> sa.Column:
    """Return a portable updated-at timestamp column."""
    return sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"))


def _lineage_cols() -> list[sa.Column]:
    """Return common data lineage columns for migrated rows."""
    return [
        sa.Column("data_class", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("source_system", sa.String(80), nullable=False, server_default="unknown"),
        sa.Column("source_label", sa.String(255), nullable=False, server_default=""),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
    ]


def _enable_rls(*tables: str) -> None:
    """Enable RLS for Supabase-exposed Postgres tables.

    Args:
        tables: Table names to protect with Row Level Security.
    """
    if op.get_context().dialect.name != "postgresql":
        return
    for table in tables:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))


def upgrade() -> None:
    """Create the first Supabase/PostgreSQL foundation schema."""
    op.create_table(
        "roles",
        sa.Column("role_id", sa.Integer, primary_key=True),
        sa.Column("role_name", sa.String(80), nullable=False, unique=True),
        sa.Column("role_level", sa.Integer, nullable=False, server_default="1"),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        _now_col(),
    )

    op.create_table(
        "users",
        sa.Column("user_id", sa.Integer, primary_key=True),
        sa.Column("employee_id", sa.String(80), nullable=False, unique=True),
        sa.Column("username", sa.String(160), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, server_default=""),
        sa.Column("phone", sa.String(80), nullable=False, server_default=""),
        sa.Column("department", sa.String(160), nullable=False, server_default=""),
        sa.Column("position", sa.String(160), nullable=False, server_default=""),
        sa.Column("password_hash", sa.Text, nullable=False, server_default=""),
        sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.role_id"), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("must_change_pw", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("failed_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        _now_col(),
        _updated_col(),
        *_lineage_cols(),
    )
    op.create_index("ix_users_employee_id", "users", ["employee_id"])

    op.create_table(
        "login_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.user_id"), nullable=True),
        sa.Column("employee_id", sa.String(80), nullable=False),
        sa.Column("action", sa.String(80), nullable=False, server_default="login"),
        sa.Column("success", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("ip_address", sa.String(120), nullable=False, server_default=""),
        sa.Column("user_agent", sa.Text, nullable=False, server_default=""),
        _now_col(),
        *_lineage_cols(),
    )
    op.create_index("ix_login_history_employee_created", "login_history", ["employee_id", "created_at"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("actor_employee_id", sa.String(80), nullable=False, server_default=""),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("resource_type", sa.String(120), nullable=False, server_default=""),
        sa.Column("resource_id", sa.String(160), nullable=False, server_default=""),
        sa.Column("success", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("payload", sa.JSON, nullable=False, server_default=sa.text("'{}'")),
        _now_col(),
        *_lineage_cols(),
    )
    op.create_index("ix_audit_logs_action_created", "audit_logs", ["action", "created_at"])

    op.create_table(
        "employees",
        sa.Column("employee_id", sa.String(80), primary_key=True),
        sa.Column("canonical_employee_id", sa.String(80), nullable=False, server_default=""),
        sa.Column("name", sa.String(160), nullable=False, server_default=""),
        sa.Column("department", sa.String(160), nullable=False, server_default=""),
        sa.Column("position", sa.String(160), nullable=False, server_default=""),
        sa.Column("email", sa.String(255), nullable=False, server_default=""),
        sa.Column("phone", sa.String(80), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        _now_col(),
        _updated_col(),
        *_lineage_cols(),
    )

    op.create_table(
        "employee_search_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("employee_id", sa.String(80), nullable=False, server_default=""),
        sa.Column("query", sa.Text, nullable=False),
        sa.Column("result_count", sa.Integer, nullable=False, server_default="0"),
        _now_col(),
        *_lineage_cols(),
    )

    op.create_table(
        "regulation_changes",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("source", sa.String(120), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("severity", sa.String(40), nullable=False, server_default="MEDIUM"),
        sa.Column("status", sa.String(40), nullable=False, server_default="new"),
        sa.Column("url", sa.Text, nullable=False, server_default=""),
        sa.Column("payload", sa.JSON, nullable=False, server_default=sa.text("'{}'")),
        _now_col(),
        _updated_col(),
        *_lineage_cols(),
    )
    op.create_index("ix_regulation_changes_status_created", "regulation_changes", ["status", "created_at"])

    op.create_table(
        "crawl_history",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("crawler_name", sa.String(120), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("items_seen", sa.Integer, nullable=False, server_default="0"),
        sa.Column("items_changed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.Text, nullable=False, server_default=""),
        _now_col(),
        *_lineage_cols(),
    )

    op.create_table(
        "notification_outbox",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.Column("target", sa.String(255), nullable=False, server_default=""),
        sa.Column("status", sa.String(40), nullable=False, server_default="queued"),
        sa.Column("payload", sa.JSON, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
        _now_col(),
        _updated_col(),
        *_lineage_cols(),
    )
    op.create_index("ix_notification_outbox_status", "notification_outbox", ["status", "available_at"])

    op.create_table(
        "notification_logs",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("outbox_id", sa.String(80), nullable=False, server_default=""),
        sa.Column("channel", sa.String(80), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("response", sa.Text, nullable=False, server_default=""),
        _now_col(),
        *_lineage_cols(),
    )

    op.create_table(
        "live_alarms",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("domain", sa.String(80), nullable=False, server_default="equipment"),
        sa.Column("severity", sa.String(40), nullable=False, server_default="info"),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", sa.JSON, nullable=False, server_default=sa.text("'{}'")),
        _now_col(),
        *_lineage_cols(),
    )
    op.create_index("ix_live_alarms_created", "live_alarms", ["created_at"])

    op.create_table(
        "feedback_events",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("message_id", sa.String(120), nullable=False),
        sa.Column("employee_id", sa.String(80), nullable=False, server_default="anonymous"),
        sa.Column("rating", sa.String(40), nullable=False),
        _now_col(),
        *_lineage_cols(),
    )
    op.create_index("ix_feedback_events_message", "feedback_events", ["message_id", "created_at"])

    op.create_table(
        "draft_versions",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("employee_id", sa.String(80), nullable=False),
        sa.Column("doc_type", sa.String(120), nullable=False, server_default=""),
        sa.Column("title", sa.Text, nullable=False, server_default=""),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("metadata", sa.JSON, nullable=False, server_default=sa.text("'{}'")),
        _now_col(),
        _updated_col(),
        *_lineage_cols(),
    )
    op.create_index("ix_draft_versions_employee", "draft_versions", ["employee_id", "updated_at"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("employee_id", sa.String(80), nullable=False),
        sa.Column("role", sa.String(40), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("metadata", sa.JSON, nullable=False, server_default=sa.text("'{}'")),
        _now_col(),
        *_lineage_cols(),
    )
    op.create_index("ix_chat_messages_employee", "chat_messages", ["employee_id", "created_at"])

    op.create_table(
        "attachments",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("employee_id", sa.String(80), nullable=False),
        sa.Column("bucket", sa.String(120), nullable=False),
        sa.Column("object_path", sa.Text, nullable=False),
        sa.Column("content_type", sa.String(160), nullable=False, server_default=""),
        sa.Column("size_bytes", sa.Integer, nullable=False, server_default="0"),
        sa.Column("metadata", sa.JSON, nullable=False, server_default=sa.text("'{}'")),
        _now_col(),
        *_lineage_cols(),
    )

    op.create_table(
        "plc_violations",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("line_id", sa.String(80), nullable=False, server_default=""),
        sa.Column("process_id", sa.String(80), nullable=False, server_default=""),
        sa.Column("rule_number", sa.Integer, nullable=False, server_default="0"),
        sa.Column("severity", sa.String(40), nullable=False, server_default="info"),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("payload", sa.JSON, nullable=False, server_default=sa.text("'{}'")),
        _now_col(),
        *_lineage_cols(),
    )
    op.create_index("ix_plc_violations_created", "plc_violations", ["created_at"])

    _enable_rls(
        "roles",
        "users",
        "login_history",
        "audit_logs",
        "employees",
        "employee_search_history",
        "regulation_changes",
        "crawl_history",
        "notification_outbox",
        "notification_logs",
        "live_alarms",
        "feedback_events",
        "draft_versions",
        "chat_messages",
        "attachments",
        "plc_violations",
    )


def downgrade() -> None:
    """Drop the foundation schema."""
    for table in (
        "plc_violations",
        "attachments",
        "chat_messages",
        "draft_versions",
        "feedback_events",
        "live_alarms",
        "notification_logs",
        "notification_outbox",
        "crawl_history",
        "regulation_changes",
        "employee_search_history",
        "employees",
        "audit_logs",
        "login_history",
        "users",
        "roles",
    ):
        op.drop_table(table)
