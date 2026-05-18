"""``src.safety.response_filter`` 단위 테스트."""

from __future__ import annotations

import pytest
from src.safety.response_filter import (
    ResponseFilterError,
    assert_response_safe,
    scan_user_content,
)


class TestScanUserContent:
    def test_empty_returns_empty(self) -> None:
        assert scan_user_content() == []
        assert scan_user_content("", "") == []

    def test_clean_text_returns_empty(self) -> None:
        assert scan_user_content("비타민 C 1000mg", "종합비타민") == []

    def test_finds_forbidden_term(self) -> None:
        assert "진단" in scan_user_content("이것은 진단입니다")

    def test_deduplicates_across_inputs(self) -> None:
        result = scan_user_content("진단", "진단", "또 진단")
        assert result.count("진단") == 1


class TestAssertResponseSafe:
    def test_clean_passes(self) -> None:
        assert_response_safe("비타민 C", "종합비타민", "")

    def test_forbidden_raises(self) -> None:
        with pytest.raises(ResponseFilterError) as exc_info:
            assert_response_safe("이것은 진단입니다")
        assert "진단" in exc_info.value.terms

    def test_multiple_forbidden_listed(self) -> None:
        with pytest.raises(ResponseFilterError) as exc_info:
            assert_response_safe("진단", "처방")
        assert set(exc_info.value.terms) == {"진단", "처방"}
