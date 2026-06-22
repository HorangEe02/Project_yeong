"""Unit tests for supplement-parser excipient filtering + OCR pattern fallback.

Covers the recent changes:
- ``_is_excipient_name`` exact normalized-name matching (no false drops).
- ``_extract_ocr_pattern_ingredient_candidates`` excludes excipients on the
  fallback path too (parity with the LLM-path sanitizer).

These are pure functions, so they need no DB session or Pydantic schema setup.
"""

from __future__ import annotations

from src.services.supplement_parser import (
    OCR_PATTERN_FALLBACK_SOURCE,
    _extract_ocr_pattern_ingredient_candidates,
    _is_excipient_name,
)


class TestIsExcipientName:
    """Exact normalized-name excipient matching."""

    def test_matches_known_excipients_case_insensitive(self) -> None:
        assert _is_excipient_name("gelatin")
        assert _is_excipient_name("Gelatin")
        assert _is_excipient_name("GLYCERIN")
        assert _is_excipient_name("purified water")
        assert _is_excipient_name("젤라틴")
        assert _is_excipient_name("정제수")

    def test_does_not_drop_active_nutrients(self) -> None:
        # Exact match only — substrings of excipient names must not match.
        assert not _is_excipient_name("Vitamin C")
        assert not _is_excipient_name("magnesium")  # not "magnesium stearate"
        assert not _is_excipient_name("BCAA")
        assert not _is_excipient_name("")


class TestExtractOcrPatternCandidates:
    """Bounded name+amount+unit extraction with excipient exclusion."""

    def test_extracts_name_amount_unit(self) -> None:
        candidates = _extract_ocr_pattern_ingredient_candidates("Vitamin C 1000 mg")
        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate["display_name"] == "Vitamin C"
        assert candidate["amount"] == 1000
        assert candidate["unit"] == "mg"
        assert candidate["source"] == OCR_PATTERN_FALLBACK_SOURCE

    def test_excludes_excipients_from_fallback(self) -> None:
        candidates = _extract_ocr_pattern_ingredient_candidates(
            "Vitamin C 1000 mg\nGelatin 100 mg\nGlycerin 50 mg"
        )
        names = {str(candidate["display_name"]).lower() for candidate in candidates}
        assert "vitamin c" in names
        assert "gelatin" not in names
        assert "glycerin" not in names

    def test_extracts_daily_value_percent(self) -> None:
        candidates = _extract_ocr_pattern_ingredient_candidates("Vitamin C 1000 mg 100%")
        assert len(candidates) == 1
        assert candidates[0]["amount"] == 1000
        assert candidates[0]["unit"] == "mg"
        assert candidates[0]["daily_value_percent"] == 100

    def test_daily_value_percent_is_none_when_absent(self) -> None:
        candidates = _extract_ocr_pattern_ingredient_candidates("Vitamin C 1000 mg")
        assert candidates[0]["daily_value_percent"] is None
