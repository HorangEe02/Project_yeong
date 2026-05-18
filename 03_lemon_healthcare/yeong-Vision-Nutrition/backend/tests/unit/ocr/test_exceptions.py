"""OCR 예외 계층 단위 테스트.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-01-ocr-pipeline.md Step 1
"""

from __future__ import annotations

import pytest
from src.ocr.exceptions import (
    OCRApiError,
    OCRError,
    OCRImageError,
    OCRSecurityError,
    OCRTimeoutError,
)


def test_ocr_error_is_exception() -> None:
    """``OCRError`` 는 일반 ``Exception`` 의 하위 클래스."""
    assert issubclass(OCRError, Exception)


def test_ocr_api_error_attaches_engine_name() -> None:
    """``OCRApiError`` 는 ``engine`` 속성을 보존하고 메시지에 엔진명을 포함한다."""
    exc = OCRApiError("google_vision_v1", "Quota exceeded")
    assert exc.engine == "google_vision_v1"
    assert "google_vision_v1" in str(exc)
    assert "Quota exceeded" in str(exc)


def test_ocr_timeout_error_inherits_from_ocr_error() -> None:
    """``OCRTimeoutError`` 는 ``OCRError`` 의 하위 — 호출처 한 곳에서 잡을 수 있게."""
    assert issubclass(OCRTimeoutError, OCRError)


def test_ocr_image_error_inherits_from_ocr_error() -> None:
    """``OCRImageError`` 도 ``OCRError`` 하위."""
    assert issubclass(OCRImageError, OCRError)


def test_ocr_security_error_is_image_error_subclass() -> None:
    """``OCRSecurityError`` 는 ``OCRImageError`` 의 하위 — image 처리 단계에서 잡힘."""
    assert issubclass(OCRSecurityError, OCRImageError)
    assert issubclass(OCRSecurityError, OCRError)


def test_ocr_api_error_is_raisable() -> None:
    """예외를 실제로 ``raise / catch`` 흐름에 사용할 수 있어야 한다."""
    with pytest.raises(OCRApiError):
        raise OCRApiError("engine", "msg")
