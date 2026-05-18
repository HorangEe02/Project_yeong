"""``src.safety.forbidden_terms`` 단위 테스트 — S2 게이트.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-02-ollama-llm-safety.md Step 3
"""

from __future__ import annotations

import pytest
from src.llm.exceptions import LLMRefusalError
from src.safety.forbidden_terms import (
    FORBIDDEN_TERMS,
    assert_no_forbidden_terms,
    find_forbidden_terms,
)


class TestFindForbiddenTerms:
    """``find_forbidden_terms`` 의 분기 검증."""

    def test_empty_returns_empty_list(self) -> None:
        assert find_forbidden_terms("") == []

    def test_clean_text_returns_empty_list(self) -> None:
        assert find_forbidden_terms("비타민 C 1000mg") == []

    def test_korean_term_detected(self) -> None:
        assert "진단" in find_forbidden_terms("이 영양제는 감기를 진단합니다.")

    def test_english_lowercase_detected(self) -> None:
        assert "diagnose" in find_forbidden_terms("diagnose by your doctor")

    def test_english_uppercase_also_detected_case_insensitive(self) -> None:
        assert "diagnose" in find_forbidden_terms("DIAGNOSE PROPERLY")

    def test_multiple_terms_returned_sorted(self) -> None:
        result = find_forbidden_terms("이것은 처방이며 진단입니다.")
        assert result == sorted(result)
        assert {"진단", "처방"}.issubset(set(result))

    def test_dedup(self) -> None:
        """동일 단어가 여러 번 나와도 한 번만 반환."""
        result = find_forbidden_terms("진단 진단 진단")
        assert result.count("진단") == 1

    def test_phrase_term_detected(self) -> None:
        assert "이 약을 드세요" in find_forbidden_terms("그러니까 이 약을 드세요.")

    def test_treatment_english_detected(self) -> None:
        assert "treatment" in find_forbidden_terms("Recommended treatment")

    def test_constant_is_frozenset(self) -> None:
        """``FORBIDDEN_TERMS`` 는 변경 불가."""
        assert isinstance(FORBIDDEN_TERMS, frozenset)


class TestAssertNoForbiddenTerms:
    """``assert_no_forbidden_terms`` 의 raise 분기."""

    def test_clean_text_passes(self) -> None:
        assert_no_forbidden_terms("비타민 C 1000mg")

    def test_empty_passes(self) -> None:
        assert_no_forbidden_terms("")

    def test_forbidden_term_raises(self) -> None:
        with pytest.raises(LLMRefusalError) as exc_info:
            assert_no_forbidden_terms("처방을 받으세요")
        assert exc_info.value.terms == ["처방"]

    def test_context_appears_in_message(self) -> None:
        with pytest.raises(LLMRefusalError) as exc_info:
            assert_no_forbidden_terms("진단합니다", context="custom_ctx")
        assert "custom_ctx" in str(exc_info.value)

    def test_multiple_terms_listed_on_exception(self) -> None:
        with pytest.raises(LLMRefusalError) as exc_info:
            assert_no_forbidden_terms("진단 + 처방 + diagnose")
        assert set(exc_info.value.terms) == {"진단", "처방", "diagnose"}
