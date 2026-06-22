"""``text_normalizer`` 단위 테스트 — 단위·한·영 공백 정규화 검증.

Reference:
    backend/src/ocr/text_normalizer.py
    docs/ocr_baseline_reports/baseline_summary.md §5
"""

from __future__ import annotations

from src.ocr.text_normalizer import (
    GREEK_MU,
    MICRO_SIGN,
    normalize_ko_en_spacing,
    normalize_ocr_text,
    normalize_units,
)


class TestNormalizeUnits:
    """OCR 가 잘못 읽기 쉬운 단위 표기들을 KDRIs 표준으로."""

    def test_micro_sign_to_greek_mu(self) -> None:
        """U+00B5 micro sign → U+03BC greek mu."""
        assert normalize_units(f"50{MICRO_SIGN}g") == f"50{GREEK_MU}g"

    def test_ascii_u_after_digit(self) -> None:
        """``1000ug`` → ``1000μg`` (숫자 뒤 ASCII u 만 교정)."""
        assert normalize_units("1000ug") == "1000μg"
        assert normalize_units("1000 ug") == "1000 μg"
        assert normalize_units("50ug RAE") == "50μg RAE"

    def test_does_not_touch_word_ug(self) -> None:
        """일반 단어의 ``ug`` 는 건드리지 않는다 — 숫자 직전 또는 단위 키워드 직전만."""
        # ``August`` 안의 'ug' 는 변환하지 않아야 안전. 본 normalizer 는
        # 숫자 직전(``\d+\s*ug``) + 단위 키워드(``RAE/DFE/NE/TE``) 패턴만 잡는다.
        assert normalize_units("August 비타민") == "August 비타민"

    def test_compound_unit_spacing_ug_rae(self) -> None:
        """``μgRAE`` 또는 ``μg  RAE`` → ``μg RAE``."""
        assert normalize_units("50μgRAE") == "50μg RAE"
        assert normalize_units("50μg  RAE") == "50μg RAE"

    def test_compound_unit_spacing_ug_dfe(self) -> None:
        assert normalize_units("400μgDFE") == "400μg DFE"

    def test_compound_unit_spacing_mg_ne(self) -> None:
        assert normalize_units("16mgNE") == "16mg NE"

    def test_compound_unit_alpha_te_normalizes_a_to_alpha(self) -> None:
        """``mg a-TE`` / ``mga-TE`` → ``mg α-TE``."""
        assert normalize_units("12mg a-TE") == "12mg α-TE"
        assert normalize_units("12mga-TE") == "12mg α-TE"
        assert normalize_units("12mgα-TE") == "12mg α-TE"

    def test_idempotent_on_already_normalized(self) -> None:
        """이미 표준 형식이면 변경되지 않는다."""
        assert normalize_units("400μg DFE") == "400μg DFE"
        assert normalize_units("12mg α-TE") == "12mg α-TE"


class TestNormalizeKoEnSpacing:
    """한글 ↔ ASCII alnum 경계 공백 보강."""

    def test_korean_followed_by_letter(self) -> None:
        assert normalize_ko_en_spacing("비타민C") == "비타민 C"

    def test_korean_followed_by_digit(self) -> None:
        assert normalize_ko_en_spacing("비타민1000") == "비타민 1000"

    def test_letter_followed_by_korean(self) -> None:
        assert normalize_ko_en_spacing("Vitamin비타민") == "Vitamin 비타민"

    def test_digit_followed_by_korean(self) -> None:
        assert normalize_ko_en_spacing("3비타민") == "3 비타민"

    def test_already_spaced_unchanged(self) -> None:
        assert normalize_ko_en_spacing("비타민 C 1000mg") == "비타민 C 1000mg"

    def test_does_not_touch_pure_latin(self) -> None:
        assert normalize_ko_en_spacing("Vitamin C 1000mg") == "Vitamin C 1000mg"

    def test_does_not_touch_pure_korean(self) -> None:
        assert normalize_ko_en_spacing("비타민 종합 영양제") == "비타민 종합 영양제"


class TestNormalizeOcrText:
    """단위 + 한·영 공백 통합 진입점."""

    def test_combined_unit_and_spacing(self) -> None:
        """단위 교정 + 한·영 공백 둘 다 적용."""
        # '비타민C1000ug RAE' → unit fix → '비타민C1000μg RAE' → spacing → '비타민 C1000μg RAE'
        # (C↔1000 은 모두 alnum 이라 사이 공백 안 들어감 — 의도된 동작)
        assert normalize_ocr_text("비타민C1000ug RAE") == "비타민 C1000μg RAE"

    def test_micro_sign_with_spacing(self) -> None:
        result = normalize_ocr_text(f"엽산400{MICRO_SIGN}gDFE")
        assert result == "엽산 400μg DFE"

    def test_idempotent(self) -> None:
        already_normalized = "비타민 C 1000μg RAE"
        assert normalize_ocr_text(already_normalized) == already_normalized
