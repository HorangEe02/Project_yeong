"""Current-user medication profile ORM models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, String, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import conv

from src.db.base import Base
from src.models.db.mixins import TimestampMixin


class UserMedication(TimestampMixin, Base):
    """Persist one user-confirmed medication name for chatbot context.

    Dosage, timing, OCR text, notes, and raw user questions are intentionally
    outside this v1 table. The chatbot only needs structured confirmation
    context to avoid pretending it knows the user's medication list.
    """

    __tablename__ = "user_medications"
    __table_args__ = (
        CheckConstraint(
            "display_name <> ''",
            name=conv("ck_user_medications_display_name_nonempty"),
        ),
        CheckConstraint(
            "normalized_name IS NULL OR normalized_name <> ''",
            name=conv("ck_user_medications_normalized_name_nonempty"),
        ),
        CheckConstraint(
            "medication_class IS NULL OR medication_class <> ''",
            name=conv("ck_user_medications_medication_class_nonempty"),
        ),
        CheckConstraint(
            "confirmation_status IN ('user_confirmed')",
            name=conv("ck_user_medications_confirmation_status_allowed"),
        ),
        Index("ix_user_medications_owner_active", "owner_subject_hash", "is_active"),
        Index("ix_user_medications_owner_normalized", "owner_subject_hash", "normalized_name"),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_subject_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    medication_class: Mapped[str | None] = mapped_column(String(80), nullable=True)
    condition_tags: Mapped[list[str]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        default=list,
    )
    confirmation_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="user_confirmed",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
