"""의료법·약사법 금지 표현 자동 검출 — S2 안전 게이트.

LLM 응답·서비스 응답 텍스트를 라우터/응답 직전 단계에서 검사한다. 발견 시
``LLMRefusalError`` 로 차단하고, 호출처는 사용자에게 안전 메시지로 대체 응답한다.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-02-ollama-llm-safety.md Step 3
    /Users/yeong/.claude/plans/ocr-yolo-sprightly-neumann.md §3.2 S2
    docs/10-compliance-checklist.md §10
"""

from __future__ import annotations

from typing import Final

from src.llm.exceptions import LLMRefusalError

FORBIDDEN_TERMS: Final[frozenset[str]] = frozenset(
    {
        # 의료법 §27 — 진단·처방·치료
        "진단",
        "처방",
        "처방전",
        "처방약",
        "치료",
        "치료제",
        # 약사법 §61, §68 — 의약품 직접 추천
        "이 약을 드세요",
        "이 의약품",
        "복용하세요",
        # 의료법 §56 — 효과 단정 (의료광고)
        "보장",
        "확실히",
        "분명히",
        "즉효",
        # 영어 동치
        "diagnose",
        "diagnosis",
        "prescribe",
        "prescription",
        "cure",
        "treat",
        "treatment",
    }
)
"""금지 표현 집합. 변경 시 ``docs/10-compliance-checklist.md §10`` 와 동기화."""


def find_forbidden_terms(text: str) -> list[str]:
    """``text`` 에 포함된 금지 표현을 알파벳 / 가나다 순으로 반환.

    Args:
        text: 검사할 문자열. ``None`` / 빈 문자열은 빈 리스트.

    Returns:
        발견된 금지 표현의 정렬된 리스트. 중복 제거.

    Examples:
        >>> find_forbidden_terms("비타민 C는 감기를 진단합니다")
        ['진단']
        >>> find_forbidden_terms("Diagnose by your doctor")
        ['diagnose']
        >>> find_forbidden_terms("")
        []
    """
    if not text:
        return []
    lower = text.lower()
    found = {term for term in FORBIDDEN_TERMS if term.lower() in lower}
    return sorted(found)


def assert_no_forbidden_terms(text: str, context: str = "llm_response") -> None:
    """``text`` 에 금지 표현이 발견되면 ``LLMRefusalError`` 를 raise한다.

    Args:
        text: 검사할 응답 텍스트.
        context: 로그 분석용 컨텍스트 라벨 (엔진명 또는 단계명).

    Raises:
        LLMRefusalError: 금지 표현이 1개 이상 발견된 경우.
    """
    found = find_forbidden_terms(text)
    if found:
        raise LLMRefusalError(
            reason=f"Forbidden terms detected in {context}",
            terms=found,
        )
