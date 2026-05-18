"""``ConsentRecord`` ORM 모델 — docs/17 §3 동의 매트릭스.

호출처(SupplementService 등)는 user_id + consent_type 조회로 ``revoked_at IS NULL``
인 row가 있는지 확인해 진입 게이트로 사용한다.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-04-database-models.md Step 4
    docs/17-image-collection-consent-plan.md §3
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Final, Literal

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811 — SA convention
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.db.base import Base
from src.models.db.user import _utc_now

if TYPE_CHECKING:
    from src.models.db.user import User

ConsentType = Literal[
    "service_terms",
    "general_profile",
    "chronic_disease",
    "medications",
    "biometric",
    "image_history",
    "image_training",
    "image_partner",
]

ALLOWED_CONSENT_TYPES: Final[frozenset[str]] = frozenset(
    {
        "service_terms",
        "general_profile",
        "chronic_disease",
        "medications",
        "biometric",
        "image_history",
        "image_training",
        "image_partner",
    }
)
"""런타임 검증용 — ``Literal`` 은 mypy 정적 검사만 보장한다."""


class ConsentRecord(Base):
    """단일 사용자 × 단일 동의 유형의 1 row.

    동일 ``consent_type`` 에 대해 revoke 후 재동의 시 새로운 row를 ``INSERT``.
    이력 보존을 위해 update 대신 append-only.
    """

    __tablename__ = "consent_records"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    consent_type: Mapped[str] = mapped_column(String(32), nullable=False)
    purpose: Mapped[str] = mapped_column(String(255), nullable=False)
    data_categories: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    retention_period_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    user: Mapped[User] = relationship(back_populates="consents")
