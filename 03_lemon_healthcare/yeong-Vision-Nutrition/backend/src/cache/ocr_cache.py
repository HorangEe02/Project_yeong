"""OCR 결과 Redis 캐시.

이미지 SHA-256 해시를 키로 사용하여 동일 이미지 재처리를 방지한다. TTL은
``Settings.image_retention_history_days`` 에서 가져온다 (docs/17 §3 항목 2).

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-01-ocr-pipeline.md Step 5
    docs/dev-guides/07-ocr-pipeline.md §6
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Final

import redis.asyncio as redis

from src.ocr.base import OCRResult

logger = logging.getLogger(__name__)

CACHE_PREFIX: Final[str] = "ocr:"


def hash_image(image_bytes: bytes) -> str:
    """이미지의 SHA-256 해시.

    Args:
        image_bytes: 이미지 바이트.

    Returns:
        64자 16진수 SHA-256 다이제스트.

    Examples:
        >>> hash_image(b"")
        'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
    """
    return hashlib.sha256(image_bytes).hexdigest()


class OCRCache:
    """Redis 기반 OCR 결과 캐시.

    이미지 해시 → ``OCRResult`` JSON 매핑. TTL 만료 시 자동 폐기.
    """

    def __init__(self, redis_client: redis.Redis[bytes], ttl_seconds: int) -> None:
        """캐시 초기화.

        Args:
            redis_client: ``redis.asyncio.Redis`` 클라이언트 (또는 호환 fake).
            ttl_seconds: 캐시 TTL (초). ``Settings.image_retention_history_days * 86400``
                값을 호출처에서 전달한다.

        Raises:
            ValueError: ``ttl_seconds`` 가 양수가 아닌 경우.
        """
        if ttl_seconds <= 0:
            raise ValueError(f"ttl_seconds must be positive, got {ttl_seconds}")
        self._redis = redis_client
        self._ttl = ttl_seconds

    async def get(self, image_bytes: bytes) -> OCRResult | None:
        """캐시 조회.

        Args:
            image_bytes: 원본 이미지 바이트.

        Returns:
            캐시된 ``OCRResult`` 또는 ``None``.
        """
        key = f"{CACHE_PREFIX}{hash_image(image_bytes)}"
        cached = await self._redis.get(key)
        if cached is None:
            return None
        try:
            data: dict[str, Any] = json.loads(cached)
            return OCRResult(
                text=data["text"],
                confidence=data["confidence"],
                engine=data["engine"],
                words=data.get("words", []),
                elapsed_ms=data.get("elapsed_ms", 0.0),
            )
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("Failed to deserialize cache entry: %s", exc)
            return None

    async def set(self, image_bytes: bytes, result: OCRResult) -> None:
        """캐시 저장.

        Args:
            image_bytes: 원본 이미지 바이트.
            result: 저장할 ``OCRResult``.
        """
        key = f"{CACHE_PREFIX}{hash_image(image_bytes)}"
        payload = {
            "text": result.text,
            "confidence": result.confidence,
            "engine": result.engine,
            "words": result.words,
            "elapsed_ms": result.elapsed_ms,
        }
        await self._redis.setex(
            key,
            self._ttl,
            json.dumps(payload, ensure_ascii=False),
        )
