"""교차 기능 내비게이션 브릿지 (v3.0)

Feature 간 이동을 지원한다.
- C(AI 업무 도우미) → A(인원검색): 담당자 검색
- A(인원검색) → B(문서작성): 이메일 작성
- C(AI 업무 도우미) → B(문서작성): 템플릿 다운로드
- C(AI 업무 도우미) → F(설비): 에러코드 검색

app.py의 active_module 메커니즘을 활용한다.
"""

import streamlit as st
from typing import Any

# ── active_module 키 상수 ──
_MOD_DASHBOARD = "dashboard"
_MOD_SEARCH = "page_search"
_MOD_DRAFT = "page_draft"
_MOD_ONBOARDING = "page_onboarding"
_MOD_COMPLIANCE = "page_compliance"
_MOD_ADMIN = "page_admin"
_MOD_EQUIPMENT = "page_equipment"


def navigate_to(module_key: str, **params: Any) -> None:
    """지정 모듈로 이동하면서 파라미터를 전달한다.

    Args:
        module_key: app.py의 active_module 키
                    (예: "page_search", "page_draft")
        **params: 도착 페이지에서 get_bridge_params()로 회수할 값
    """
    st.session_state["active_module"] = module_key
    if params:
        st.session_state["_bridge_params"] = params
    st.rerun()


def get_bridge_params() -> dict:
    """도착 페이지에서 브릿지 파라미터를 회수한다.

    한 번 읽으면 자동 삭제되어 중복 사용을 방지한다.
    """
    return st.session_state.pop("_bridge_params", {})


# ── 시나리오별 헬퍼 ──

def go_to_employee_search(query: str = "") -> None:
    """인원 검색 페이지로 이동"""
    navigate_to(_MOD_SEARCH, search_query=query)


def go_to_email_compose(
    recipient: str = "",
    subject: str = "",
    doc_type: str = "사내 이메일",
) -> None:
    """문서 작성 페이지로 이동 (이메일 작성 모드)"""
    navigate_to(
        _MOD_DRAFT,
        prefill_doc_type=doc_type,
        prefill_recipient=recipient,
        prefill_subject=subject,
    )


def go_to_template_download(doc_type: str = "") -> None:
    """문서 작성 페이지로 이동 (템플릿 모드)"""
    navigate_to(_MOD_DRAFT, prefill_doc_type=doc_type, mode="template")


def go_to_compliance(scenario: str = "") -> None:
    """규정 준수 페이지로 이동"""
    navigate_to(_MOD_COMPLIANCE, scenario=scenario)


def go_to_equipment(tab: str = "", query: str = "") -> None:
    """설비/공정 페이지로 이동"""
    navigate_to(_MOD_EQUIPMENT, active_tab=tab, equipment_query=query)
