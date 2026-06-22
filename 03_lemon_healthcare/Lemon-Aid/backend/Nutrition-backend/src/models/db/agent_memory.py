"""AI Agent memory and run-log ORM models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Index, Numeric, String, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.models.db.mixins import TimestampMixin


class AgentMemory(TimestampMixin, Base):
    """Persist privacy-minimized long-term summaries for one owner.

    Raw images, raw OCR text, full prompts, and raw LLM responses must never be
    stored in this table. `summary_json` is intentionally a compact aggregate
    used to rehydrate future coaching context.
    """

    __tablename__ = "agent_memory"
    __table_args__ = (
        UniqueConstraint(
            "owner_subject_hash",
            "memory_type",
            name="uq_agent_memory_owner_type",
        ),
        CheckConstraint("memory_type <> ''", name="agent_memory_memory_type_nonempty"),
        CheckConstraint(
            "algorithm_version <> ''",
            name="agent_memory_algorithm_version_nonempty",
        ),
        Index("ix_agent_memory_owner_type", "owner_subject_hash", "memory_type"),
        Index("ix_agent_memory_owner_updated_at", "owner_subject_hash", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_subject_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    memory_type: Mapped[str] = mapped_column(String(64), nullable=False)
    summary_json: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB, nullable=False, default=dict
    )
    source_counters: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB, nullable=False, default=dict
    )
    last_source_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False)


class AgentRun(TimestampMixin, Base):
    """Persist sanitized AI Agent execution metadata."""

    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('completed', 'failed')",
            name="agent_runs_status_allowed",
        ),
        CheckConstraint(
            "approval_status IN ('confirmed', 'requires_confirmation')",
            name="agent_runs_approval_status_allowed",
        ),
        CheckConstraint("latency_ms >= 0", name="agent_runs_latency_ms_nonnegative"),
        CheckConstraint("cost_usd >= 0", name="agent_runs_cost_usd_nonnegative"),
        Index("ix_agent_runs_owner_created_at", "owner_subject_hash", "created_at"),
        Index("ix_agent_runs_request_id", "request_id"),
        Index(
            "ix_agent_runs_owner_agent_created_at", "owner_subject_hash", "agent_name", "created_at"
        ),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    request_id: Mapped[str] = mapped_column(String(80), nullable=False)
    owner_subject_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    agent_name: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    approval_status: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    latency_ms: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    used_tools: Mapped[list[str]] = mapped_column(postgresql.JSONB, nullable=False, default=list)
