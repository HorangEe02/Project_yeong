"""``AccessAuditLog`` ORM 모델 — docs/16 §3.5.

민감 작업(동의 수락/철회, 영양제 등록, PHI 조회, 약물 안전 알림)은 모두 본 테이블에
append-only 로 기록된다. raw IP / User-Agent 는 저장하지 않고 SHA-256 hash 와
truncate 만 보관한다.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-04-database-models.md Step 5
    docs/16-implementation-settings-gap-review.md §3.5
    docs/10-compliance-checklist.md §5
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811 — SA convention
from sqlalchemy.orm import Mapped, mapped_column

from src.models.db.base import Base
from src.models.db.user import _utc_now


class AccessAuditLog(Base):
    """민감 작업의 감사 로그.

    기본 보관 365일 (docs/16 §3.3). 자동 파기 cron 은 트랙 후속.
    """

    __tablename__ = "access_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    """SHA-256(ip + 서버 비밀 salt). raw IP 절대 저장 금지."""
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        index=True,
    )
