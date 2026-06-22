"""Supplement parser schema tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from src.models.schemas.supplement_parser import (
    SupplementOCRTextParseRequest,
    SupplementStructuredParseResult,
)


def test_structured_parse_result_rejects_fake_nutrient_code() -> None:
    """Verify the LLM cannot invent internal nutrient codes during extraction."""
    with pytest.raises(ValidationError):
        SupplementStructuredParseResult.model_validate(
            {
                "parsed_product": {"product_name": "테스트 비타민"},
                "ingredient_candidates": [
                    {
                        "display_name": "비타민 D",
                        "nutrient_code": "vitamin_d_ug",
                        "amount": 25,
                        "unit": "ug",
                        "confidence": 0.9,
                    }
                ],
                "low_confidence_fields": [],
                "warnings": [],
            }
        )


def test_structured_parse_result_normalizes_warning_lists() -> None:
    """Verify repeated or blank warning strings are removed."""
    result = SupplementStructuredParseResult.model_validate(
        {
            "parsed_product": {"product_name": "테스트 비타민"},
            "ingredient_candidates": [],
            "low_confidence_fields": [" manufacturer ", "", "manufacturer"],
            "warnings": ["사용자 확인 필요", " ", "사용자 확인 필요"],
        }
    )

    assert result.low_confidence_fields == ["manufacturer"]
    assert result.warnings == ["사용자 확인 필요"]


def test_ocr_text_parse_request_bounds_provider_and_confidence() -> None:
    """Verify OCR text attach requests reject invalid provider metadata."""
    request = SupplementOCRTextParseRequest.model_validate(
        {
            "ocr_text": " 비타민 D 1000 ",
            "ocr_provider": " manual ",
            "ocr_confidence": 0.91,
        }
    )

    assert request.ocr_text == "비타민 D 1000"
    assert request.ocr_provider == "manual"
    assert request.ocr_confidence == 0.91

    with pytest.raises(ValidationError):
        SupplementOCRTextParseRequest.model_validate(
            {"ocr_text": "비타민 D", "ocr_provider": "manual", "ocr_confidence": 1.01}
        )

    with pytest.raises(ValidationError):
        SupplementOCRTextParseRequest.model_validate(
            {"ocr_text": "비타민 D", "ocr_provider": "", "ocr_confidence": None}
        )
