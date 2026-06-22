"""Cross-provider ensemble OCR merge unit tests.

These tests pin the pure in-memory line-union merge helper that supplements a
primary (Clova) OCR result with novel lines from a secondary (Paddle) provider.
The merge never replaces primary text; it only appends bounded novel lines.
"""

from __future__ import annotations

from pydantic import SecretStr
from src.config import Settings
from src.ocr.base import OCRPage, OCRResult
from src.services.supplement_image_analysis import _merge_cross_provider_ocr_results


def _settings(**overrides: object) -> Settings:
    """Return merge-test settings with optional overrides.

    Args:
        **overrides: Per-test settings field overrides.

    Returns:
        Settings instance for merge tests.
    """
    defaults: dict[str, object] = {
        "_env_file": None,
        "privacy_hash_secret": SecretStr("test-privacy-secret"),
        "ocr_secondary_merge_policy": "always",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _result(text: str, *, provider: str, confidence: float | None = 0.9) -> OCRResult:
    """Build an OCR result fixture.

    Args:
        text: OCR text.
        provider: Provider label.
        confidence: Optional provider confidence.

    Returns:
        OCR result fixture.
    """
    return OCRResult(text=text, provider=provider, confidence=confidence)


def test_merge_unions_novel_secondary_lines() -> None:
    """Verify novel secondary lines are appended after primary lines in order."""
    primary = _result("비타민 D 1000\n60 capsules", provider="clova")
    secondary = _result("60 capsules\n마그네슘 400mg", provider="paddleocr")

    merged = _merge_cross_provider_ocr_results(primary, secondary, _settings())

    assert merged is not None
    assert merged.text == "비타민 D 1000\n60 capsules\n마그네슘 400mg"


def test_merge_dedups_whitespace_variant() -> None:
    """Verify a whitespace-only variant of a primary line is not appended."""
    primary = _result("비타민 D 1000", provider="clova")
    secondary = _result("비타민D 1000", provider="paddleocr")

    merged = _merge_cross_provider_ocr_results(primary, secondary, _settings())

    assert merged is not None
    assert merged.text == "비타민 D 1000"


def test_merge_dedups_near_duplicate_above_threshold() -> None:
    """Verify a near-duplicate secondary line above threshold is dropped."""
    primary = _result("마그네슘 400mg", provider="clova")
    secondary = _result("마그네슘 4OOmg", provider="paddleocr")

    merged = _merge_cross_provider_ocr_results(
        primary, secondary, _settings(ocr_merge_dedup_threshold=0.7)
    )

    assert merged is not None
    assert merged.text == "마그네슘 400mg"


def test_merge_keeps_single_char_drift_at_shipped_default_threshold() -> None:
    """Document that the shipped 0.92 default does NOT dedup short 0/O char drift.

    The whole-line SequenceMatcher ratio for "마그네슘 400mg" vs "마그네슘 4OOmg"
    is ~0.78 (< 0.92), so the near-dup layer leaves the secondary variant in.
    Exact + whitespace dedup still fire; this pins the real reach of the default
    so a future threshold change is a deliberate, regression-visible decision.
    """
    primary = _result("마그네슘 400mg", provider="clova")
    secondary = _result("마그네슘 4OOmg", provider="paddleocr")

    merged = _merge_cross_provider_ocr_results(primary, secondary, _settings())

    assert merged is not None
    assert merged.text == "마그네슘 400mg\n마그네슘 4OOmg"


def test_merge_returns_secondary_when_primary_empty() -> None:
    """Verify an empty primary yields the secondary result unchanged."""
    primary = _result("   \n  ", provider="clova")
    secondary = _result("마그네슘 400mg", provider="paddleocr")

    merged = _merge_cross_provider_ocr_results(primary, secondary, _settings())

    assert merged is secondary


def test_merge_returns_primary_when_secondary_empty() -> None:
    """Verify an empty secondary yields the primary result unchanged."""
    primary = _result("비타민 D 1000", provider="clova")
    secondary = _result("", provider="paddleocr")

    merged = _merge_cross_provider_ocr_results(primary, secondary, _settings())

    assert merged is primary


def test_merge_respects_max_supplement_lines() -> None:
    """Verify the number of appended novel lines is bounded by the cap."""
    primary = _result("비타민 D 1000", provider="clova")
    secondary = _result("라인1\n라인2\n라인3", provider="paddleocr")

    merged = _merge_cross_provider_ocr_results(
        primary, secondary, _settings(ocr_merge_max_supplement_lines=2)
    )

    assert merged is not None
    assert merged.text == "비타민 D 1000\n라인1\n라인2"


def test_merge_provider_label_and_confidence_anchor_on_primary() -> None:
    """Verify the merged provider label joins providers and confidence anchors primary."""
    primary = _result("비타민 D 1000", provider="clova", confidence=0.91)
    secondary = _result("마그네슘 400mg", provider="paddleocr", confidence=0.55)

    merged = _merge_cross_provider_ocr_results(primary, secondary, _settings())

    assert merged is not None
    assert merged.provider == "clova+paddleocr"
    assert merged.confidence == 0.91


def test_merge_confidence_falls_back_to_secondary_when_primary_missing() -> None:
    """Verify confidence uses the secondary value only when primary has none."""
    primary = _result("비타민 D 1000", provider="clova", confidence=None)
    secondary = _result("마그네슘 400mg", provider="paddleocr", confidence=0.55)

    merged = _merge_cross_provider_ocr_results(primary, secondary, _settings())

    assert merged is not None
    assert merged.confidence == 0.55


def test_merge_concatenates_pages_from_both_providers() -> None:
    """Verify merged pages preserve primary-then-secondary page order."""
    primary_page = OCRPage(width=10, height=10, confidence=0.9, blocks=())
    secondary_page = OCRPage(width=20, height=20, confidence=0.8, blocks=())
    primary = OCRResult(
        text="비타민 D 1000",
        provider="clova",
        confidence=0.91,
        pages=(primary_page,),
    )
    secondary = OCRResult(
        text="마그네슘 400mg",
        provider="paddleocr",
        confidence=0.55,
        pages=(secondary_page,),
    )

    merged = _merge_cross_provider_ocr_results(primary, secondary, _settings())

    assert merged is not None
    assert merged.pages == (primary_page, secondary_page)
