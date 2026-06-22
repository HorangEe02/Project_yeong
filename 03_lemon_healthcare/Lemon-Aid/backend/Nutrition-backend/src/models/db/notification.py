"""Reminder preference ORM models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, String, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.models.db.mixins import TimestampMixin


class ReminderPreference(TimestampMixin, Base):
    """Persist one current-user health reminder preference.

    Push delivery tokens are intentionally stored outside this table. This table
    only represents user preferences such as category, local time, and enabled
    state.
    """

    __tablename__ = "reminder_preferences"
    __table_args__ = (
        CheckConstraint(
            (
                "category IN ("
                "'supplement_reminder', 'meal_check_in', "
                "'daily_coaching_prompt', 'safety_follow_up'"
                ")"
            ),
            name="reminder_category_allowed",
        ),
        CheckConstraint(
            "time_of_day ~ '^[0-2][0-9]:[0-5][0-9]$'",
            name="reminder_time_of_day_format",
        ),
        CheckConstraint("message <> ''", name="reminder_message_nonempty"),
        Index("ix_reminder_preferences_owner_enabled", "owner_subject", "enabled"),
        Index("ix_reminder_preferences_owner_category", "owner_subject", "category"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_subject: Mapped[str] = mapped_column(String(512), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    time_of_day: Mapped[str] = mapped_column(String(5), nullable=False)
    timezone: Mapped[str] = mapped_column(String(80), nullable=False, default="Asia/Seoul")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    message: Mapped[str] = mapped_column(String(240), nullable=False)
    preference_metadata: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB, nullable=False, default=dict
    )
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
