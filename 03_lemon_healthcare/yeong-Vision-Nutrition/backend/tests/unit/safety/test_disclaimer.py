"""``src.safety.disclaimer`` 텍스트 상수 검증."""

from __future__ import annotations

from src.safety.disclaimer import (
    CONSULT_PROFESSIONAL_MESSAGE_KO,
    EMERGENCY_RESOURCES_KO,
    MAIN_DISCLAIMER_KO,
    SUPPLEMENT_DISCLAIMER_KO,
)


def test_all_disclaimers_non_empty() -> None:
    assert MAIN_DISCLAIMER_KO.strip()
    assert SUPPLEMENT_DISCLAIMER_KO.strip()
    assert CONSULT_PROFESSIONAL_MESSAGE_KO.strip()


def test_main_disclaimer_mentions_professional_consultation() -> None:
    assert "전문가" in MAIN_DISCLAIMER_KO


def test_supplement_disclaimer_mentions_no_treatment_guarantee() -> None:
    """영양제는 의약품이 아니라는 명시."""
    assert "의약품" in SUPPLEMENT_DISCLAIMER_KO


def test_emergency_resources_three_or_more_entries() -> None:
    assert len(EMERGENCY_RESOURCES_KO) >= 3
    for entry in EMERGENCY_RESOURCES_KO:
        assert "name" in entry
        assert "phone" in entry
        assert entry["phone"]


def test_emergency_resources_include_known_korean_hotlines() -> None:
    phones = {e["phone"] for e in EMERGENCY_RESOURCES_KO}
    # docs/10 §11.1 의 핵심 3개 번호
    assert {"1577-0199", "109", "1339"}.issubset(phones)
