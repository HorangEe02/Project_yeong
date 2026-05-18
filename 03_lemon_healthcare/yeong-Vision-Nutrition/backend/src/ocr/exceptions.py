"""OCR 관련 예외 계층.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-01-ocr-pipeline.md Step 1
    docs/dev-guides/07-ocr-pipeline.md §1
"""

from __future__ import annotations


class OCRError(Exception):
    """OCR 처리 실패의 기본 예외."""


class OCRApiError(OCRError):
    """외부 OCR API 호출 실패 (인증, 쿼터, 네트워크 등)."""

    def __init__(self, engine: str, message: str) -> None:
        """예외 초기화.

        Args:
            engine: 실패한 OCR 엔진 식별자.
            message: 원인 메시지.
        """
        super().__init__(f"{engine}: {message}")
        self.engine = engine


class OCRTimeoutError(OCRError):
    """OCR API 호출 타임아웃."""


class OCRImageError(OCRError):
    """이미지 자체의 문제 (크기·형식·손상)."""


class OCRSecurityError(OCRImageError):
    """S3 보안 게이트 위반 — MIME 위조, decompression bomb 등.

    Reference:
        /Users/yeong/.claude/plans/ocr-yolo-sprightly-neumann.md §3.2 S3
    """
