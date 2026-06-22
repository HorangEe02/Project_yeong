# dev-guides/07 — OCR 파이프라인 (Cloud Vision + CLOVA 백업)

> **Phase**: 2 | **선행 작업**: [`00-setup-environment.md`](./00-setup-environment.md) | **예상 소요**: 4~5시간

---

## 🎯 작업 목표

영양제 라벨 사진에서 텍스트를 추출하는 OCR 파이프라인을 **Adapter 패턴**으로 구현한다. 주력은 Google Cloud Vision, 백업은 Naver CLOVA OCR. 자동 폴백·캐싱·이미지 전처리 포함.

---

## 📋 산출물

```
backend/
├── src/
│   ├── ocr/
│   │   ├── __init__.py
│   │   ├── base.py              # OCRAdapter ABC + OCRResult DTO
│   │   ├── google_vision.py     # Google Cloud Vision 구현 (주력)
│   │   ├── clova.py             # CLOVA OCR 구현 (백업)
│   │   ├── preprocessor.py      # 이미지 전처리 (PIL)
│   │   ├── pipeline.py          # 폴백 + 캐싱 통합 파이프라인
│   │   └── exceptions.py        # OCRError 등
│   └── cache/
│       └── ocr_cache.py         # Redis 기반 (이미지 해시 키)
└── tests/
    ├── unit/ocr/
    │   ├── test_preprocessor.py
    │   ├── test_google_vision.py    # 모킹
    │   ├── test_clova.py            # 모킹
    │   └── test_pipeline.py         # 폴백 룰 검증
    ├── integration/ocr/
    │   ├── test_real_google_vision.py    # 실제 API (skip if no creds)
    │   └── test_pipeline_with_cache.py
    └── e2e/
        └── test_ocr_e2e.py        # 영양제 샘플 100장 정확도 측정
```

---

## 📐 설계 명세

> 🔍 **출처**: [docs/Nutrition-docs/06-tech-stack.md](../06-tech-stack.md), [docs/Nutrition-docs/09-data-catalog.md §5.1, §5.2](../09-data-catalog.md)

### 아키텍처

```
┌────────────────────────────────────────────────┐
│           OCRPipeline (조정자)                   │
│  - 캐시 조회 → OCR 호출 → 폴백 → 캐시 저장      │
└────────────────────────────────────────────────┘
              │
   ┌──────────┴──────────┐
   ▼                     ▼
┌──────────────┐    ┌──────────────┐
│ OCRAdapter   │    │ OCRCache     │
│ (ABC)        │    │ (Redis)      │
└──────────────┘    └──────────────┘
   │
   ├──── GoogleVisionOCR (주력)
   └──── ClovaOCR (백업)
```

### 폴백 룰

```
1. 이미지 SHA-256 해시 → Redis 조회
2. 캐시 미스 → 주력(Cloud Vision) 호출
3. 신뢰도 ≥ 0.85 → 결과 반환
4. 신뢰도 < 0.85 또는 API 에러 → 백업(CLOVA) 호출
5. 둘 다 실패 → OCRError 발생
6. 성공한 결과를 Redis에 30일 캐싱
```

---

## 🔧 구현 명세

### 1. `src/ocr/exceptions.py`

```python
"""OCR 관련 예외."""

from __future__ import annotations


class OCRError(Exception):
    """OCR 처리 실패의 기본 예외."""


class OCRApiError(OCRError):
    """외부 API 호출 실패."""

    def __init__(self, engine: str, message: str) -> None:
        super().__init__(f"{engine}: {message}")
        self.engine = engine


class OCRTimeoutError(OCRError):
    """OCR API 타임아웃."""


class OCRImageError(OCRError):
    """이미지 자체의 문제 (크기·형식·손상)."""
```

### 2. `src/ocr/base.py` (ABC + DTO)

```python
"""OCR Adapter 추상 인터페이스."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class OCRResult:
    """OCR 결과 컨테이너.

    Attributes:
        text: 추출된 전체 텍스트.
        confidence: 평균 신뢰도 (0.0~1.0).
        engine: 사용된 OCR 엔진 식별자.
        words: 단어 단위 결과 (선택).
        elapsed_ms: 호출 소요 시간 (ms).
    """

    text: str
    confidence: float
    engine: str
    words: list[dict] = field(default_factory=list)
    elapsed_ms: float = 0.0

    @property
    def is_high_confidence(self) -> bool:
        """신뢰도 0.85 이상 여부."""
        return self.confidence >= 0.85


class OCRAdapter(ABC):
    """OCR 엔진의 추상 인터페이스.

    모든 OCR 구현체는 이 클래스를 상속해야 한다.

    Examples:
        >>> ocr: OCRAdapter = GoogleVisionOCR()
        >>> result = await ocr.extract_text(image_bytes)
        >>> if not result.is_high_confidence:
        ...     # 폴백 트리거
        ...     pass
    """

    @abstractmethod
    async def extract_text(self, image_bytes: bytes) -> OCRResult:
        """이미지에서 텍스트를 추출한다.

        Args:
            image_bytes: 이미지 원본 바이트 (JPEG/PNG, 5MB 이하).

        Returns:
            OCRResult.

        Raises:
            OCRApiError: API 호출 실패.
            OCRImageError: 이미지 자체 문제.
            OCRTimeoutError: 타임아웃.
        """
        ...

    @property
    @abstractmethod
    def engine_name(self) -> str:
        """엔진 식별자 (e.g., "google_vision_v1")."""
        ...
```

### 3. `src/ocr/preprocessor.py`

```python
"""이미지 전처리 모듈."""

from __future__ import annotations

import io
import logging
from typing import Final

from PIL import Image, ImageOps

from src.ocr.exceptions import OCRImageError


logger = logging.getLogger(__name__)


MAX_DIMENSION: Final[int] = 2048
"""OCR API에 보낼 이미지의 최대 변 길이."""

MIN_DIMENSION: Final[int] = 200
"""유효한 영양제 라벨 사진의 최소 변 길이."""

MAX_FILE_SIZE_MB: Final[float] = 5.0
"""OCR API의 일반적 상한 (Cloud Vision은 20MB이지만 보수적)."""


def preprocess_image(image_bytes: bytes) -> bytes:
    """OCR 정확도 향상을 위한 이미지 전처리.

    Args:
        image_bytes: 원본 이미지 바이트.

    Returns:
        전처리된 이미지 바이트 (JPEG, RGB).

    Raises:
        OCRImageError: 이미지 형식이 잘못되었거나 크기가 부족한 경우.

    처리 단계:
        1. EXIF 회전 보정 (자동)
        2. RGB 변환 (RGBA·CMYK 정규화)
        3. 너무 크면 max_dimension 이내로 리사이징
        4. JPEG quality=85로 저장 (크기↓, 품질 유지)
    """
    if not image_bytes:
        raise OCRImageError("Empty image bytes")

    try:
        img = Image.open(io.BytesIO(image_bytes))
    except Exception as e:
        raise OCRImageError(f"Cannot open image: {e}") from e

    # 1. EXIF 회전 보정
    img = ImageOps.exif_transpose(img)

    # 2. 크기 검증
    w, h = img.size
    if w < MIN_DIMENSION or h < MIN_DIMENSION:
        raise OCRImageError(
            f"Image too small: {w}x{h} (min {MIN_DIMENSION}x{MIN_DIMENSION})"
        )

    # 3. RGB 변환
    if img.mode != "RGB":
        img = img.convert("RGB")

    # 4. 리사이징 (긴 변 기준)
    if max(w, h) > MAX_DIMENSION:
        ratio = MAX_DIMENSION / max(w, h)
        new_size = (int(w * ratio), int(h * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        logger.info("Resized image: %s → %s", (w, h), new_size)

    # 5. JPEG 인코딩
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85, optimize=True)
    result_bytes = buffer.getvalue()

    size_mb = len(result_bytes) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        # 한 번 더 리사이징
        scale = (MAX_FILE_SIZE_MB / size_mb) ** 0.5
        new_size = (int(img.width * scale), int(img.height * scale))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=80, optimize=True)
        result_bytes = buffer.getvalue()

    return result_bytes
```

### 4. `src/ocr/google_vision.py`

```python
"""Google Cloud Vision OCR 구현."""

from __future__ import annotations

import logging
import time
from typing import Final

from google.api_core.exceptions import GoogleAPIError
from google.cloud import vision

from src.ocr.base import OCRAdapter, OCRResult
from src.ocr.exceptions import OCRApiError, OCRTimeoutError


logger = logging.getLogger(__name__)


CLIENT_TIMEOUT_SEC: Final[float] = 10.0
LANGUAGE_HINTS: Final[list[str]] = ["ko", "en"]


class GoogleVisionOCR(OCRAdapter):
    """Google Cloud Vision API 기반 OCR.

    Reference:
        docs/Nutrition-docs/09-data-catalog.md §5.1
    """

    def __init__(self, client: vision.ImageAnnotatorClient | None = None) -> None:
        """클라이언트 초기화.

        Args:
            client: 의존성 주입용 클라이언트 (테스트에서 모킹).
                    None이면 환경변수 GOOGLE_APPLICATION_CREDENTIALS 사용.
        """
        self._client = client or vision.ImageAnnotatorClient()

    @property
    def engine_name(self) -> str:
        """엔진 식별자."""
        return "google_vision_v1"

    async def extract_text(self, image_bytes: bytes) -> OCRResult:
        """이미지에서 텍스트 추출 (Document Text Detection 모드).

        Args:
            image_bytes: 이미지 바이트.

        Returns:
            OCRResult.

        Raises:
            OCRApiError: API 호출 실패.
            OCRTimeoutError: 타임아웃.
        """
        start = time.perf_counter()

        image = vision.Image(content=image_bytes)
        context = vision.ImageContext(language_hints=LANGUAGE_HINTS)

        try:
            response = self._client.document_text_detection(
                image=image,
                image_context=context,
                timeout=CLIENT_TIMEOUT_SEC,
            )
        except GoogleAPIError as e:
            raise OCRApiError(self.engine_name, str(e)) from e

        if response.error.message:
            raise OCRApiError(self.engine_name, response.error.message)

        elapsed_ms = (time.perf_counter() - start) * 1000

        # 신뢰도: 페이지별 confidence의 평균
        full = response.full_text_annotation
        if not full or not full.pages:
            return OCRResult(
                text="",
                confidence=0.0,
                engine=self.engine_name,
                elapsed_ms=elapsed_ms,
            )

        page_confs = [p.confidence for p in full.pages if p.confidence > 0]
        avg_conf = sum(page_confs) / len(page_confs) if page_confs else 0.0

        # 단어 단위 (선택)
        words: list[dict] = []
        for page in full.pages:
            for block in page.blocks:
                for paragraph in block.paragraphs:
                    for word in paragraph.words:
                        word_text = "".join(s.text for s in word.symbols)
                        words.append({
                            "text": word_text,
                            "confidence": word.confidence,
                        })

        logger.info(
            "Cloud Vision OCR: %.0fms, conf=%.2f, %d words",
            elapsed_ms, avg_conf, len(words),
        )

        return OCRResult(
            text=full.text,
            confidence=avg_conf,
            engine=self.engine_name,
            words=words,
            elapsed_ms=elapsed_ms,
        )
```

### 5. `src/ocr/clova.py` (백업)

```python
"""Naver CLOVA OCR 구현 (백업)."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Final

import httpx

from src.ocr.base import OCRAdapter, OCRResult
from src.ocr.exceptions import OCRApiError, OCRTimeoutError


logger = logging.getLogger(__name__)


CLOVA_TIMEOUT_SEC: Final[float] = 15.0


class ClovaOCR(OCRAdapter):
    """Naver CLOVA OCR 기반 (백업 OCR).

    Reference:
        docs/Nutrition-docs/09-data-catalog.md §5.2
    """

    def __init__(self, api_url: str, secret_key: str) -> None:
        """클라이언트 초기화.

        Args:
            api_url: CLOVA OCR API 엔드포인트.
            secret_key: API 시크릿 키.
        """
        self._api_url = api_url
        self._secret_key = secret_key

    @property
    def engine_name(self) -> str:
        """엔진 식별자."""
        return "clova_general_v1"

    async def extract_text(self, image_bytes: bytes) -> OCRResult:
        """CLOVA OCR로 텍스트 추출.

        Args:
            image_bytes: 이미지 바이트.

        Returns:
            OCRResult.

        Raises:
            OCRApiError: API 호출 실패.
            OCRTimeoutError: 타임아웃.
        """
        start = time.perf_counter()

        request_json = {
            "version": "V2",
            "requestId": str(uuid.uuid4()),
            "timestamp": int(time.time() * 1000),
            "lang": "ko",
            "images": [
                {
                    "format": "jpg",
                    "name": "supplement",
                }
            ],
        }

        files = {
            "message": (None, str(request_json), "application/json"),
            "file": ("image.jpg", image_bytes, "image/jpeg"),
        }
        headers = {"X-OCR-SECRET": self._secret_key}

        try:
            async with httpx.AsyncClient(timeout=CLOVA_TIMEOUT_SEC) as client:
                response = await client.post(
                    self._api_url, headers=headers, files=files
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as e:
            raise OCRTimeoutError(f"CLOVA timeout: {e}") from e
        except httpx.HTTPError as e:
            raise OCRApiError(self.engine_name, str(e)) from e

        elapsed_ms = (time.perf_counter() - start) * 1000

        # 응답 파싱
        if not data.get("images"):
            raise OCRApiError(self.engine_name, "No images in response")

        image_result = data["images"][0]
        if image_result.get("inferResult") != "SUCCESS":
            raise OCRApiError(
                self.engine_name,
                image_result.get("message", "Unknown error"),
            )

        fields = image_result.get("fields", [])
        text_parts = [f["inferText"] for f in fields]
        full_text = "\n".join(text_parts)

        confs = [f.get("inferConfidence", 0.0) for f in fields]
        avg_conf = sum(confs) / len(confs) if confs else 0.0

        words = [
            {
                "text": f["inferText"],
                "confidence": f.get("inferConfidence", 0.0),
            }
            for f in fields
        ]

        logger.info(
            "CLOVA OCR: %.0fms, conf=%.2f, %d fields",
            elapsed_ms, avg_conf, len(fields),
        )

        return OCRResult(
            text=full_text,
            confidence=avg_conf,
            engine=self.engine_name,
            words=words,
            elapsed_ms=elapsed_ms,
        )
```

### 6. `src/cache/ocr_cache.py`

```python
"""OCR 결과 Redis 캐시."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Final

import redis.asyncio as redis

from src.ocr.base import OCRResult


logger = logging.getLogger(__name__)


CACHE_TTL_SEC: Final[int] = 60 * 60 * 24 * 30  # 30일
CACHE_PREFIX: Final[str] = "ocr:"


def _hash_image(image_bytes: bytes) -> str:
    """이미지의 SHA-256 해시.

    Args:
        image_bytes: 이미지 바이트.

    Returns:
        16진수 해시 문자열.
    """
    return hashlib.sha256(image_bytes).hexdigest()


class OCRCache:
    """Redis 기반 OCR 결과 캐시.

    이미지 해시를 키로 사용하여 동일 이미지 재처리를 방지.
    TTL은 30일.
    """

    def __init__(self, redis_client: redis.Redis) -> None:
        """캐시 초기화.

        Args:
            redis_client: Redis 클라이언트.
        """
        self._redis = redis_client

    async def get(self, image_bytes: bytes) -> OCRResult | None:
        """캐시 조회.

        Args:
            image_bytes: 원본 이미지 바이트.

        Returns:
            캐시된 OCRResult, 없으면 None.
        """
        key = f"{CACHE_PREFIX}{_hash_image(image_bytes)}"
        cached = await self._redis.get(key)
        if cached is None:
            return None
        try:
            data = json.loads(cached)
            return OCRResult(**data)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Failed to deserialize cache entry: %s", e)
            return None

    async def set(self, image_bytes: bytes, result: OCRResult) -> None:
        """캐시 저장.

        Args:
            image_bytes: 원본 이미지 바이트.
            result: 저장할 OCRResult.
        """
        key = f"{CACHE_PREFIX}{_hash_image(image_bytes)}"
        data = {
            "text": result.text,
            "confidence": result.confidence,
            "engine": result.engine,
            "words": result.words,
            "elapsed_ms": result.elapsed_ms,
        }
        await self._redis.setex(key, CACHE_TTL_SEC, json.dumps(data, ensure_ascii=False))
```

### 7. `src/ocr/pipeline.py`

```python
"""OCR 통합 파이프라인 — 캐싱 + 폴백."""

from __future__ import annotations

import logging
from typing import Final

from src.ocr.base import OCRAdapter, OCRResult
from src.ocr.exceptions import OCRApiError, OCRError
from src.ocr.preprocessor import preprocess_image
from src.cache.ocr_cache import OCRCache


logger = logging.getLogger(__name__)


CONFIDENCE_FALLBACK_THRESHOLD: Final[float] = 0.85
"""신뢰도가 이 값 미만이면 백업 OCR로 폴백."""


class OCRPipeline:
    """OCR 파이프라인 — 전처리 + 캐싱 + 폴백.

    동작 흐름:
        1. 이미지 전처리 (회전·리사이징·JPEG 인코딩)
        2. 캐시 조회 (이미지 해시)
        3. 캐시 미스 → 주력 OCR 호출
        4. 신뢰도 < threshold → 백업 OCR 폴백
        5. 결과 캐싱
    """

    def __init__(
        self,
        primary: OCRAdapter,
        fallback: OCRAdapter | None,
        cache: OCRCache | None = None,
    ) -> None:
        """파이프라인 초기화.

        Args:
            primary: 주력 OCR Adapter (Google Cloud Vision).
            fallback: 백업 OCR Adapter (CLOVA). None이면 폴백 X.
            cache: OCR 결과 캐시 (Redis). None이면 캐시 X.
        """
        self._primary = primary
        self._fallback = fallback
        self._cache = cache

    async def extract(self, image_bytes: bytes) -> OCRResult:
        """파이프라인 실행.

        Args:
            image_bytes: 원본 이미지 바이트.

        Returns:
            OCRResult — 주력 또는 폴백 결과.

        Raises:
            OCRError: 모든 OCR 엔진이 실패한 경우.
        """
        # 1. 전처리
        processed = preprocess_image(image_bytes)

        # 2. 캐시 조회 (전처리된 이미지 해시 기준)
        if self._cache:
            cached = await self._cache.get(processed)
            if cached:
                logger.info("OCR cache hit (engine=%s)", cached.engine)
                return cached

        # 3. 주력 OCR
        primary_result: OCRResult | None = None
        try:
            primary_result = await self._primary.extract_text(processed)
            logger.info(
                "Primary OCR: conf=%.2f", primary_result.confidence,
            )
        except OCRApiError as e:
            logger.warning("Primary OCR failed: %s", e)

        # 4. 폴백 판단
        should_fallback = (
            primary_result is None
            or primary_result.confidence < CONFIDENCE_FALLBACK_THRESHOLD
        )

        result: OCRResult
        if should_fallback and self._fallback:
            try:
                fallback_result = await self._fallback.extract_text(processed)
                logger.info(
                    "Fallback OCR: conf=%.2f", fallback_result.confidence,
                )
                # 더 높은 신뢰도 선택
                if (
                    primary_result is None
                    or fallback_result.confidence > primary_result.confidence
                ):
                    result = fallback_result
                else:
                    result = primary_result
            except OCRApiError as e:
                logger.warning("Fallback OCR also failed: %s", e)
                if primary_result is None:
                    raise OCRError("All OCR engines failed") from e
                result = primary_result
        elif primary_result is None:
            raise OCRError("Primary OCR failed and no fallback configured")
        else:
            result = primary_result

        # 5. 캐싱
        if self._cache:
            await self._cache.set(processed, result)

        return result
```

---

## 🧪 테스트 (4-Tier)

### Tier 1: 단위 테스트

#### `test_preprocessor.py`

| 테스트 | 검증 |
|-------|------|
| `test_empty_bytes_raises` | OCRImageError |
| `test_invalid_format_raises` | 잘못된 바이트 → OCRImageError |
| `test_too_small_raises` | 100x100 → OCRImageError |
| `test_rgba_to_rgb` | PNG (RGBA) → JPEG (RGB) |
| `test_resize_large` | 4000x3000 → 2048x1536 |
| `test_exif_rotation_applied` | EXIF Orientation=6 → 90° 회전 |
| `test_output_under_5mb` | 큰 이미지 → 5MB 이내 |

#### `test_google_vision.py` (모킹)

```python
"""GoogleVisionOCR 단위 테스트 (실제 API 호출 X)."""

import pytest
from unittest.mock import MagicMock

from src.ocr.google_vision import GoogleVisionOCR
from src.ocr.exceptions import OCRApiError


def make_mock_response(text: str, confidence: float = 0.9):
    """Cloud Vision 응답 모킹."""
    response = MagicMock()
    response.error.message = ""
    response.full_text_annotation.text = text
    response.full_text_annotation.pages = [
        MagicMock(confidence=confidence, blocks=[]),
    ]
    return response


class TestGoogleVisionOCR:
    @pytest.mark.asyncio
    async def test_extract_text_success(self) -> None:
        client = MagicMock()
        client.document_text_detection.return_value = make_mock_response(
            "비타민C 1000mg", confidence=0.95
        )
        ocr = GoogleVisionOCR(client=client)

        result = await ocr.extract_text(b"fake")
        assert result.text == "비타민C 1000mg"
        assert result.confidence == 0.95
        assert result.engine == "google_vision_v1"
        assert result.is_high_confidence

    @pytest.mark.asyncio
    async def test_api_error_raises(self) -> None:
        client = MagicMock()
        response = MagicMock()
        response.error.message = "Quota exceeded"
        client.document_text_detection.return_value = response
        ocr = GoogleVisionOCR(client=client)

        with pytest.raises(OCRApiError):
            await ocr.extract_text(b"fake")

    @pytest.mark.asyncio
    async def test_empty_response_returns_zero_conf(self) -> None:
        client = MagicMock()
        response = MagicMock()
        response.error.message = ""
        response.full_text_annotation = None
        client.document_text_detection.return_value = response
        ocr = GoogleVisionOCR(client=client)

        result = await ocr.extract_text(b"fake")
        assert result.confidence == 0.0
        assert not result.is_high_confidence
```

#### `test_pipeline.py`

| 테스트 | 검증 |
|-------|------|
| `test_high_conf_no_fallback` | 주력 0.95 → 폴백 호출 X |
| `test_low_conf_triggers_fallback` | 주력 0.5 → 폴백 호출 |
| `test_fallback_better_returned` | 주력 0.5, 폴백 0.9 → 폴백 결과 반환 |
| `test_primary_error_fallback_called` | 주력 예외 → 폴백 호출 |
| `test_all_failed_raises` | 둘 다 실패 → OCRError |
| `test_cache_hit_skips_apis` | 캐시에 있음 → 주력 호출 X |
| `test_cache_miss_calls_primary` | 캐시 미스 → 주력 호출 + 캐시 저장 |
| `test_no_fallback_configured` | fallback=None → 주력만 |

### Tier 2: 통합 테스트

```python
"""OCRPipeline + Redis 통합."""

@pytest.mark.asyncio
async def test_pipeline_with_real_redis(redis_client):
    """실제 Redis (Docker)와 통합."""
    cache = OCRCache(redis_client)
    pipeline = OCRPipeline(
        primary=MockOCR("text", 0.9),
        fallback=None,
        cache=cache,
    )
    result1 = await pipeline.extract(SAMPLE_IMAGE)
    result2 = await pipeline.extract(SAMPLE_IMAGE)

    # 두 번째는 캐시 hit
    assert result2.text == result1.text
    # 주력은 1회만 호출됨 (call counter)
```

### Tier 3: 실 API 통합 테스트 (선택)

```python
"""실제 Google Cloud Vision 호출.

조건:
    - GOOGLE_APPLICATION_CREDENTIALS 환경변수 필요
    - 실행 시 비용 발생 (1,000건 후 $1.5/1k)
"""

import pytest
import os


@pytest.mark.skipif(
    not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
    reason="No GCP credentials"
)
@pytest.mark.integration
class TestGoogleVisionReal:
    @pytest.mark.asyncio
    async def test_real_supplement_label(self):
        """실제 영양제 라벨 사진 OCR."""
        with open("tests/fixtures/sample_supplement.jpg", "rb") as f:
            image = f.read()

        ocr = GoogleVisionOCR()
        result = await ocr.extract_text(image)

        assert result.confidence > 0.8
        assert "비타민" in result.text or "Vitamin" in result.text
```

### Tier 4: E2E 정확도 테스트

```python
"""영양제 100장 정확도 측정."""

import json
from pathlib import Path

import pytest


@pytest.mark.e2e
class TestOCRAccuracy:
    """100장 영양제 라벨 정확도 측정.

    조건:
        - tests/fixtures/supplement_labels/ 에 100장 + ground_truth.json
        - 실제 API 호출 (비용 ~$0.15)
    """

    @pytest.fixture(scope="class")
    def labels_dir(self) -> Path:
        return Path("tests/fixtures/supplement_labels")

    @pytest.fixture(scope="class")
    def ground_truth(self, labels_dir: Path) -> dict:
        with open(labels_dir / "ground_truth.json") as f:
            return json.load(f)

    @pytest.mark.asyncio
    async def test_accuracy_above_85(self, labels_dir, ground_truth):
        """평균 정확도 ≥ 85% 달성."""
        ocr = GoogleVisionOCR()
        correct = 0
        total = 0

        for image_file, expected in ground_truth.items():
            with open(labels_dir / image_file, "rb") as f:
                image = f.read()
            result = await ocr.extract_text(image)
            # 핵심 키워드 매칭
            if all(kw in result.text for kw in expected["keywords"]):
                correct += 1
            total += 1

        accuracy = correct / total if total else 0
        print(f"Accuracy: {accuracy:.2%} ({correct}/{total})")
        assert accuracy >= 0.85
```

### 성능 테스트

```python
"""OCR 응답 시간 검증."""

@pytest.mark.performance
class TestOCRPerformance:
    @pytest.mark.asyncio
    async def test_pipeline_under_3s(self):
        """전체 파이프라인 (캐시 미스) < 3초."""
        pipeline = OCRPipeline(
            primary=GoogleVisionOCR(),
            fallback=None,
            cache=None,
        )

        start = time.perf_counter()
        await pipeline.extract(SAMPLE_IMAGE)
        elapsed = time.perf_counter() - start

        assert elapsed < 3.0

    @pytest.mark.asyncio
    async def test_cache_hit_under_50ms(self, cache):
        """캐시 hit 응답 < 50ms."""
        pipeline = OCRPipeline(
            primary=MockOCR("text", 0.9),
            fallback=None,
            cache=cache,
        )
        # 첫 호출 (캐시 저장)
        await pipeline.extract(SAMPLE_IMAGE)

        # 두 번째 호출 (캐시 hit)
        start = time.perf_counter()
        await pipeline.extract(SAMPLE_IMAGE)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 50
```

---

## ✅ Definition of Done

- [ ] `src/ocr/exceptions.py` — OCRError 계층
- [ ] `src/ocr/base.py` — OCRAdapter ABC + OCRResult
- [ ] `src/ocr/preprocessor.py` — preprocess_image
- [ ] `src/ocr/google_vision.py` — Cloud Vision 구현
- [ ] `src/ocr/clova.py` — CLOVA 백업 구현
- [ ] `src/cache/ocr_cache.py` — Redis 캐싱
- [ ] `src/ocr/pipeline.py` — 통합 파이프라인 (전처리 + 캐싱 + 폴백)
- [ ] 모든 함수 Google-style docstring
- [ ] 모든 함수 타입 힌트
- [ ] 단위 테스트 30+ (전처리, 각 Adapter 모킹, 파이프라인 분기)
- [ ] 통합 테스트 (Redis 통합)
- [ ] (선택) 실 API 통합 테스트 (`@pytest.mark.integration`)
- [ ] (선택) E2E 정확도 테스트 (100장, ≥85%, `@pytest.mark.e2e`)
- [ ] 성능 테스트 (캐시 hit < 50ms, 캐시 미스 < 3초)
- [ ] `mypy src/ocr src/cache --strict` 통과
- [ ] `pytest tests/unit/ocr -v` 통과
- [ ] 코드 커버리지 ≥ 90% (단위 테스트 기준)

---

## 💡 구현 팁

### Adapter 패턴의 가치

```python
# 향후 OCR 엔진 교체 시 한 줄만 수정
pipeline = OCRPipeline(
    primary=GoogleVisionOCR(),  # ← AzureOCR()로 바꾸면 끝
    fallback=ClovaOCR(...),
    cache=cache,
)
```

### 모킹 전략 (단위 테스트)

실제 API 호출 없이 모든 분기를 검증:

```python
class MockOCR(OCRAdapter):
    def __init__(self, text: str, confidence: float):
        self._text = text
        self._confidence = confidence
        self.call_count = 0

    @property
    def engine_name(self) -> str:
        return "mock"

    async def extract_text(self, image_bytes: bytes) -> OCRResult:
        self.call_count += 1
        return OCRResult(text=self._text, confidence=self._confidence, engine="mock")
```

### CLOVA 응답 형식 차이

CLOVA의 응답은 Google Vision과 형식이 다르므로 **Adapter 내에서 정규화**. OCRResult는 두 엔진의 결과를 동일한 형태로 반환.

### 비용 최적화

- **Redis 캐싱 강력 권장** — 동일 이미지 재처리 방지
- **이미지 전처리로 크기 ↓** — 작은 이미지는 응답 빠르고 정확도도 높음
- **신뢰도 임계 0.85** — 너무 높이면 폴백 자주 발동 (CLOVA 비용)

---

## 🚫 이 작업에서 하지 말 것

- ❌ Google Vision SDK 직접 호출 (Adapter 우회)
- ❌ FastAPI 라우터에 OCR 직접 통합 (다음 가이드 09)
- ❌ LLM 파싱 (다음 가이드 08)
- ❌ DB 저장 (다음 가이드 09)

---

## 🔗 관련 문서

- [`/CLAUDE.md`](../../CLAUDE.md)
- [`/backend/CLAUDE.md`](../../backend/CLAUDE.md) (Adapter 패턴)
- [`/docs/Nutrition-docs/06-tech-stack.md`](../06-tech-stack.md)
- [`/docs/Nutrition-docs/09-data-catalog.md §5.1, §5.2`](../09-data-catalog.md)
- 이전: [`06-deficient-nutrient-diagnosis.md`](./06-deficient-nutrient-diagnosis.md)
- 다음: [`08-llm-supplement-parsing.md`](./08-llm-supplement-parsing.md)
