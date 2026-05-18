"""``User`` + ``UserProfile`` ORM 모델 (1:1).

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-04-database-models.md Step 3
    docs/16-implementation-settings-gap-review.md §3.5
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811 — SA convention
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.db.base import Base

if TYPE_CHECKING:
    from src.models.db.consent import ConsentRecord
    from src.models.db.supplement import Supplement


def _utc_now() -> datetime:
    """UTC-aware 현재 시각 — 모든 ``DateTime(timezone=True)`` 컬럼 default."""
    return datetime.now(UTC)


class User(Base):
    """사용자 계정 — 인증·동의·영양제 기록의 루트.

    ``deleted_at`` 이 NULL 이 아니면 soft-deleted 상태로 간주하고 모든 API가 401 처리.
    Hard delete + 백업 폐기는 회원탈퇴 90일 후 cron 으로 (트랙 후속).
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    profile: Mapped[UserProfile | None] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    consents: Mapped[list[ConsentRecord]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    supplements: Mapped[list[Supplement]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class UserProfile(Base):
    """건강 분석에 필요한 사용자 인구학·임상 정보 (1:1 with ``User``).

    민감 컬럼: ``chronic_diseases``, ``medications`` — docs/10 §5.1.
    트랙 B는 JSON 평문 저장. 정식 출시 전 AES-256 컬럼 암호화 필요.
    """

    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    sex: Mapped[str] = mapped_column(String(8), nullable=False)
    height_cm: Mapped[float] = mapped_column(Float, nullable=False)
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    is_pregnant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_lactating: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_smoker: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    chronic_diseases: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    medications: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )

    user: Mapped[User] = relationship(back_populates="profile")
