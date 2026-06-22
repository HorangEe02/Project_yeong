"""Analysis result ORM model."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Index, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.models.db.mixins import TimestampMixin


class AnalysisResult(TimestampMixin, Base):
    """Persist server-computed analysis outputs for an authenticated owner.

    Attributes:
        id: Stable result identifier.
        owner_subject: Issuer-qualified authenticated subject.
        analysis_type: Type of stored analysis.
        algorithm_version: Version of the server algorithm used for the result.
        kdris_source_manifest_version: KDRIs source manifest schema version for nutrition results.
        input_snapshot: Server-validated input snapshot.
        result_snapshot: Server-computed output snapshot.
        created_at: Server-side record creation timestamp.
        updated_at: Server-side record update timestamp.
    """

    __tablename__ = "analysis_results"
    __table_args__ = (
        CheckConstraint(
            "analysis_type IN ('activity_score', 'weight_prediction', "
            "'nutrition_analysis', 'daily_health_score')",
            name="analysis_type_allowed",
        ),
        Index("ix_analysis_results_owner_created_at", "owner_subject", "created_at"),
        Index(
            "ix_analysis_results_owner_type_created_at",
            "owner_subject",
            "analysis_type",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_subject: Mapped[str] = mapped_column(String(512), nullable=False)
    analysis_type: Mapped[str] = mapped_column(String(32), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False)
    kdris_source_manifest_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(postgresql.JSONB, nullable=False)
    result_snapshot: Mapped[dict[str, Any]] = mapped_column(postgresql.JSONB, nullable=False)
