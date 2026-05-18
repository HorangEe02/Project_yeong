"""``GoogleVisionOCR`` 단위 테스트 — 실제 API 호출 없이 MagicMock 기반.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-01-ocr-pipeline.md Step 4
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from google.api_core import exceptions as gapi_exceptions
from src.ocr.exceptions import OCRApiError, OCRTimeoutError
from src.ocr.google_vision import GoogleVisionOCR


def _make_vision_response(
    text: str,
    confidence: float = 0.9,
    error_message: str = "",
) -> Any:
    """Cloud Vision ``document_text_detection`` 응답 mock."""
    response = MagicMock()
    response.error.message = error_message

    sym = MagicMock()
    sym.text = text

    word = MagicMock()
    word.confidence = confidence
    word.symbols = [sym]

    paragraph = MagicMock()
    paragraph.words = [word]

    block = MagicMock()
    block.paragraphs = [paragraph]

    page = MagicMock()
    page.confidence = confidence
    page.blocks = [block]

    full = MagicMock()
    full.text = text
    full.pages = [page]
    response.full_text_annotation = full
    return response


class TestGoogleVisionOCR:
    """주력 OCR Adapter 분기 검증."""

    @pytest.mark.asyncio
    async def test_extract_text_success(self) -> None:
        client = MagicMock()
        client.document_text_detection.return_value = _make_vision_response(
            "비타민 C 1000mg",
            confidence=0.95,
        )
        ocr = GoogleVisionOCR(client=client)
        result = await ocr.extract_text(b"fake")
        assert result.text == "비타민 C 1000mg"
        assert result.confidence == 0.95
        assert result.engine == "google_vision_v1"
        assert result.is_high_confidence
        assert result.elapsed_ms >= 0
        assert len(result.words) == 1
        assert result.words[0]["text"] == "비타민 C 1000mg"

    @pytest.mark.asyncio
    async def test_response_error_message_raises_ocr_api_error(self) -> None:
        """응답에 ``error.message`` 가 있으면 ``OCRApiError`` 로 변환."""
        client = MagicMock()
        response = MagicMock()
        response.error.message = "Quota exceeded"
        response.full_text_annotation = None
        client.document_text_detection.return_value = response
        ocr = GoogleVisionOCR(client=client)
        with pytest.raises(OCRApiError) as exc_info:
            await ocr.extract_text(b"fake")
        assert "Quota exceeded" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_google_api_error_wrapped_to_ocr_api_error(self) -> None:
        """SDK 예외는 ``OCRApiError`` 로 정규화된다."""
        client = MagicMock()
        client.document_text_detection.side_effect = gapi_exceptions.PermissionDenied("nope")
        ocr = GoogleVisionOCR(client=client)
        with pytest.raises(OCRApiError):
            await ocr.extract_text(b"fake")

    @pytest.mark.asyncio
    async def test_deadline_exceeded_wrapped_to_timeout(self) -> None:
        """타임아웃 SDK 예외는 ``OCRTimeoutError`` 로 변환된다."""
        client = MagicMock()
        client.document_text_detection.side_effect = gapi_exceptions.DeadlineExceeded("slow")
        ocr = GoogleVisionOCR(client=client)
        with pytest.raises(OCRTimeoutError):
            await ocr.extract_text(b"fake")

    @pytest.mark.asyncio
    async def test_empty_response_returns_zero_confidence(self) -> None:
        """``full_text_annotation`` 이 없으면 빈 결과를 반환 (예외 X)."""
        client = MagicMock()
        response = MagicMock()
        response.error.message = ""
        response.full_text_annotation = None
        client.document_text_detection.return_value = response
        ocr = GoogleVisionOCR(client=client)
        result = await ocr.extract_text(b"fake")
        assert result.text == ""
        assert result.confidence == 0.0
        assert not result.is_high_confidence

    def test_engine_name(self) -> None:
        ocr = GoogleVisionOCR(client=MagicMock())
        assert ocr.engine_name == "google_vision_v1"
