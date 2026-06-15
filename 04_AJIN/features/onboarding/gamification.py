"""v4.7 C-4 — 배지 정의 + 평가 + 리더보드 산식.

배지 10종 — 즉시 평가 (퀴즈/피드백 트리거) + 일괄 평가 (매일 06:00 Celery).
리더보드 — weekly_score 산식, 부서 인원 < 3 면 공개 안 함.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Optional

from features.onboarding import gamification_db as gdb

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BadgeDef:
    badge_id: str
    eval_fn: Callable[[str], bool]
    # 분류 — UI 그룹화용
    category: str  # 'quiz' | 'sop' | 'streak' | 'feedback' | 'glossary' | 'leaderboard'
    # 등급 — UI 색상용
    tier: str = "bronze"  # 'bronze' | 'silver' | 'gold' | 'platinum'

    def snapshot(self, user_id: str) -> dict:
        """획득 시 함께 저장할 메타데이터."""
        return {"category": self.category, "tier": self.tier}


# ── 평가 함수 헬퍼 (테스트 가능하도록 분리) ──


def _has_any_quiz(user_id: str) -> bool:
    return gdb.count_total_quizzes(user_id) >= 1


def _quiz_master(user_id: str, *, difficulty: str, threshold: int) -> bool:
    return gdb.count_correct_quizzes(user_id, difficulty=difficulty) >= threshold


def _sop_explorer_n(user_id: str, *, n: int) -> bool:
    """전 단계 완료 SOP 개수 ≥ n."""
    # 동적 import 로 sop_guide 의존성 lazy
    from features.onboarding.sop_guide import get_all_sops

    sops = get_all_sops()
    totals = {s.sop_id: len(s.steps) for s in sops if s.steps}
    return gdb.count_completed_sops(user_id, totals) >= n


def _sop_completer_dept(user_id: str, user_department: str) -> bool:
    """부서 관련 SOP 100% 완료."""
    from features.onboarding.sop_guide import get_all_sops

    sops = [s for s in get_all_sops() if s.department == user_department and s.steps]
    if not sops:
        return False
    totals = {s.sop_id: len(s.steps) for s in sops}
    return gdb.count_completed_sops(user_id, totals) == len(sops)


def _streak_n(user_id: str, *, days: int) -> bool:
    return gdb.count_streak_days(user_id, days_window=days + 5) >= days


def _feedback_n(user_id: str, *, n: int) -> bool:
    return gdb.get_positive_feedback_count(user_id) >= n


def _glossary_n(user_id: str, *, n: int) -> bool:
    return gdb.get_glossary_lookup_count(user_id) >= n


def _dept_pioneer(user_id: str) -> bool:
    """월간 부서 종합점수 1위 — Celery monthly task 가 별도로 부여."""
    # 이 평가 함수는 즉시 평가에서는 항상 False (monthly task 에서만 INSERT)
    return False


# ── 10 배지 정의 ──

BADGE_DEFS: dict[str, BadgeDef] = {
    "quiz_starter": BadgeDef(
        "quiz_starter", _has_any_quiz, category="quiz", tier="bronze"
    ),
    "quiz_master_basic": BadgeDef(
        "quiz_master_basic",
        lambda uid: _quiz_master(uid, difficulty="basic", threshold=10),
        category="quiz",
        tier="silver",
    ),
    "quiz_master_advanced": BadgeDef(
        "quiz_master_advanced",
        lambda uid: _quiz_master(uid, difficulty="advanced", threshold=5),
        category="quiz",
        tier="gold",
    ),
    "sop_explorer": BadgeDef(
        "sop_explorer",
        lambda uid: _sop_explorer_n(uid, n=3),
        category="sop",
        tier="silver",
    ),
    "sop_completer": BadgeDef(
        "sop_completer",
        # user_department 가 필요한 평가는 evaluate_badges 에서 context 주입
        lambda uid: False,
        category="sop",
        tier="gold",
    ),
    "streak_7": BadgeDef(
        "streak_7",
        lambda uid: _streak_n(uid, days=7),
        category="streak",
        tier="silver",
    ),
    "streak_30": BadgeDef(
        "streak_30",
        lambda uid: _streak_n(uid, days=30),
        category="streak",
        tier="gold",
    ),
    "helpful_voice": BadgeDef(
        "helpful_voice",
        lambda uid: _feedback_n(uid, n=50),
        category="feedback",
        tier="silver",
    ),
    "glossary_native": BadgeDef(
        "glossary_native",
        lambda uid: _glossary_n(uid, n=100),
        category="glossary",
        tier="silver",
    ),
    "department_pioneer": BadgeDef(
        "department_pioneer",
        _dept_pioneer,
        category="leaderboard",
        tier="platinum",
    ),
}


def evaluate_badges(
    user_id: str,
    *,
    user_department: str = "",
    event_hint: Optional[str] = None,
) -> list[str]:
    """user 의 모든 배지 평가. 신규 획득된 배지 ID 리스트 반환.

    event_hint 는 향후 부분 평가 최적화용 (현재는 무시 — 전체 10개 평가).
    """
    earned_now = {b["badge_id"] for b in gdb.get_earned_badges(user_id)}
    newly: list[str] = []
    for badge_id, bdef in BADGE_DEFS.items():
        if badge_id in earned_now:
            continue
        # sop_completer 는 부서 컨텍스트 필요
        try:
            if badge_id == "sop_completer":
                ok = bool(user_department) and _sop_completer_dept(user_id, user_department)
            else:
                ok = bdef.eval_fn(user_id)
        except Exception:  # noqa: BLE001
            logger.exception("badge eval failed: %s", badge_id)
            continue
        if ok:
            if gdb.persist_badge(user_id, badge_id, metadata=bdef.snapshot(user_id)):
                newly.append(badge_id)
    return newly


# ── 리더보드 산식 ──


WEEKLY_WEIGHTS = {
    "quiz_correct": 10,
    "sop_steps_completed": 5,
    "positive_feedback": 3,
    "chat_count": 1,
}


def compute_user_weekly_score(user_id: str, db_path=None) -> int:
    """최근 7일 활동의 weighted score."""
    from features.onboarding.gamification_db import DB_PATH, get_conn

    db_path = db_path or DB_PATH
    with get_conn(db_path) as conn:
        row = conn.execute(
            """SELECT
                COALESCE(SUM(quiz_correct),0) AS qc,
                COALESCE(SUM(sop_steps_completed),0) AS sc,
                COALESCE(SUM(positive_feedback),0) AS pf,
                COALESCE(SUM(chat_count),0) AS cc
              FROM user_daily_activity
              WHERE user_id=? AND date >= date('now','localtime', '-7 days')""",
            (user_id,),
        ).fetchone()
    if not row:
        return 0
    return (
        row["qc"] * WEEKLY_WEIGHTS["quiz_correct"]
        + row["sc"] * WEEKLY_WEIGHTS["sop_steps_completed"]
        + row["pf"] * WEEKLY_WEIGHTS["positive_feedback"]
        + row["cc"] * WEEKLY_WEIGHTS["chat_count"]
    )


def compute_dept_leaderboard(dept: str, period: str = "week") -> dict:
    """부서 리더보드 산출.

    부서 활성 인원 < 3 명이면 `visible=False` + 빈 리스트.
    응답:
      {
        "dept": ...,
        "period": ...,
        "visible": bool,
        "top_users": [{"user_id":..., "score":...}, ...],   # 상위 N (raw score 비공개 — 백분위만 권장)
        "total_active": int,
      }
    """
    users = gdb.get_dept_active_users(dept, since_days=7)
    if len(users) < 3:
        return {"dept": dept, "period": period, "visible": False, "top_users": [], "total_active": len(users)}

    scored = [(uid, compute_user_weekly_score(uid)) for uid in users]
    scored.sort(key=lambda x: x[1], reverse=True)
    top = [{"user_id": uid, "score": score} for uid, score in scored[:5]]
    return {
        "dept": dept,
        "period": period,
        "visible": True,
        "top_users": top,
        "total_active": len(users),
    }


def user_rank_in_dept(user_id: str, dept: str) -> Optional[dict]:
    """본인의 부서 내 순위 + 백분위. 부서 < 3명 이면 None."""
    users = gdb.get_dept_active_users(dept, since_days=7)
    if len(users) < 3 or user_id not in users:
        return None
    scored = sorted(
        ((uid, compute_user_weekly_score(uid)) for uid in users), key=lambda x: x[1], reverse=True
    )
    rank = next((i + 1 for i, (uid, _s) in enumerate(scored) if uid == user_id), None)
    if rank is None:
        return None
    total = len(scored)
    percentile = round(100.0 * rank / total)
    return {"rank": rank, "total": total, "percentile": percentile}
