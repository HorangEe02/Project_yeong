"""Create AI Agent memory and run-log tables.

Revision ID: 0030_create_agent_memory_tables
Revises: 0029_create_wiki_gemma_embeddings
Create Date: 2026-05-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0030_create_agent_memory_tables"
down_revision: str | None = "0029_create_wiki_gemma_embeddings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create privacy-minimized Agent memory and execution metadata tables."""
    op.create_table(
        "agent_memory",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_subject_hash", sa.String(length=64), nullable=False),
        sa.Column("memory_type", sa.String(length=64), nullable=False),
        sa.Column("summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_counters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("last_source_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("algorithm_version", sa.String(length=64), nullable=False),
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
            "memory_type <> ''", name=op.f("ck_agent_memory_agent_memory_memory_type_nonempty")
        ),
        sa.CheckConstraint(
            "algorithm_version <> ''",
            name=op.f("ck_agent_memory_agent_memory_algorithm_version_nonempty"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_memory")),
        sa.UniqueConstraint("owner_subject_hash", "memory_type", name="uq_agent_memory_owner_type"),
    )
    op.create_index(
        "ix_agent_memory_owner_type", "agent_memory", ["owner_subject_hash", "memory_type"]
    )
    op.create_index(
        "ix_agent_memory_owner_updated_at", "agent_memory", ["owner_subject_hash", "updated_at"]
    )

    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_id", sa.String(length=80), nullable=False),
        sa.Column("owner_subject_hash", sa.String(length=64), nullable=False),
        sa.Column("agent_name", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("approval_status", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("latency_ms", sa.Numeric(12, 3), nullable=False),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("used_tools", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
            "status IN ('completed', 'failed')",
            name=op.f("ck_agent_runs_agent_runs_status_allowed"),
        ),
        sa.CheckConstraint(
            "approval_status IN ('confirmed', 'requires_confirmation')",
            name=op.f("ck_agent_runs_agent_runs_approval_status_allowed"),
        ),
        sa.CheckConstraint(
            "latency_ms >= 0", name=op.f("ck_agent_runs_agent_runs_latency_ms_nonnegative")
        ),
        sa.CheckConstraint(
            "cost_usd >= 0", name=op.f("ck_agent_runs_agent_runs_cost_usd_nonnegative")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_runs")),
    )
    op.create_index(
        "ix_agent_runs_owner_created_at", "agent_runs", ["owner_subject_hash", "created_at"]
    )
    op.create_index("ix_agent_runs_request_id", "agent_runs", ["request_id"])
    op.create_index(
        "ix_agent_runs_owner_agent_created_at",
        "agent_runs",
        ["owner_subject_hash", "agent_name", "created_at"],
    )


def downgrade() -> None:
    """Drop Agent memory and run-log tables."""
    op.drop_index("ix_agent_runs_owner_agent_created_at", table_name="agent_runs")
    op.drop_index("ix_agent_runs_request_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_owner_created_at", table_name="agent_runs")
    op.drop_table("agent_runs")
    op.drop_index("ix_agent_memory_owner_updated_at", table_name="agent_memory")
    op.drop_index("ix_agent_memory_owner_type", table_name="agent_memory")
    op.drop_table("agent_memory")
