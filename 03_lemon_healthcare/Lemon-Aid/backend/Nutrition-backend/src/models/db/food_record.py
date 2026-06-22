"""Current-user food record ORM models."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, Date, Index, Numeric, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import conv

from src.db.base import Base
from src.models.db.mixins import TimestampMixin


class FoodRecord(TimestampMixin, Base):
    """Persist one user-confirmed food record for app-context chatbot grounding."""

    __tablename__ = "food_records"
    __table_args__ = (
        CheckConstraint(
            "meal_type IN ('breakfast', 'lunch', 'dinner', 'snack', 'extra')",
            name=conv("ck_food_records_meal_type_allowed"),
        ),
        CheckConstraint(
            "source IN ('manual', 'food_user_input', 'food_ocr_confirmed')",
            name=conv("ck_food_records_source_allowed"),
        ),
        CheckConstraint(
            "match_confidence IS NULL OR (match_confidence >= 0 AND match_confidence <= 1)",
            name=conv("ck_food_records_match_confidence_range"),
        ),
        Index("ix_food_records_owner_date", "owner_subject_hash", "recorded_date"),
        Index(
            "ix_food_records_owner_meal_date", "owner_subject_hash", "meal_type", "recorded_date"
        ),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_subject_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    recorded_date: Mapped[date] = mapped_column(Date, nullable=False)
    meal_type: Mapped[str] = mapped_column(String(24), nullable=False)
    display_items: Mapped[list[str]] = mapped_column(postgresql.JSONB, nullable=False, default=list)
    amount_text: Mapped[str | None] = mapped_column(String(120), nullable=True)
    estimated_tags: Mapped[list[str]] = mapped_column(
        postgresql.JSONB, nullable=False, default=list
    )
    rough_nutrient_axes: Mapped[list[str]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=list,
    )
    user_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="manual")
    food_db_match_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    match_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    nutrient_estimates: Mapped[dict[str, Any] | None] = mapped_column(
        postgresql.JSONB,
        nullable=True,
    )
