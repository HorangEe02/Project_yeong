"""LLM 관련 예외 계층.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-02-ollama-llm-safety.md Step 1
"""

from __future__ import annotations


class LLMError(Exception):
    """LLM 처리 실패의 기본 예외."""


class LLMApiError(LLMError):
    """외부 / 로컬 LLM API 호출 실패."""

    def __init__(self, engine: str, message: str) -> None:
        """예외 초기화.

        Args:
            engine: 실패한 LLM 엔진 식별자.
            message: 원인 메시지.
        """
        super().__init__(f"{engine}: {message}")
        self.engine = engine


class LLMParseError(LLMError):
    """LLM 응답 파싱 실패 (JSON 형식 / 스키마 검증 불일치)."""


class LLMRefusalError(LLMError):
    """LLM 응답이 forbidden term 포함 등 정책 위반 시 S2 게이트가 발생시킨다.

    의료법 §27 (무면허 의료행위) / §56 (의료광고 금지) / 약사법 §61, §68
    잠재 위반 표면을 차단한다.

    Reference:
        /Users/yeong/.claude/plans/ocr-yolo-sprightly-neumann.md §3.2 S2
        docs/10-compliance-checklist.md §10
    """

    def __init__(self, reason: str, terms: list[str] | None = None) -> None:
        """예외 초기화.

        Args:
            reason: 위반 사유.
            terms: 발견된 금지 표현 목록.
        """
        super().__init__(reason)
        self.terms: list[str] = terms or []
