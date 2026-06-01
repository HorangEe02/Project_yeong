"""v4.7 Sprint 2 P0 (축 ④) — Vision OCR + 검색 통합.

이미지 바이트 → Gemini Vision API 로 OCR → 추출된 텍스트로 기존 RRF 검색.

외부 의존:
  - GEMINI_API_KEY 환경 변수 — 미설정 시 RuntimeError("vision_disabled") 발생.
  - google-generativeai (genai) SDK — 미설치 또는 호출 실패 시 RuntimeError.

캐싱:
  - 동일 이미지에 대한 반복 호출은 비싼 비용 → in-memory SHA-256 LRU 캐시.
"""

from __future__ import annotations

import hashlib
import logging
import os
from collections import OrderedDict
from typing import Any

logger = logging.getLogger(__name__)

# in-memory OCR 캐시 — 최대 32 항목, LRU.
_OCR_CACHE: "OrderedDict[str, str]" = OrderedDict()
_OCR_CACHE_MAX = 32


def _cache_get(key: str) -> str | None:
    if key in _OCR_CACHE:
        _OCR_CACHE.move_to_end(key)
        return _OCR_CACHE[key]
    return None


def _cache_put(key: str, value: str) -> None:
    _OCR_CACHE[key] = value
    _OCR_CACHE.move_to_end(key)
    while len(_OCR_CACHE) > _OCR_CACHE_MAX:
        _OCR_CACHE.popitem(last=False)


def _gemini_ocr(image_bytes: bytes) -> str:
    """Gemini Vision API 로 이미지에서 텍스트 추출.

    Raises:
        RuntimeError("vision_disabled") — GEMINI_API_KEY 미설정
        RuntimeError("vision_failed") — SDK 미설치 또는 호출 실패
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("vision_disabled")

    try:
        # SDK 가 없는 환경에서도 import error 가 명확하도록.
        import google.generativeai as genai  # type: ignore
    except Exception as e:  # pragma: no cover — 환경 의존
        logger.warning("google-generativeai SDK 미설치: %s", e)
        raise RuntimeError("vision_failed") from e

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-3.5-flash")
        prompt = (
            "Extract all visible text from this image as Korean and/or English. "
            "Do not summarize, paraphrase, or add commentary. "
            "Return ONLY the raw OCR text. If the image is a drawing, also list "
            "any drawing numbers (e.g. KOR-2024-001) on a separate line."
        )
        response = model.generate_content(
            [prompt, {"mime_type": "image/png", "data": image_bytes}]
        )
        text = getattr(response, "text", None) or ""
        return text.strip()
    except Exception as e:  # pragma: no cover — 외부 호출 의존
        logger.warning("Gemini vision OCR 호출 실패: %s", e)
        raise RuntimeError("vision_failed") from e


def vision_search(image_bytes: bytes, searcher: Any | None = None) -> tuple[str, list[dict]]:
    """이미지 → OCR → 검색 통합 진입점.

    Args:
        image_bytes: 원본 이미지 바이트.
        searcher: backend.dependencies.get_searcher() 가 주입한 RRF 검색 객체.
                  None 이면 검색 결과는 빈 리스트로 폴백.

    Returns:
        (ocr_text, search_results_dict_list)

    Raises:
        RuntimeError("vision_disabled") — API key 미설정
        RuntimeError("vision_failed") — Gemini 호출 실패
    """
    if not image_bytes:
        return "", []

    cache_key = hashlib.sha256(image_bytes).hexdigest()
    cached = _cache_get(cache_key)
    if cached is not None:
        ocr_text = cached
    else:
        ocr_text = _gemini_ocr(image_bytes)
        _cache_put(cache_key, ocr_text)

    results: list[dict] = []
    if ocr_text and searcher is not None:
        try:
            # OCR 텍스트는 길 수 있음 — 첫 200자만 query 로 사용.
            query = ocr_text[:200].strip()
            raw = searcher.search(query=query, k=8)
            for r in raw:
                results.append(
                    {
                        "doc_id": getattr(r, "doc_id", ""),
                        "title": getattr(r, "title", ""),
                        "doc_type": getattr(r, "doc_type", ""),
                        "part_name": getattr(r, "part_name", ""),
                        "content": getattr(r, "content", ""),
                        "score": float(getattr(r, "score", 0.0)),
                        "metadata": getattr(r, "metadata", {}) or {},
                    }
                )
        except Exception as e:  # pragma: no cover
            logger.warning("vision_search searcher fallback: %s", e)
            results = []

    return ocr_text, results
