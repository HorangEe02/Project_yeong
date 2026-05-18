"""ConsentService — 동의 게이트 + 수락 / 철회.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-05-api-integration.md Step 4
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db.consent import ALLOWED_CONSENT_TYPES, ConsentRecord


class ConsentService:
    """동의 매트릭스 검증 / 수락 / 철회."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def require(self, user_id: uuid.UUID, required: Iterable[str]) -> None:
        """필수 consent 가 모두 active(revoked_at IS NULL) 인지 검증.

        Args:
            user_id: 사용자 UUID.
            required: 필수 ``consent_type`` 집합.

        Raises:
            HTTPException 403: 누락된 동의가 1건 이상.
        """
        required_set = set(required)
        result = await self._session.execute(
            select(ConsentRecord.consent_type).where(
                ConsentRecord.user_id == user_id,
                ConsentRecord.revoked_at.is_(None),
            )
        )
        active = {row[0] for row in result.all()}
        missing = required_set - active
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "consent_required",
                    "missing": sorted(missing),
                },
            )

    async def accept(
        self,
        user_id: uuid.UUID,
        consent_type: str,
        *,
        purpose: str = "service usage",
        policy_version: str = "v1.0",
    ) -> ConsentRecord:
        """단일 ``consent_type`` 수락 → ``ConsentRecord`` INSERT.

        Raises:
            HTTPException 400: 알 수 없는 consent_type.
        """
        if consent_type not in ALLOWED_CONSENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown consent_type: {consent_type}",
            )
        record = ConsentRecord(
            id=uuid.uuid4(),
            user_id=user_id,
            consent_type=consent_type,
            purpose=purpose,
            data_categories=[],
            retention_period_days=0,
            policy_version=policy_version,
            accepted_at=datetime.now(UTC),
        )
        self._session.add(record)
        return record

    async def revoke(self, user_id: uuid.UUID, consent_type: str) -> int:
        """``consent_type`` 의 active row 들을 모두 철회.

        Returns:
            철회된 row 수.

        Raises:
            HTTPException 404: 철회할 active 동의 없음.
        """
        result = await self._session.execute(
            select(ConsentRecord).where(
                ConsentRecord.user_id == user_id,
                ConsentRecord.consent_type == consent_type,
                ConsentRecord.revoked_at.is_(None),
            )
        )
        records = list(result.scalars().all())
        if not records:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active consent to revoke",
            )
        now = datetime.now(UTC)
        for r in records:
            r.revoked_at = now
        return len(records)
