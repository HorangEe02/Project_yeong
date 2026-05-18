"""외부 LLM 사용 가드 — 트랙 B에서 항상 raise.

트랙 B는 ``docs/12-local-llm-ollama-migration.md §1`` 에 따라 환자 식별 가능
정보를 외부 LLM(Anthropic / OpenAI / Ollama Cloud)으로 보내지 않는다. 외부 LLM을
사용하려는 호출은 본 가드에 의해 ``ExternalLLMDisabledError`` 로 즉시 차단된다.

비식별 테스트 또는 발주처 승인 환경 도입 시, 본 가드를 별도 build profile에서
override하거나 명시적 ``allow=True`` 인자를 받는 메서드를 추가한다 (트랙 OUT OF
SCOPE — Phase 02 외 후속 단계).

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-02-ollama-llm-safety.md Step 6
    docs/12-local-llm-ollama-migration.md §1, §2
"""

from __future__ import annotations

from src.llm.exceptions import LLMApiError


class ExternalLLMDisabledError(LLMApiError):
    """외부 LLM 호출이 정책상 비활성화된 경우 발생.

    호출처는 본 예외를 잡아 사용자에게 "외부 LLM은 비활성화되어 있습니다"
    보다는 일반 503/422 응답으로 매핑한다 (정책 노출 회피).
    """


def ensure_external_llm_allowed() -> None:
    """외부 LLM 사용 가능 여부를 검증한다.

    트랙 B는 항상 ``ExternalLLMDisabledError`` 를 raise한다. 비식별 테스트나
    발주처 승인 환경 도입 시 본 함수를 별도 build profile에서 교체한다.

    Raises:
        ExternalLLMDisabledError: 트랙 B에서는 항상 발생.
    """
    raise ExternalLLMDisabledError(
        engine="external-llm",
        message=(
            "External LLM calls are disabled for identifiable patient data "
            "(docs/12 §1). Use OllamaAdapter (local) only."
        ),
    )
