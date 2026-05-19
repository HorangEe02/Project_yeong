"""PaddleOCR (host-local) 구현 — 외부 cloud OCR 없이 동작하는 ``OCRAdapter``.

PaddleOCR v3.5+ 의 ``PaddleOCR`` pipeline 을 [OCRAdapter] ABC 에 adapt.
sync ``predict()`` 를 ``loop.run_in_executor`` 로 wrap 해 백엔드 async 인터페이스
유지. 모델은 첫 호출 시 ``~/.paddleocr/`` 에 자동 다운로드 (한국어 약 500MB).

Reference:
    /Users/yeong/.claude/plans/mossy-forging-hejlsberg.md §Phase M-3-V
    /Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/PaddleOCR-main/paddleocr/_pipelines/ocr.py
    docs/dev-guides/07-ocr-pipeline.md §4
"""

from __future__ import annotations

import asyncio
import io
import logging
import time
from typing import Any, Final

from src.ocr.base import OCRAdapter, OCRResult
from src.ocr.exceptions import OCRApiError, OCRTimeoutError

logger = logging.getLogger(__name__)

DEFAULT_LANG: Final[str] = "korean"
DEFAULT_TIMEOUT_SEC: Final[float] = 30.0
"""한국어 모델 첫 inference 가 cold start 시 5-10s 소요 — warmup 후 1-2s."""


class PaddleOCRAdapter(OCRAdapter):
    """PaddleOCR v3.5+ 기반 host-local OCR adapter.

    Google Cloud Vision 같은 외부 API 의존성이 없다 — 모델은 host 의
    ``~/.paddleocr/`` 에 자동 다운로드되며 macOS Apple Silicon native 추론을
    지원한다. 트랙 B 의 OCRAdapter 인터페이스를 그대로 구현하므로
    ``deps.get_ocr_pipeline`` 에서 settings 분기로 plug-in.
    """

    def __init__(
        self,
        lang: str = DEFAULT_LANG,
        timeout_sec: float = DEFAULT_TIMEOUT_SEC,
    ) -> None:
        """PaddleOCR pipeline 초기화 (첫 호출 시 모델 다운로드 트리거).

        Args:
            lang: PaddleOCR 언어 코드 — 한국어는 ``"korean"``, 영어는 ``"en"``.
            timeout_sec: 단일 inference 의 wall-clock timeout.
        """
        # paddleocr / paddlepaddle 은 무거운 의존성이므로 lazy import — 다른 OCR
        # provider (google_vision) 만 쓰는 환경은 paddleocr 미설치여도 동작.
        from paddleocr import PaddleOCR  # noqa: PLC0415

        self._lang = lang
        self._timeout_sec = timeout_sec
        self._ocr = PaddleOCR(lang=lang)
        logger.info(
            "PaddleOCRAdapter initialized",
            extra={"lang": lang, "timeout_sec": timeout_sec},
        )

    @property
    def engine_name(self) -> str:
        """``"paddleocr_v3_<lang>"`` — 응답의 ``ocr_engine`` 필드에 그대로 노출."""
        return f"paddleocr_v3_{self._lang}"

    async def extract_text(self, image_bytes: bytes) -> OCRResult:
        """이미지 바이트에서 텍스트 추출.

        Args:
            image_bytes: 전처리된 JPEG/PNG 바이트.

        Returns:
            ``OCRResult`` — text/confidence/words.

        Raises:
            OCRApiError: image 디코드 실패 또는 PaddleOCR 내부 오류.
            OCRTimeoutError: ``timeout_sec`` 초과.
        """
        start = time.perf_counter()

        # PaddleOCR.predict 는 file path / URL / np.ndarray 를 받는다 — bytes 직접 X.
        # PIL 로 디코드 후 numpy array 변환 (RGB 강제 — paddle 입력 형식).
        try:
            from PIL import Image  # noqa: PLC0415
            import numpy as np  # noqa: PLC0415

            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            arr = np.array(img)
        except Exception as exc:  # noqa: BLE001 — PIL 의 다양한 디코드 에러 통합
            raise OCRApiError(self.engine_name, f"image decode failed: {exc}") from exc

        loop = asyncio.get_running_loop()
        try:
            raw = await asyncio.wait_for(
                loop.run_in_executor(None, self._ocr.predict, arr),
                timeout=self._timeout_sec,
            )
        except asyncio.TimeoutError as exc:
            raise OCRTimeoutError(
                f"PaddleOCR timeout after {self._timeout_sec}s"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise OCRApiError(self.engine_name, str(exc)) from exc

        elapsed_ms = (time.perf_counter() - start) * 1000
        text, confidence, words = self._aggregate(raw)

        logger.info(
            "PaddleOCR completed",
            extra={
                "elapsed_ms": elapsed_ms,
                "confidence": confidence,
                "word_count": len(words),
                "engine": self.engine_name,
            },
        )

        return OCRResult(
            text=text,
            confidence=confidence,
            engine=self.engine_name,
            words=words,
            elapsed_ms=elapsed_ms,
        )

    @staticmethod
    def _aggregate(raw: Any) -> tuple[str, float, list[dict[str, Any]]]:
        """``PaddleOCR.predict`` 결과를 ``OCRResult`` 필드로 집계.

        v3.5 의 ``predict()`` 반환은 PaddleX result object 의 list (보통 1 image →
        1 result). 각 result 는 dict-like 또는 attribute 둘 다 지원하며 다음 키를
        노출:
            - ``rec_texts``: list[str] — 인식된 텍스트 (line 단위)
            - ``rec_scores``: list[float] — 각 텍스트의 신뢰도

        google_vision 의 ``word`` 형식과 동일하게 ``{"text", "confidence"}`` 로
        정규화.
        """
        if not raw:
            return ("", 0.0, [])

        words: list[dict[str, Any]] = []
        texts: list[str] = []
        scores: list[float] = []

        for result in raw:
            rec_texts = _extract_field(result, "rec_texts") or []
            rec_scores = _extract_field(result, "rec_scores") or []

            for txt, score in zip(rec_texts, rec_scores, strict=False):
                if txt is None:
                    continue
                t = str(txt).strip()
                if not t:
                    continue
                conf = float(score) if score is not None else 0.0
                texts.append(t)
                scores.append(conf)
                words.append({"text": t, "confidence": conf})

        full_text = "\n".join(texts)
        avg_conf = sum(scores) / len(scores) if scores else 0.0
        return (full_text, avg_conf, words)


def _extract_field(result: Any, key: str) -> Any:
    """PaddleX result 가 dict-like (``result[key]``) 또는 attribute (``result.key``)
    둘 다 지원하므로 양쪽 시도. 둘 다 실패 시 ``None``."""
    try:
        return result[key]
    except (TypeError, KeyError, IndexError):
        return getattr(result, key, None)
