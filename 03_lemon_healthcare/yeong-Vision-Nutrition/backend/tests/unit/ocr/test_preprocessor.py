"""OCR 전처리 단위 테스트 — S3 보안 게이트 4종 모두 포함.

S3 검증 항목 (ocr-yolo-sprightly-neumann.md §3.2 S3):
    ① MIME 위조 차단 (test_zip_polyglot_*, test_text_*)
    ② Decompression bomb 차단 (test_decompression_bomb_*)
    ③ EXIF metadata 전체 제거 (test_exif_metadata_stripped)
    ④ 빈 바이트 / 비정상 입력 거부 (test_empty_*)

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-01-ocr-pipeline.md Step 3
"""

from __future__ import annotations

import io

import pytest
from PIL import ExifTags, Image
from src.ocr.exceptions import OCRImageError, OCRSecurityError
from src.ocr.preprocessor import (
    MAX_DIMENSION,
    MIN_DIMENSION,
    preprocess_image,
    sniff_image_mime,
)


def _make_jpeg(width: int = 400, height: int = 400) -> bytes:
    """전처리 통과 가능한 표준 JPEG 바이트 생성."""
    img = Image.new("RGB", (width, height), color=(128, 64, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def _make_png(width: int = 400, height: int = 400) -> bytes:
    img = Image.new("RGB", (width, height), color=(50, 200, 100))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestSniffImageMime:
    """``sniff_image_mime`` 의 헤더 판별 검증."""

    def test_jpeg_returns_jpeg(self) -> None:
        assert sniff_image_mime(_make_jpeg()) == "image/jpeg"

    def test_png_returns_png(self) -> None:
        assert sniff_image_mime(_make_png()) == "image/png"

    def test_zip_polyglot_returns_none(self) -> None:
        """확장자 위조 / ZIP polyglot 은 ``None``."""
        assert sniff_image_mime(b"PK\x03\x04\x14\x00fake") is None

    def test_plain_text_returns_none(self) -> None:
        assert sniff_image_mime(b"<html>not an image</html>") is None

    def test_empty_returns_none(self) -> None:
        assert sniff_image_mime(b"") is None


class TestPreprocessImageS3Gates:
    """S3 보안 게이트 4종 — 모든 위반은 ``OCRSecurityError`` 또는 ``OCRImageError`` 로 차단."""

    def test_empty_bytes_raises_image_error(self) -> None:
        """S3 ④: 빈 바이트는 ``OCRImageError``."""
        with pytest.raises(OCRImageError):
            preprocess_image(b"")

    def test_zip_polyglot_blocked(self) -> None:
        """S3 ①: ZIP 시작 바이트는 ``OCRSecurityError`` 로 차단."""
        with pytest.raises(OCRSecurityError):
            preprocess_image(b"PK\x03\x04\x14\x00fake zip content")

    def test_text_payload_blocked(self) -> None:
        """S3 ①: 일반 텍스트는 magic header 불일치로 거부."""
        with pytest.raises(OCRSecurityError):
            preprocess_image(b"<html><body>not an image</body></html>")

    def test_decompression_bomb_blocked(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """S3 ②: ``MAX_IMAGE_PIXELS`` 초과 → ``OCRSecurityError``."""
        from PIL import Image as PILImage
        from src.ocr import preprocessor as pp

        monkeypatch.setattr(pp, "MAX_IMAGE_PIXELS", 1000)
        monkeypatch.setattr(PILImage, "MAX_IMAGE_PIXELS", 1000)

        img_bytes = _make_jpeg(400, 400)  # 160,000 pixels > 1000 limit
        with pytest.raises(OCRSecurityError):
            preprocess_image(img_bytes)

    def test_exif_metadata_stripped(self) -> None:
        """S3 ③: 입력 EXIF가 출력 이미지에는 제거되어야 한다."""
        img = Image.new("RGB", (400, 400), color=(80, 80, 80))
        exif = img.getexif()
        exif[ExifTags.Base.Make.value] = "TestCamera"
        exif[ExifTags.Base.Model.value] = "TestModel"
        buf = io.BytesIO()
        img.save(buf, format="JPEG", exif=exif)
        original = buf.getvalue()

        # 원본 이미지에 EXIF가 실제로 들어갔는지 sanity check
        with Image.open(io.BytesIO(original)) as orig:
            assert len(orig.getexif()) > 0

        processed = preprocess_image(original)
        with Image.open(io.BytesIO(processed)) as result:
            assert len(result.getexif()) == 0


class TestPreprocessImageNormal:
    """정상 경로 + 크기 검증."""

    def test_valid_jpeg_passes(self) -> None:
        processed = preprocess_image(_make_jpeg(800, 600))
        assert sniff_image_mime(processed) == "image/jpeg"
        with Image.open(io.BytesIO(processed)) as img:
            assert img.mode == "RGB"
            assert img.size == (800, 600)

    def test_png_input_converted_to_jpeg_output(self) -> None:
        """PNG 입력이라도 출력은 항상 JPEG."""
        processed = preprocess_image(_make_png(400, 400))
        assert sniff_image_mime(processed) == "image/jpeg"

    def test_too_small_raises(self) -> None:
        too_small = _make_jpeg(MIN_DIMENSION - 50, MIN_DIMENSION - 50)
        with pytest.raises(OCRImageError):
            preprocess_image(too_small)

    def test_large_image_resized_within_max_dimension(self) -> None:
        big = _make_jpeg(MAX_DIMENSION + 1000, MAX_DIMENSION + 800)
        processed = preprocess_image(big)
        with Image.open(io.BytesIO(processed)) as img:
            assert max(img.size) <= MAX_DIMENSION
