"""
검색 이력 관리 + 결과 정렬
- 세션 기반 최근 검색어 저장 (최대 20건)
- 5종 정렬 옵션
"""

import streamlit as st
from typing import List


MAX_HISTORY = 20
SESSION_KEY = "employee_search_history"


def add_search_query(query: str):
    """검색어를 이력에 추가"""
    if not query or len(query.strip()) < 2:
        return
    query = query.strip()
    history = st.session_state.get(SESSION_KEY, [])
    history = [h for h in history if h != query]
    history.insert(0, query)
    st.session_state[SESSION_KEY] = history[:MAX_HISTORY]


def get_search_history() -> List[str]:
    """최근 검색 이력"""
    return st.session_state.get(SESSION_KEY, [])


def clear_search_history():
    """이력 초기화"""
    st.session_state[SESSION_KEY] = []


# ──────────────────────────────────────────────
# 검색 결과 정렬
# ──────────────────────────────────────────────

SORT_OPTIONS = {
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
    """검색 결과 정렬"""
    if sort_key not in SORT_OPTIONS or SORT_OPTIONS[sort_key] is None:
        return results

    field, is_custom = SORT_OPTIONS[sort_key]

    if is_custom and field == "position":
        return sorted(results, key=lambda x: POSITION_ORDER.get(x.get("position", ""), 99))
    else:
        return sorted(results, key=lambda x: x.get(field, "") or "")
