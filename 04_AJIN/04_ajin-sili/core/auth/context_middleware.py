"""
컨텍스트 주입 미들웨어 — 각 기능 페이지 렌더 전 자동 실행

역할:
1. UserContext 생성 (session_state에서)
2. 부서 설정 조회 (DEPARTMENT_REGISTRY)
3. 가시성 레벨 판단용 헬퍼
4. 프롬프트 컨텍스트 문자열 생성
"""
from typing import Optional, Tuple

from core.auth.user_context import UserContext, get_user_context_from_session
from core.auth.visibility import VisibilityLevel, determine_visibility
from core.department_config import get_dept_config


def get_page_context() -> Tuple[Optional[UserContext], dict]:
    """
    페이지 렌더 시작점에서 호출. 사용자 컨텍스트 + 부서 설정을 반환합니다.

    Returns:
        (user_ctx, dept_config)
        - user_ctx: UserContext 또는 None (비로그인)
        - dept_config: 부서별 설정 딕셔너리
    """
    user_ctx = get_user_context_from_session()
    dept = user_ctx.department if user_ctx else ""
    dept_config = get_dept_config(dept)
    return user_ctx, dept_config


def can_view_detail(
    user_ctx: Optional[UserContext],
    target_department: str,
) -> bool:
    """대상 부서의 상세 정보를 볼 수 있는지 간단 판단"""
    vis = determine_visibility(user_ctx, target_department)
    return vis == VisibilityLevel.FULL


def build_llm_user_context(
    user_ctx: Optional[UserContext],
    dept_config: dict,
) -> str:
    """LLM 프롬프트에 주입할 통합 사용자 컨텍스트 문자열"""
    if not user_ctx:
        return ""

    parts = [user_ctx.to_prompt_context()]

    # 부서 카테고리 힌트
    category = dept_config.get("category", "")
    category_labels = {
        "management": "경영/관리",
        "production": "생산/제조",
        "engineering": "기술/연구",
        "quality": "품질",
        "sales": "영업/해외",
    }
    if category in category_labels:
        parts.append(f"[부서 성격] {category_labels[category]} 분야")

    # 용어 포커스 힌트
    focus = dept_config.get("glossary_focus", [])
    if focus:
        parts.append(f"[관심 분야] {', '.join(focus[:5])}")

    return "\n".join(parts)


def get_sorted_doc_types(dept_config: dict, all_doc_types: list[str]) -> list[str]:
    """
    부서 doc_priority에 따라 문서 유형 목록을 정렬합니다.
    우선순위에 있는 것 → 나머지 순서로 반환합니다.
    """
    priority = dept_config.get("doc_priority", [])
    priority_set = set(priority)

    sorted_types = [dt for dt in priority if dt in all_doc_types]
    sorted_types += [dt for dt in all_doc_types if dt not in priority_set]

    return sorted_types


def get_default_tone(user_ctx: Optional[UserContext]) -> str:
    """직급에 따라 기본 톤을 자동 설정합니다."""
    if not user_ctx:
        return "formal"

    level = user_ctx.position_level
    if level >= 6:  # 부장 이상
        return "executive"
    elif level >= 4:  # 과장~차장
        return "formal"
    else:  # 대리 이하
        return "standard"
