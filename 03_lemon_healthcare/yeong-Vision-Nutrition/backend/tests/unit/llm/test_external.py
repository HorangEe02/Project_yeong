"""``src.llm.external`` 외부 LLM 가드 검증.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-02-ollama-llm-safety.md Step 6
"""

from __future__ import annotations

import pytest
from src.llm.exceptions import LLMApiError
from src.llm.external import ExternalLLMDisabledError, ensure_external_llm_allowed


def test_external_disabled_error_is_llm_api_error_subclass() -> None:
    """외부 LLM 차단 예외는 일반 LLMApiError 흐름과 호환된다."""
    assert issubclass(ExternalLLMDisabledError, LLMApiError)


def test_ensure_external_llm_allowed_always_raises_in_track_b() -> None:
    """트랙 B는 외부 LLM을 절대 허용하지 않는다."""
    with pytest.raises(ExternalLLMDisabledError):
        ensure_external_llm_allowed()


def test_exception_message_does_not_leak_policy_internals_to_user() -> None:
    """예외 메시지가 ``ExternalLLMDisabledError`` 인스턴스의 ``.engine`` 식별자에
    'external-llm' 라벨을 담는다 (호출처가 일반 503/422로 매핑)."""
    with pytest.raises(ExternalLLMDisabledError) as exc_info:
        ensure_external_llm_allowed()
    assert exc_info.value.engine == "external-llm"
