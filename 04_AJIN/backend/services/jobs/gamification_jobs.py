"""v4.7 C-4 — 게이미피케이션 Celery beat 작업.

- t_gamification_daily_eval (매일 06:00 KST)
    - user_daily_activity 에 등록된 사용자 모두 evaluate_badges 호출 (streak/누적 배지)
- t_gamification_weekly_leaderboard (매주 월요일 06:00 KST)
    - 활성 부서별 compute_dept_leaderboard 호출 + snapshot 저장 (`week_YYYY-WW`)
- t_gamification_monthly_pioneer (매월 말일 23:00 KST 근접)
    - 부서별 월간 점수 1위 → `department_pioneer` 배지 부여
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


def run_daily_eval() -> dict[str, Any]:
    """모든 활성 사용자에 대해 evaluate_badges 일괄 호출."""
    from features.onboarding import gamification_db as gdb
    from features.onboarding.gamification import evaluate_badges

    gdb.init_gamification_db()
    with gdb.get_conn() as conn:
        rows = conn.execute(
            "SELECT user_id, user_department FROM user_daily_activity GROUP BY user_id, user_department"
        ).fetchall()
    total_newly = 0
    processed = 0
    for r in rows:
        uid = r["user_id"]
        dept = r["user_department"] or ""
        try:
            newly = evaluate_badges(uid, user_department=dept, event_hint="daily")
            total_newly += len(newly)
            processed += 1
        except Exception:  # noqa: BLE001
            logger.exception("daily_eval user=%s failed", uid)
    return {"processed": processed, "newly_earned": total_newly}


def run_weekly_leaderboard() -> dict[str, Any]:
    """활성 부서별 주간 리더보드 스냅샷."""
    from features.onboarding import gamification_db as gdb
    from features.onboarding.gamification import compute_dept_leaderboard

    gdb.init_gamification_db()
    with gdb.get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT user_department FROM user_daily_activity WHERE user_department <> ''"
        ).fetchall()
    period = f"week_{datetime.now().strftime('%Y-%U')}"
    saved = 0
    for r in rows:
        dept = r["user_department"]
        result = compute_dept_leaderboard(dept, period=period)
        if result.get("visible"):
            gdb.save_leaderboard_snapshot(dept, period, result["top_users"])
            saved += 1
    return {"period": period, "snapshots_saved": saved}


def run_monthly_pioneer() -> dict[str, Any]:
    """월간 부서 1위에게 department_pioneer 배지 부여."""
    from features.onboarding import gamification_db as gdb
    from features.onboarding.gamification import compute_dept_leaderboard

    gdb.init_gamification_db()
    with gdb.get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT user_department FROM user_daily_activity WHERE user_department <> ''"
        ).fetchall()
    period = f"month_{datetime.now().strftime('%Y-%m')}"
    awarded = 0
    for r in rows:
        dept = r["user_department"]
        lb = compute_dept_leaderboard(dept, period=period)
        if not lb.get("visible") or not lb.get("top_users"):
            continue
        top_user = lb["top_users"][0]["user_id"]
        if gdb.persist_badge(top_user, "department_pioneer", metadata={"dept": dept, "period": period}):
            awarded += 1
    return {"period": period, "awards": awarded}
