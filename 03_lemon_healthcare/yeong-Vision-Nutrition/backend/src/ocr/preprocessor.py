"""OCR 전처리 — 보안 게이트 포함.

처리 순서:
    1. 빈 바이트 차단.
    2. magic-byte 헤더 sniff — S3 ① MIME 위조 차단.
       libmagic 시스템 의존을 회피하기 위해 자체 헤더 비교로 구현. 트랙 B 범위
       (JPEG/PNG 2종)에서 충분하다.
    3. ``Pillow.verify`` + ``MAX_IMAGE_PIXELS`` 제한 — S3 ② decompression bomb 차단.
    4. EXIF 회전 보정 → metadata 전체 제거 — S3 ③ EXIF GPS·시리얼·이름 strip.
    5. RGB 변환 + 크기 검증 + 리사이즈.
    6. JPEG q=85 인코딩 + 5MB 상한 추가 다운스케일.

알려진 한계 (TODO[track-c]):
    라벨에 우연히 포함된 사용자 손글씨/얼굴 자동 모자이크는 미구현. docs/17 §4.1
    요구사항이며, Vision 기반 후처리로 트랙 C에서 다룬다. 트랙 B 사용자에게는
    Phase 05 disclaimer를 통해 "사진에 사용자 얼굴/손글씨가 포함되지 않도록 촬영
    하세요" 안내가 추가된다.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-01-ocr-pipeline.md Step 3
    /Users/yeong/.claude/plans/ocr-yolo-sprightly-neumann.md §3.2 S3
    docs/17-image-collection-consent-plan.md §4.1
"""

from __future__ import annotations

import io
import logging
from typing import Final

from PIL import Image, ImageOps

from src.ocr.exceptions import OCRImageError, OCRSecurityError

logger = logging.getLogger(__name__)

MAX_IMAGE_PIXELS: Final[int] = 50_000_000
"""Pillow 기본(178,956,970)보다 보수적인 decompression bomb 상한."""

MAX_DIMENSION: Final[int] = 2048
"""OCR API에 보낼 이미지의 최대 변 길이 (px)."""

MIN_DIMENSION: Final[int] = 200
"""유효한 영양제 라벨 사진의 최소 변 길이 (px)."""

MAX_FILE_SIZE_BYTES: Final[int] = 5 * 1024 * 1024
"""OCR API 페이로드 상한 (5 MB)."""

HEADER_SNIFF_BYTES: Final[int] = 16
"""``sniff_image_mime`` 가 검사할 헤더 길이."""

_JPEG_SIGNATURE: Final[bytes] = b"\xff\xd8\xff"
_PNG_SIGNATURE: Final[bytes] = b"\x89PNG\r\n\x1a\n"

Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


def sniff_image_mime(image_bytes: bytes) -> str | None:
    """첫 16 바이트로 MIME을 판별한다.

    트랙 B는 ``image/jpeg``, ``image/png`` 만 허용하므로 두 시그니처만 검사한다.
    libmagic / ``python-magic`` 외부 의존 없이 동작한다.

    Args:
        image_bytes: 검사할 이미지 바이트.

    Returns:
        ``"image/jpeg"`` | ``"image/png"`` 또는 일치하지 않으면 ``None``.

    Examples:
        >>> sniff_image_mime(b"\\xff\\xd8\\xff\\xe0\\x00\\x10JFIF")
        'image/jpeg'
        >>> sniff_image_mime(b"\\x89PNG\\r\\n\\x1a\\n\\x00\\x00\\x00\\rIHDR")
        'image/png'
        >>> sniff_image_mime(b"PK\\x03\\x04")  # ZIP polyglot 위조
        >>>
    """
    head = image_bytes[:HEADER_SNIFF_BYTES]
    if head.startswith(_JPEG_SIGNATURE):
        return "image/jpeg"
    if head.startswith(_PNG_SIGNATURE):
        return "image/png"
    return None


def preprocess_image(image_bytes: bytes) -> bytes:
    """OCR 정확도와 보안을 위한 전처리.

    Args:
        image_bytes: 원본 이미지 바이트.

    Returns:
        전처리된 JPEG 바이트 (RGB, 최대 ``MAX_DIMENSION`` 변 길이, ``MAX_FILE_SIZE_BYTES`` 이하).

    Raises:
        OCRImageError: 이미지 형식·크기 문제.
        OCRSecurityError: S3 보안 게이트 위반 (MIME 위조 / decompression bomb).
    """
    if not image_bytes:
        raise OCRImageError("Empty image bytes")

    # S3 ① MIME 위조 차단
    sniffed = sniff_image_mime(image_bytes)
    if sniffed is None:
        raise OCRSecurityError("Unrecognized image header (expected JPEG/PNG magic bytes)")

    # S3 ② decompression bomb 차단 — verify는 헤더만 확인
    try:
        with Image.open(io.BytesIO(image_bytes)) as probe:
            probe.verify()
    except Image.DecompressionBombError as exc:
        raise OCRSecurityError(f"Image exceeds MAX_IMAGE_PIXELS={MAX_IMAGE_PIXELS}") from exc
    except (OSError, SyntaxError, ValueError) as exc:
        raise OCRImageError(f"Cannot open image: {exc}") from exc

    # verify는 fp를 닫으므로 다시 연다 — 실제 픽셀 디코드
    img: Image.Image
    try:
        opened = Image.open(io.BytesIO(image_bytes))
        opened.load()
        img = opened
    except Image.DecompressionBombError as exc:
        raise OCRSecurityError(f"Image exceeds MAX_IMAGE_PIXELS={MAX_IMAGE_PIXELS}") from exc
    except (OSError, SyntaxError, ValueError) as exc:
        raise OCRImageError(f"Cannot decode image: {exc}") from exc

    transposed = ImageOps.exif_transpose(img)
    if transposed is not None:
        img = transposed

    # S3 ③ EXIF metadata 전체 제거 — convert만으로는 EXIF가 남을 수 있어 빈 이미지에 paste
    if img.mode != "RGB":
        img = img.convert("RGB")
    cleaned = Image.new("RGB", img.size)
    cleaned.paste(img)
    img = cleaned

    width, height = img.size
    if width < MIN_DIMENSION or height < MIN_DIMENSION:
        raise OCRImageError(
            f"Image too small: {width}x{height} (min {MIN_DIMENSION}x{MIN_DIMENSION})"
        )

    if max(width, height) > MAX_DIMENSION:
        ratio = MAX_DIMENSION / max(width, height)
        new_size = (int(width * ratio), int(height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        logger.info(
            "Resized image",
            extra={"orig_size": (width, height), "new_size": new_size},
        )

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85, optimize=True)
    result = out.getvalue()

    if len(result) > MAX_FILE_SIZE_BYTES:
        scale = (MAX_FILE_SIZE_BYTES / len(result)) ** 0.5
        scaled = img.resize(
            (int(img.width * scale), int(img.height * scale)),
            Image.Resampling.LANCZOS,
        )
        out = io.BytesIO()
        scaled.save(out, format="JPEG", quality=80, optimize=True)
        result = out.getvalue()

    return result
