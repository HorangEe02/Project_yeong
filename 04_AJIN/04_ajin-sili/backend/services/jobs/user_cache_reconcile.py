"""야간 user_cache 정합성 검증 — IdP 와 캐시 mismatch 검출.

매일 01:30 KST (compliance crawler 02:00 시작 전).

동작:
  - IDP_PROVIDER=disabled 면 즉시 no-op return.
  - 모든 users 테이블 row 순회 → UserCache.is_fresh 평가.
  - stale row 에 대해 provider fetch 시도 → 비교 후 mismatch 카운트.
  - 결과 dict 반환 (Celery task return value 로 사용 + 향후 알림 hook).

본 phase 는 검출만 수행. 자동 invalidate 는 호출자가 결정.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def _idp_enabled() -> bool:
    pname = (os.environ.get("IDP_PROVIDER", "disabled") or "").strip().lower()
    return pname not in ("", "disabled", "none")


def run_reconcile() -> dict[str, int]:
    """user_cache 야간 정합성 점검 본체.

    Returns:
        {"total": N, "fresh": N, "stale": N, "mismatch": N, "skipped": N}
    """
    summary = {"total": 0, "fresh": 0, "stale": 0, "mismatch": 0, "skipped": 0}

    if not _idp_enabled():
        logger.info("user_cache_reconcile: IDP_PROVIDER 비활성 — no-op")
        return summary

    from core.auth.database import get_auth_db
    from core.auth.user_cache import UserCache

    cache = UserCache()
    conn = get_auth_db()
    try:
        rows = conn.execute(
            "SELECT employee_id, email, username, department, cached_at "
            "FROM users WHERE is_active = 1"
        ).fetchall()
    finally:
        conn.close()

    for row in rows:
        summary["total"] += 1
        emp_id = row["employee_id"]
        try:
            if cache.is_fresh(emp_id):
                summary["fresh"] += 1
                continue
            summary["stale"] += 1
            refreshed = cache.get_or_fetch(emp_id)
            if refreshed is None:
                summary["skipped"] += 1
                continue
            # mismatch 판정 — 주요 필드 비교
            for k in ("email", "username", "department"):
                if (row[k] or "") != (refreshed.get(k) or ""):
                    summary["mismatch"] += 1
                    logger.info(
                        "user_cache_reconcile: mismatch %s.%s: cache=%r idp=%r",
                        emp_id, k, row[k], refreshed.get(k),
                    )
                    break
        except Exception as e:
            logger.warning("user_cache_reconcile: %s 처리 실패 — %s", emp_id, e)
            summary["skipped"] += 1

    logger.info("user_cache_reconcile 완료: %s", summary)
    return summary
