"""감사 이벤트 emit 단일 진입점.

호출자(auth.py 등)는 한 함수만 호출하면 세 채널에 동시 기록:
  1. Postgres login_history — Firebase audit shadow 대체 표준 경로.
  2. Firestore audit_logs (legacy fallback) — 실패해도 호출자 영향 없음.
  3. stdout JSON 로그 (H8) — Cloud Logging 자동 수집 → BigQuery sink 대상.

설계 의도:
  - SQLite login_history 핫패스는 auth.py 가 그대로 유지 (점진 마이그레이션).
  - 본 모듈은 Firestore/Cloud Logging "추가" 채널만 담당.
  - 어느 채널이 실패해도 다른 채널은 정상 동작 — 단일 실패점 없음.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


def emit_login_event(
    *,
    user_id: int,
    employee_id: str,
    success: bool,
    ip_address: str = "",
    user_agent: str = "",
    department: str = "",
    role_level: int = 0,
    extra: Optional[dict] = None,
) -> None:
    """로그인 이벤트 1건을 Postgres + legacy Firestore + Cloud Logging에 emit.

    호출 위치: backend/routers/auth.py 로그인 핸들러 (실패/성공 분기).
    """
    # Channel 1 — Postgres audit repository (Firebase audit shadow 대체)
    try:
        from core.auth.postgres_audit import write_login_event
        write_login_event(
            user_id=user_id,
            employee_id=employee_id,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
            department=department,
            role_level=role_level,
        )
    except Exception as e:
        logger.warning("[audit] Postgres emit 실패: %s", e)

    # Channel 2 — Firestore audit_logs legacy fallback (기본 비활성)
    try:
        from core.auth.firestore_audit import write_login_event
        write_login_event(
            user_id=user_id,
            employee_id=employee_id,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
            department=department,
            role_level=role_level,
        )
    except Exception as e:
        logger.warning("[audit] Firestore emit 실패: %s", e)

    # Channel 3 — stdout JSON (H8: Cloud Logging → BigQuery)
    try:
        record = {
            "severity": "NOTICE" if success else "WARNING",
            "event": "login",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "employee_id": employee_id,
            "success": success,
            "ip": ip_address,
            "user_agent": user_agent,
            "department": department,
            "role_level": role_level,
        }
        if extra:
            from core.auth.audit_redaction import redact_audit_detail

            record.update(
                {
                    key: redact_audit_detail(value) if isinstance(value, str) else value
                    for key, value in extra.items()
                }
            )
        print(json.dumps(record, ensure_ascii=False), file=sys.stdout, flush=True)
    except Exception as e:
        logger.warning("[audit] stdout emit 실패: %s", e)
