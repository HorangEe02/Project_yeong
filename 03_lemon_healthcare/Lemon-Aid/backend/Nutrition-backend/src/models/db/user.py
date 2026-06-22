"""User ORM model."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Date, Numeric, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.models.db.mixins import TimestampMixin


class User(TimestampMixin, Base):
    """Persist the minimum profile data needed by Phase 1 algorithms.

    Attributes:
        id: Stable user identifier.
        sex: Biological sex value currently supported by KDRIs/sample algorithms.
        birth_date: Optional birth date for future age derivation.
        height_cm: User height in centimeters.
        base_weight_kg: Baseline body weight in kilograms.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("sex IN ('male', 'female')", name="sex_allowed"),
        CheckConstraint("height_cm > 0", name="height_cm_positive"),
        CheckConstraint("base_weight_kg > 0", name="base_weight_kg_positive"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    sex: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    height_cm: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    base_weight_kg: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
