"""검색 이력 관리 + 결과 정렬.

Sprint 1 P0 — Streamlit 세션 의존 제거, employees.db search_history 테이블에
영속화 (마이그레이션 0001).

스키마 (data/migrations/0001_canonical_directory.sql):
    id, user_id, query, intent, clicked_rank, action_invoked,
    latency_ms, result_count, ts

KPI K2 (Top-3 hit rate) / K3 (일평균 검색/직원) / K6 (검색→액션 전환율) 계산 근거.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import List, Optional

from core.directory.migrations import EMPLOYEES_DB

logger = logging.getLogger(__name__)

MAX_HISTORY = 20
ANONYMOUS_USER = "anonymous"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(EMPLOYEES_DB))
    conn.row_factory = sqlite3.Row
    return conn


# ──────────────────────────────────────────────
# 기록 / 조회 / 초기화
# ──────────────────────────────────────────────


def record_search(
    user_id: str,
    query: str,
    intent: Optional[str] = None,
    latency_ms: Optional[int] = None,
    result_count: Optional[int] = None,
) -> Optional[int]:
    """검색 이벤트 1건 영속화. row id 반환 (실패 시 None)."""
    query = (query or "").strip()
    if len(query) < 2:
        return None
    try:
        with _conn() as conn:
            cur = conn.execute(
                """INSERT INTO search_history
                   (user_id, query, intent, latency_ms, result_count)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id or ANONYMOUS_USER, query, intent, latency_ms, result_count),
            )
            conn.commit()
            return int(cur.lastrowid) if cur.lastrowid else None
    except sqlite3.OperationalError as e:
        logger.warning("search_history INSERT 실패: %s", e)
        return None


def record_click(history_id: int, clicked_rank: int) -> None:
    """사용자가 결과 N번째 항목 클릭 — K2 측정용."""
    try:
        with _conn() as conn:
            conn.execute(
                "UPDATE search_history SET clicked_rank = ? WHERE id = ?",
                (clicked_rank, history_id),
            )
            conn.commit()
    except sqlite3.OperationalError as e:
        logger.warning("record_click 실패: %s", e)


def record_action(history_id: int, action: str) -> None:
    """검색 → 액션 (메일/슬랙/캘린더/결재 등) — K6 측정용."""
    try:
        with _conn() as conn:
            conn.execute(
                "UPDATE search_history SET action_invoked = ? WHERE id = ?",
                (action, history_id),
            )
            conn.commit()
    except sqlite3.OperationalError as e:
        logger.warning("record_action 실패: %s", e)


def get_recent_queries(user_id: str, limit: int = MAX_HISTORY) -> List[str]:
    """사용자의 최근 distinct 검색어 N개 (최신 우선)."""
    try:
        with _conn() as conn:
            rows = conn.execute(
                """SELECT query FROM search_history
                   WHERE user_id = ?
                   ORDER BY ts DESC
                   LIMIT ?""",
                (user_id or ANONYMOUS_USER, max(1, min(limit, 200))),
            ).fetchall()
        # distinct 유지 + 최신순
        seen: set[str] = set()
        out: List[str] = []
        for r in rows:
            q = r["query"]
            if q in seen:
                continue
            seen.add(q)
            out.append(q)
            if len(out) >= limit:
                break
        return out
    except sqlite3.OperationalError as e:
        logger.warning("get_recent_queries 실패: %s", e)
        return []


def clear_history(user_id: str) -> int:
    """사용자 이력 전체 삭제. 삭제된 row 수 반환."""
    try:
        with _conn() as conn:
            cur = conn.execute(
                "DELETE FROM search_history WHERE user_id = ?",
                (user_id or ANONYMOUS_USER,),
            )
            conn.commit()
            return int(cur.rowcount or 0)
    except sqlite3.OperationalError as e:
        logger.warning("clear_history 실패: %s", e)
        return 0


# ─── backward-compat shims (Streamlit 사용처 잔재 — UI 점진 제거) ──

def add_search_query(query: str, user_id: str = ANONYMOUS_USER) -> Optional[int]:
    """legacy alias — Streamlit UI 가 호출하던 함수. record_search 로 위임."""
    return record_search(user_id=user_id, query=query)


def get_search_history(user_id: str = ANONYMOUS_USER) -> List[str]:
    """legacy alias — Streamlit UI 가 호출하던 함수."""
    return get_recent_queries(user_id=user_id)


def clear_search_history(user_id: str = ANONYMOUS_USER) -> int:
    """legacy alias."""
    return clear_history(user_id=user_id)


# ──────────────────────────────────────────────
# 검색 결과 정렬 (변경 없음 — UI 가 의존)
# ──────────────────────────────────────────────

SORT_OPTIONS: dict[str, Optional[tuple[str, bool]]] = {
    "관련도순": None,
    "이름순": ("name", False),
    "부서순": ("department", False),
    "직급순": ("position", True),
    "사업장순": ("plant", False),
}

POSITION_ORDER = {
    "전무": 1, "이사": 2, "상무": 3, "부장": 4, "차장": 5,
    "과장": 6, "대리": 7, "주임": 8, "사원": 9, "인턴": 10,
}


def sort_results(results: List[dict], sort_key: str = "관련도순") -> List[dict]:
    """검색 결과 정렬."""
    opt = SORT_OPTIONS.get(sort_key)
    if opt is None:
        return results
    field, is_custom = opt
    if is_custom and field == "position":
        return sorted(results, key=lambda x: POSITION_ORDER.get(x.get("position", ""), 99))
    return sorted(results, key=lambda x: x.get(field, "") or "")
