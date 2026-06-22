"""한국어/영문 분리 텍스트 메트릭 단위 테스트."""

from __future__ import annotations

import pytest
from src.utils.text_metrics import (
    character_error_rate,
    classify_char_language,
    language_segmented_error_rates,
    levenshtein_distance,
    split_text_by_language,
    word_error_rate,
)


class TestClassifyCharLanguage:
    """문자 단위 언어 분류 테스트."""

    @pytest.mark.parametrize(
        ("char", "expected"),
        [
            ("가", "ko"),  # 한글 음절 시작
            ("힣", "ko"),  # 한글 음절 끝
            ("ㄱ", "ko"),  # 한글 호환 자모
            ("ㆎ", "ko"),  # 한글 호환 자모 끝
            ("A", "en"),
            ("z", "en"),
            ("1", "other"),
            (" ", "other"),
            ("中", "other"),  # 한자
            ("%", "other"),
        ],
    )
    def test_known_characters(self, char: str, expected: str) -> None:
        """각 문자 카테고리가 올바르게 분류된다."""
        assert classify_char_language(char) == expected

    def test_rejects_multi_char_input(self) -> None:
        """2글자 이상은 ValueError 발생."""
        with pytest.raises(ValueError, match="single character"):
            classify_char_language("AB")

    def test_rejects_empty_string(self) -> None:
        """빈 문자열은 ValueError 발생."""
        with pytest.raises(ValueError, match="single character"):
            classify_char_language("")


class TestSplitTextByLanguage:
    """텍스트 언어별 분리 테스트."""

    def test_korean_only(self) -> None:
        """한국어만 있는 텍스트는 한국어 토큰만 채워진다."""
        result = split_text_by_language("비타민")
        assert result["ko"] == "비타민"
        assert result["en"] == ""

    def test_english_only(self) -> None:
        """영문만 있는 텍스트는 영문 토큰만 채워진다."""
        result = split_text_by_language("Vitamin")
        assert result["ko"] == ""
        assert result["en"] == "Vitamin"

    def test_korean_english_mixed_with_space(self) -> None:
        """공백 구분된 한/영 혼합 케이스."""
        result = split_text_by_language("비타민 C 100 mg")
        assert result["ko"] == "비타민"
        assert result["en"] == "C mg"

    def test_korean_english_adjacent(self) -> None:
        """공백 없이 붙은 한/영 전환도 분리된다."""
        result = split_text_by_language("비타민C100mg")
        assert result["ko"] == "비타민"
        assert result["en"] == "C mg"

    def test_numbers_and_symbols_ignored(self) -> None:
        """숫자/기호는 어느 쪽에도 포함되지 않는다."""
        result = split_text_by_language("123 !@# 456")
        assert result["ko"] == ""
        assert result["en"] == ""

    def test_empty_string(self) -> None:
        """빈 문자열은 빈 사전을 반환한다."""
        result = split_text_by_language("")
        assert result["ko"] == ""
        assert result["en"] == ""


class TestLevenshteinDistance:
    """Levenshtein 거리 계산 테스트."""

    def test_classic_kitten_sitting(self) -> None:
        """[고전 예시] kitten → sitting 의 거리는 3."""
        assert levenshtein_distance("kitten", "sitting") == 3

    def test_identical_strings(self) -> None:
        """같은 문자열은 거리 0."""
        assert levenshtein_distance("abc", "abc") == 0

    def test_empty_hypothesis(self) -> None:
        """가설이 비면 거리는 기준 길이."""
        assert levenshtein_distance("", "abc") == 3

    def test_empty_reference(self) -> None:
        """기준이 비면 거리는 가설 길이."""
        assert levenshtein_distance("abc", "") == 3

    def test_both_empty(self) -> None:
        """둘 다 비면 거리 0."""
        assert levenshtein_distance("", "") == 0

    def test_korean_string(self) -> None:
        """한글 단위로도 계산된다 (한글 1글자 = 1 거리)."""
        # "비타민C" vs "비타민 C": 공백 1개 삽입 → 거리 1
        assert levenshtein_distance("비타민C", "비타민 C") == 1


class TestCharacterErrorRate:
    """CER 계산 테스트."""

    def test_exact_match(self) -> None:
        """완전히 일치하면 CER 0.0."""
        assert character_error_rate("abc", "abc") == 0.0

    def test_one_insertion_in_five(self) -> None:
        """5글자 기준에서 1개 삽입 누락 → CER 0.2."""
        # "비타민C" (4) vs "비타민 C" (5): 거리 1 / 5 = 0.2
        assert character_error_rate("비타민C", "비타민 C") == pytest.approx(0.2, abs=1e-6)

    def test_empty_hypothesis_against_non_empty_reference(self) -> None:
        """빈 가설은 기준 길이만큼 오류 → CER = 1.0."""
        assert character_error_rate("", "abc") == 1.0

    def test_empty_reference_with_empty_hypothesis(self) -> None:
        """둘 다 비면 0.0."""
        assert character_error_rate("", "") == 0.0

    def test_empty_reference_with_non_empty_hypothesis(self) -> None:
        """기준이 비고 가설이 있으면 1.0 (관례)."""
        assert character_error_rate("hello", "") == 1.0


class TestWordErrorRate:
    """WER 계산 테스트."""

    def test_exact_match(self) -> None:
        """완전 일치 시 WER 0.0."""
        assert word_error_rate("the cat sat", "the cat sat") == 0.0

    def test_one_word_missing(self) -> None:
        """3 단어 기준 1개 누락 → WER ≈ 0.333."""
        assert word_error_rate("the cat", "the cat sat") == pytest.approx(1 / 3, abs=1e-6)

    def test_empty_hypothesis(self) -> None:
        """빈 가설 → WER 1.0."""
        assert word_error_rate("", "a b c") == 1.0

    def test_both_empty(self) -> None:
        """둘 다 비면 0.0."""
        assert word_error_rate("", "") == 0.0


class TestLanguageSegmentedErrorRates:
    """한/영 분리 CER/WER 통합 테스트."""

    def test_perfect_match_korean_english_mixed(self) -> None:
        """한/영 혼합이 정확히 일치하면 모든 메트릭 0.0."""
        rates = language_segmented_error_rates("비타민 C", "비타민 C")
        assert rates["cer_ko"] == 0.0
        assert rates["cer_en"] == 0.0
        assert rates["wer_ko"] == 0.0
        assert rates["wer_en"] == 0.0

    def test_korean_only_difference(self) -> None:
        """한국어 부분에만 오차가 있으면 한국어 메트릭만 0보다 크다."""
        rates = language_segmented_error_rates("비타 C", "비타민 C")
        assert rates["cer_ko"] > 0.0
        assert rates["cer_en"] == 0.0

    def test_english_only_difference(self) -> None:
        """영문 부분에만 오차가 있으면 영문 메트릭만 0보다 크다."""
        rates = language_segmented_error_rates("비타민 D", "비타민 C")
        assert rates["cer_ko"] == 0.0
        assert rates["cer_en"] > 0.0

    def test_returns_all_four_keys(self) -> None:
        """모든 키가 반환된다 (None 없음)."""
        rates = language_segmented_error_rates("", "")
        assert set(rates.keys()) == {"cer_ko", "cer_en", "wer_ko", "wer_en"}
