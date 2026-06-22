"""Unit tests for ``MultilingualOCRAdapter`` branch behavior."""

from __future__ import annotations

import pytest
from src.ocr.base import OCRAdapter, OCRError, OCRImageInput, OCRResult
from src.ocr.multilingual_adapter import MultilingualOCRAdapter


class _FakeAdapter(OCRAdapter):
    """Test adapter with controllable response and call tracking."""

    def __init__(
        self,
        provider: str = "fake",
        text: str = "ok",
        confidence: float | None = 0.9,
        raises: Exception | None = None,
    ) -> None:
        """Initialize the fake OCR adapter.

        Args:
            provider: Provider label returned in ``OCRResult``.
            text: OCR text returned on success.
            confidence: OCR confidence returned on success.
            raises: Optional exception raised by ``extract_text``.
        """
        self._provider = provider
        self._text = text
        self._confidence = confidence
        self._raises = raises
        self.call_count = 0
        self.received_images: list[OCRImageInput] = []

    async def extract_text(self, image: OCRImageInput) -> OCRResult:
        """Return a configured OCR result or raise a configured exception."""
        self.call_count += 1
        self.received_images.append(image)
        if self._raises is not None:
            raise self._raises
        return OCRResult(text=self._text, provider=self._provider, confidence=self._confidence)


def _image() -> OCRImageInput:
    """Build a minimal validated OCR image input fixture.

    Returns:
        OCR image input accepted by the adapter contract.
    """
    return OCRImageInput(
        image_bytes=b"image",
        mime_type="image/png",
        width=1,
        height=1,
    )


class TestBothSucceed:
    """Both adapters succeed."""

    @pytest.mark.asyncio
    async def test_primary_higher_confidence_wins(self) -> None:
        """Return primary result when primary confidence is higher."""
        image = _image()
        primary = _FakeAdapter(provider="ko", text="비타민 C", confidence=0.95)
        secondary = _FakeAdapter(provider="en", text="Vitamin C", confidence=0.70)
        adapter = MultilingualOCRAdapter(primary=primary, secondary=secondary)

        result = await adapter.extract_text(image)

        assert result.text == "비타민 C"
        assert result.provider == "ko"
        assert primary.call_count == 1
        assert secondary.call_count == 1
        assert primary.received_images == [image]
        assert secondary.received_images == [image]

    @pytest.mark.asyncio
    async def test_secondary_higher_confidence_wins(self) -> None:
        """Return secondary result when secondary confidence is higher."""
        primary = _FakeAdapter(provider="ko", text="비타민 C", confidence=0.40)
        secondary = _FakeAdapter(provider="en", text="Vitamin C", confidence=0.95)
        adapter = MultilingualOCRAdapter(primary=primary, secondary=secondary)

        result = await adapter.extract_text(_image())

        assert result.text == "Vitamin C"
        assert result.provider == "en"

    @pytest.mark.asyncio
    async def test_tie_breaks_toward_primary(self) -> None:
        """Return primary result when confidence values tie."""
        primary = _FakeAdapter(provider="ko", text="비타민", confidence=0.85)
        secondary = _FakeAdapter(provider="en", text="Vitamin", confidence=0.85)
        adapter = MultilingualOCRAdapter(primary=primary, secondary=secondary)

        result = await adapter.extract_text(_image())

        assert result.provider == "ko"

    @pytest.mark.asyncio
    async def test_none_confidence_is_lower_than_numeric_confidence(self) -> None:
        """Treat missing confidence as lower than any numeric confidence."""
        primary = _FakeAdapter(provider="ko", text="비타민", confidence=None)
        secondary = _FakeAdapter(provider="en", text="Vitamin", confidence=0.0)
        adapter = MultilingualOCRAdapter(primary=primary, secondary=secondary)

        result = await adapter.extract_text(_image())

        assert result.provider == "en"


class TestOneSideFails:
    """Only one adapter fails."""

    @pytest.mark.asyncio
    async def test_primary_fails_returns_secondary(self) -> None:
        """Return secondary result when primary raises."""
        primary = _FakeAdapter(provider="ko", raises=OCRError("boom"))
        secondary = _FakeAdapter(provider="en", text="Vitamin C", confidence=0.8)
        adapter = MultilingualOCRAdapter(primary=primary, secondary=secondary)

        result = await adapter.extract_text(_image())

        assert result.text == "Vitamin C"
        assert result.provider == "en"

    @pytest.mark.asyncio
    async def test_secondary_fails_returns_primary(self) -> None:
        """Return primary result when secondary raises."""
        primary = _FakeAdapter(provider="ko", text="비타민 C", confidence=0.8)
        secondary = _FakeAdapter(provider="en", raises=OCRError("boom"))
        adapter = MultilingualOCRAdapter(primary=primary, secondary=secondary)

        result = await adapter.extract_text(_image())

        assert result.text == "비타민 C"
        assert result.provider == "ko"


class TestBothFail:
    """Both adapters fail."""

    @pytest.mark.asyncio
    async def test_both_fail_with_ocr_error_raises(self) -> None:
        """Re-raise primary OCR errors when both adapters fail."""
        primary = _FakeAdapter(provider="ko", raises=OCRError("boom"))
        secondary = _FakeAdapter(provider="en", raises=OCRError("boom"))
        adapter = MultilingualOCRAdapter(primary=primary, secondary=secondary)

        with pytest.raises(OCRError):
            await adapter.extract_text(_image())

    @pytest.mark.asyncio
    async def test_both_fail_with_generic_exception_wraps_to_ocr_error(self) -> None:
        """Wrap non-OCR exceptions in the package-standard OCR error."""
        primary = _FakeAdapter(provider="ko", raises=RuntimeError("unknown"))
        secondary = _FakeAdapter(provider="en", raises=RuntimeError("unknown"))
        adapter = MultilingualOCRAdapter(primary=primary, secondary=secondary)

        with pytest.raises(OCRError, match="Both multilingual OCR adapters failed"):
            await adapter.extract_text(_image())


class TestParallelExecution:
    """Both adapters are called for one image."""

    @pytest.mark.asyncio
    async def test_both_adapters_called_once(self) -> None:
        """Call each adapter exactly once for one input image."""
        primary = _FakeAdapter(provider="ko", confidence=0.5)
        secondary = _FakeAdapter(provider="en", confidence=0.5)
        adapter = MultilingualOCRAdapter(primary=primary, secondary=secondary)

        await adapter.extract_text(_image())

        assert primary.call_count == 1
        assert secondary.call_count == 1
