"""선제적 가이드 엔진 — 아직 탐색하지 않은 필수 항목을 자동 추천한다.

신입사원이 "뭘 물어봐야 할지 모르겠어요" 상황에서
부서별 필수 교육 항목과 핵심 업무를 기반으로 추천 질문을 생성한다.

데이터 소스:
- core.department_config.DEPARTMENT_REGISTRY → onboarding_essentials
- features.onboarding.department_router.DEPARTMENT_PROFILES → core_responsibilities
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _get_essential_topics(department: str) -> list[str]:
    """부서별 필수 온보딩 항목을 조회한다."""
    try:
        from core.department_config import get_dept_config
        config = get_dept_config(department)
        essentials = list(config.get("onboarding_essentials", []))
    except Exception:
        essentials = []

    # department_router에서 핵심 업무도 가져옴
    try:
        from features.onboarding.department_router import DEPARTMENT_PROFILES
        profile = DEPARTMENT_PROFILES.get(department)
        if profile:
            for resp in profile.core_responsibilities:
                if resp not in essentials:
                    essentials.append(resp)
    except Exception:
        pass

    return essentials


def _normalize_term(term: str) -> str:
    """비교를 위해 정규화한다."""
    return term.strip().lower().replace(" ", "")


def _is_covered(topic: str, asked_terms: list[str]) -> bool:
    """해당 주제가 이미 질문된 용어에 포함되는지 판단한다."""
    norm_topic = _normalize_term(topic)
    for asked in asked_terms:
        norm_asked = _normalize_term(asked)
        # 부분 매칭: 질문 용어가 주제에 포함되거나, 주제가 질문에 포함
        if norm_topic in norm_asked or norm_asked in norm_topic:
            return True
    return False


def get_uncovered_topics(
    department: str,
    asked_terms: list[str],
) -> list[str]:
    """아직 질문하지 않은 필수 항목을 반환한다.

    Args:
        department: 사용자 부서명
        asked_terms: ConversationSession.asked_terms (이미 질문한 용어)

    Returns:
        미탐색 필수 항목 리스트
    """
    essentials = _get_essential_topics(department)
    if not essentials:
        return []

    uncovered = [
        topic for topic in essentials
        if not _is_covered(topic, asked_terms)
    ]
    return uncovered


def generate_suggestions(
    department: str,
    asked_terms: list[str],
    max_suggestions: int = 3,
) -> list[dict]:
    """추천 질문을 생성한다.

    Returns:
        [{"topic": str, "question": str, "priority": str}, ...]
        priority: "essential" (필수) / "recommended" (권장)
    """
    uncovered = get_uncovered_topics(department, asked_terms)
    if not uncovered:
        return []

    suggestions = []
    for i, topic in enumerate(uncovered[:max_suggestions]):
        # 질문 형태로 변환
        question = _topic_to_question(topic, department)
        priority = "essential" if i < 2 else "recommended"
        suggestions.append({
            "topic": topic,
            "question": question,
            "priority": priority,
        })

    return suggestions


def _topic_to_question(topic: str, department: str) -> str:
    """주제를 자연스러운 질문으로 변환한다."""
    # 약어/영문이면 "~가 뭐야?" 패턴
    if any(c.isupper() for c in topic) and len(topic) <= 10:
        return f"{topic}가 뭐야?"
    # 시스템/절차면 "~는 어떻게 사용해?" 패턴
    if any(kw in topic for kw in ("시스템", "포털", "ERP", "MES")):
        return f"{topic}는 어떻게 사용해?"
    # 업무면 "~에 대해 알려줘" 패턴
    if any(kw in topic for kw in ("관리", "대응", "점검", "검사", "심사")):
        return f"{topic}에 대해 알려줘"
    # 기본 패턴
    return f"{topic}이(가) 뭔지 알려줘"


def calculate_onboarding_progress(
    department: str,
    asked_terms: list[str],
) -> dict:
    """온보딩 진행률을 계산한다.

    Returns:
        {"total": int, "covered": int, "progress_pct": float,
         "uncovered": list[str], "status": str}
    """
    essentials = _get_essential_topics(department)
    if not essentials:
        return {
            "total": 0, "covered": 0, "progress_pct": 0.0,
            "uncovered": [], "status": "no_data",
        }

    covered = [t for t in essentials if _is_covered(t, asked_terms)]
    uncovered = [t for t in essentials if not _is_covered(t, asked_terms)]
    pct = round(len(covered) / len(essentials) * 100, 1) if essentials else 0.0

    if pct >= 80:
        status = "advanced"
    elif pct >= 50:
        status = "intermediate"
    elif pct >= 20:
        status = "beginner"
    else:
        status = "starting"

    return {
        "total": len(essentials),
        "covered": len(covered),
        "progress_pct": pct,
        "uncovered": uncovered,
        "status": status,
    }
