"""v4.7 C-2 — i18n_router 단위 테스트."""

from features.onboarding.i18n_router import (
    detect_language,
    resolve_language,
    verify_response_language,
    build_language_instruction,
)


def test_detect_korean():
    assert detect_language("8D 절차를 알려줘") == "ko"
    assert detect_language("안녕하세요 PPAP 요청합니다") == "ko"


def test_detect_english():
    assert detect_language("What is 8D process?") == "en"
    assert detect_language("Please explain the PPAP procedure") == "en"


def test_detect_empty_defaults_korean():
    assert detect_language("") == "ko"
    assert detect_language("???") == "ko"


def test_detect_mixed_threshold():
    # 한글 비율이 30% 이상이면 ko
    assert detect_language("SPC Cpk 절차 알려") == "ko"
    # 영문 전용 약어
    assert detect_language("REACH PPAP 8D ECN") == "en"


def test_resolve_explicit_overrides_auto():
    assert resolve_language("hello", "ko") == "ko"
    assert resolve_language("안녕", "en") == "en"


def test_resolve_auto_detects():
    assert resolve_language("8D 절차", "auto") == "ko"
    assert resolve_language("What is 8D?", "auto") == "en"


def test_verify_response_korean_pass():
    text = "8D는 자동차 산업에서 사용하는 8단계 문제 해결 방법론입니다."
    assert verify_response_language(text, "ko") is True


def test_verify_response_english_pass():
    text = "The 8D process is a structured eight-step problem solving methodology used in the automotive industry."
    assert verify_response_language(text, "en") is True


def test_verify_response_mismatch():
    ko_text = "8D는 자동차 산업에서 사용하는 8단계 문제 해결 방법론입니다."
    assert verify_response_language(ko_text, "en") is False


def test_verify_short_response_passes():
    # 20자 미만은 무조건 통과
    assert verify_response_language("OK", "ko") is True
    assert verify_response_language("OK", "en") is True


def test_build_language_instruction():
    ko = build_language_instruction("ko")
    en = build_language_instruction("en")
    assert "한국어" in ko
    assert "English" in en
