"""OCR metrics 단위 테스트 — CER/WER/exact_match/field_exact_match.

Reference:
    backend/src/ocr/metrics.py
"""

from __future__ import annotations

import math

import pytest
from src.ocr.metrics import (
    cer,
    exact_match,
    field_exact_match,
    field_match_ratio,
    normalize_text,
    wer,
)


class TestNormalizeText:
    """``normalize_text`` 규칙 검증."""

    def test_strips_outer_whitespace(self) -> None:
        """양끝 공백·줄바꿈은 제거된다."""
        assert normalize_text("  비타민 C\n") == "비타민 C"

    def test_collapses_repeated_whitespace(self) -> None:
        """연속 공백·탭·줄바꿈은 단일 스페이스로 축약된다."""
        assert normalize_text("비타민\t\tC\n\n1000mg") == "비타민 C 1000mg"

    def test_case_sensitive_default_keeps_case(self) -> None:
        """기본값 case_sensitive=True 에서는 대소문자가 보존된다."""
        assert normalize_text("Vitamin C") == "Vitamin C"

    def test_case_insensitive_lowers(self) -> None:
        """case_sensitive=False 면 lowercase 적용."""
        assert normalize_text("Vitamin C", case_sensitive=False) == "vitamin c"

    def test_nfc_unicode_normalization(self) -> None:
        """NFD(분해형) → NFC(합성형) 변환으로 한글이 정규화된다."""
        decomposed = "비타민 C"  # 합성형
        assert normalize_text(decomposed) == "비타민 C"


class TestCER:
    """CER (Character Error Rate) 검증."""

    def test_identical_strings_returns_zero(self) -> None:
        """동일 텍스트는 CER 0.0."""
        assert cer("비타민 C 1000mg", "비타민 C 1000mg") == 0.0

    def test_normalization_handles_whitespace(self) -> None:
        """공백 차이는 정규화로 흡수되어 CER 0.0."""
        assert cer("비타민  C  1000mg", "비타민 C 1000mg") == 0.0

    def test_single_char_diff(self) -> None:
        """1글자 차이 (D vs C). gt='비타민 C' (5글자) → CER=1/5=0.2."""
        assert cer("비타민 D", "비타민 C") == pytest.approx(0.2)

    def test_english_text(self) -> None:
        """영문도 동일하게 동작."""
        # 'Vitamin C' (9글자) → 'Vitamim C' (m←n): 1글자 차이
        assert cer("Vitamim C", "Vitamin C") == pytest.approx(1 / 9)

    def test_mixed_korean_english(self) -> None:
        """한·영 혼합 — 글자 단위 비교."""
        # gt='비타민 C 1000mg' (12글자) — '비타민 D 1000mg': 1글자 차이
        assert cer("비타민 D 1000mg", "비타민 C 1000mg") == pytest.approx(1 / 12)

    def test_empty_gt_with_empty_pred_returns_zero(self) -> None:
        """둘 다 비어 있으면 정의상 0.0."""
        assert cer("", "") == 0.0

    def test_empty_gt_with_nonempty_pred_returns_inf(self) -> None:
        """gt 가 비었는데 pred 가 있으면 inf."""
        assert math.isinf(cer("anything", ""))

    def test_case_insensitive_match(self) -> None:
        """case_sensitive=False 에서 대소문자만 다른 경우 CER 0.0."""
        assert cer("VITAMIN C", "vitamin c", case_sensitive=False) == 0.0


class TestWER:
    """WER (Word Error Rate) 검증."""

    def test_identical_strings_returns_zero(self) -> None:
        """동일 텍스트는 WER 0.0."""
        assert wer("비타민 C 1000mg", "비타민 C 1000mg") == 0.0

    def test_single_word_diff_out_of_three(self) -> None:
        """3 단어 중 1개 다름 → WER=1/3."""
        assert wer("비타민 D 1000mg", "비타민 C 1000mg") == pytest.approx(1 / 3)

    def test_extra_word_increases_wer(self) -> None:
        """gt 3단어, pred 가 4단어로 1개 추가 → 삽입 1개 → 1/3."""
        assert wer("비타민 C 1000mg 추가", "비타민 C 1000mg") == pytest.approx(1 / 3)

    def test_empty_gt_empty_pred_zero(self) -> None:
        assert wer("", "") == 0.0

    def test_empty_gt_nonempty_pred_inf(self) -> None:
        assert math.isinf(wer("word", ""))


class TestExactMatch:
    """``exact_match`` 검증."""

    def test_identical_returns_true(self) -> None:
        assert exact_match("비타민 C", "비타민 C") is True

    def test_normalization_collapses_whitespace(self) -> None:
        """다중 공백은 정규화로 흡수."""
        assert exact_match("비타민  C", "비타민 C") is True

    def test_one_char_diff_returns_false(self) -> None:
        assert exact_match("비타민 D", "비타민 C") is False

    def test_case_sensitive_default(self) -> None:
        assert exact_match("Vitamin C", "vitamin c") is False

    def test_case_insensitive_option(self) -> None:
        assert exact_match("Vitamin C", "vitamin c", case_sensitive=False) is True


class TestFieldExactMatch:
    """필드 단위 매칭 검증."""

    def test_all_fields_match(self) -> None:
        result = field_exact_match(
            {"product_name": "비타민 C", "dosage": "1000mg"},
            {"product_name": "비타민 C", "dosage": "1000mg"},
        )
        assert result == {"product_name": True, "dosage": True}

    def test_field_mismatch_reported(self) -> None:
        result = field_exact_match(
            {"product_name": "비타민 D", "dosage": "1000mg"},
            {"product_name": "비타민 C", "dosage": "1000mg"},
        )
        assert result == {"product_name": False, "dosage": True}

    def test_both_none_treated_as_match(self) -> None:
        """gt 가 None 이고 pred 도 None 이면 일치 (필드 부재 일치)."""
        result = field_exact_match(
            {"product_name": "X", "dosage": None},
            {"product_name": "X", "dosage": None},
        )
        assert result == {"product_name": True, "dosage": True}

    def test_one_side_none_is_mismatch(self) -> None:
        result = field_exact_match(
            {"product_name": "X", "dosage": "1mg"},
            {"product_name": "X", "dosage": None},
        )
        assert result["dosage"] is False

    def test_extra_pred_field_ignored(self) -> None:
        """pred 에만 있는 키는 평가에 포함되지 않는다."""
        result = field_exact_match(
            {"product_name": "X", "extra": "junk"},
            {"product_name": "X"},
        )
        assert result == {"product_name": True}


class TestFieldMatchRatio:
    """필드 매칭 평균 비율 검증."""

    def test_all_match_returns_one(self) -> None:
        assert (
            field_match_ratio(
                {"product_name": "X", "dosage": "1mg"},
                {"product_name": "X", "dosage": "1mg"},
            )
            == 1.0
        )

    def test_half_match(self) -> None:
        assert (
            field_match_ratio(
                {"product_name": "X", "dosage": "WRONG"},
                {"product_name": "X", "dosage": "1mg"},
            )
            == 0.5
        )

    def test_empty_gt_returns_one_vacuously(self) -> None:
        """gt 가 비어있으면 정의상 1.0 (vacuously true)."""
        assert field_match_ratio({}, {}) == 1.0
