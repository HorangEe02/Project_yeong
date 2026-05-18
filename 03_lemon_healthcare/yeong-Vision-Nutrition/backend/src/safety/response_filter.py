"""응답 직전 안전 게이트 — 사용자에게 노출되는 콘텐츠에서 forbidden term 차단.

면책 문구(``disclaimer.MAIN_DISCLAIMER_KO`` 등)는 "진단·처방을 대체하지 않습니다"
같은 의도적 의료법 회피 표현을 포함하므로 본 게이트의 검사 대상에서 명시적으로
제외된다. SupplementService 는 ``assert_response_safe`` 에 사용자-생성 콘텐츠
필드(제품명·제조사·진단 메시지·성분명·summary)만 전달한다.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-05-api-integration.md Step 6
    /Users/yeong/.claude/plans/ocr-yolo-sprightly-neumann.md §3.2 S2
"""

from __future__ import annotations

from src.safety.forbidden_terms import find_forbidden_terms


class ResponseFilterError(RuntimeError):
    """응답에 forbidden term 이 포함된 경우 발생.

    SupplementService 가 본 예외를 catch 해 사용자에게는 500 generic 응답 + 감사
    로그에 ``response_filter.blocked`` 액션을 기록한다.
    """

    def __init__(self, terms: list[str]) -> None:
        super().__init__(f"Forbidden terms detected in response: {terms}")
        self.terms = terms


def scan_user_content(*texts: str) -> list[str]:
    """``texts`` 에서 forbidden term 을 모아 정렬된 리스트로 반환.

    Args:
        *texts: 검사할 임의 개수의 문자열. 빈 문자열은 무시.

    Returns:
        발견된 금지 표현 정렬된 리스트 (중복 제거).
    """
    found: set[str] = set()
    for text in texts:
        if not text:
            continue
        found.update(find_forbidden_terms(text))
    return sorted(found)


def assert_response_safe(*texts: str) -> None:
    """``texts`` 에 forbidden term 이 0건임을 보장한다.

    Args:
        *texts: 검사할 user-content 그룹. disclaimer / emergency resources 는
            절대 본 함수에 전달하지 않는다.

    Raises:
        ResponseFilterError: forbidden term 이 1개 이상 발견된 경우.
    """
    found = scan_user_content(*texts)
    if found:
        raise ResponseFilterError(found)
