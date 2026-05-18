"""``Supplement`` ORM 모델 — 사용자 별 등록 영양제 한 건.

이미지 원본은 저장하지 않고 ``image_hash`` (SHA-256 앞 12자) 만 보존한다
(docs/14 §3 원본 이미지 기본 폐기 정책).

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-04-database-models.md Step 6
    docs/dev-guides/09-supplement-registration-api.md §2
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811 — SA convention
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.db.base import Base
from src.models.db.user import _utc_now

if TYPE_CHECKING:
    from src.models.db.user import User


class Supplement(Base):
    """등록된 영양제 한 건.

    ``ingredients`` 는 ``NutrientIntake.model_dump()`` 직렬화 결과 리스트.
    ``ocr_engine`` / ``llm_engine`` 은 트레이스용 (감사 로그와 별개).
    """

    __tablename__ = "supplements"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ingredients: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    ocr_engine: Mapped[str] = mapped_column(String(50), nullable=False)
    llm_engine: Mapped[str] = mapped_column(String(50), nullable=False)
    image_hash: Mapped[str | None] = mapped_column(String(12), nullable=True)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        index=True,
    )

    user: Mapped[User] = relationship(back_populates="supplements")
