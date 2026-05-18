"""AuditService — ``AccessAuditLog`` 기록 헬퍼.

raw IP / User-Agent 는 절대 저장하지 않는다. IP 는 SHA-256(ip + 서버 salt) 해시로,
User-Agent 는 255자 truncate.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-05-api-integration.md Step 4
    docs/16-implementation-settings-gap-review.md §3.5
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.models.db.audit import AccessAuditLog


def hash_ip(ip: str, salt: str | None = None) -> str:
    """``SHA-256(ip + salt)`` 16진수 64자.

    Args:
        ip: 클라이언트 IP 문자열.
        salt: 서버 비밀 salt. ``None`` 이면 ``Settings.ip_hash_salt``.

    Returns:
        64자 hex SHA-256 hash.
    """
    if salt is None:
        salt = get_settings().ip_hash_salt.get_secret_value()
    return hashlib.sha256(f"{ip}{salt}".encode()).hexdigest()


class AuditService:
    """``AccessAuditLog`` append-only 기록."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def log(
        self,
        *,
        actor_user_id: uuid.UUID | None,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        success: bool = True,
        error_code: str | None = None,
    ) -> AccessAuditLog:
        """감사 로그 1행을 ``session.add`` 한다. ``commit`` 은 호출처가 담당.

        Args:
            actor_user_id: 작업 주체 user id (None = 시스템 / 인증 전).
            action: 도메인-액션 키 (예: ``supplement.register.success``).
            resource_type: 리소스 종류 (``supplement``, ``consent``, ``user``).
            resource_id: 리소스 식별자 문자열 (없으면 None).
            ip_address: 클라이언트 IP 평문. 본 메서드에서 해시화.
            user_agent: HTTP User-Agent. 255자 truncate.
            success: 성공 여부.
            error_code: 실패 시 짧은 코드 문자열.

        Returns:
            세션에 add 된 ``AccessAuditLog`` 인스턴스.
        """
        entry = AccessAuditLog(
            id=uuid.uuid4(),
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address_hash=hash_ip(ip_address) if ip_address else None,
            user_agent=(user_agent or "")[:255] or None,
            success=success,
            error_code=error_code,
            occurred_at=datetime.now(UTC),
        )
        self._session.add(entry)
        return entry
