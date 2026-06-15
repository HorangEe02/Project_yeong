"""LongLLMLingua context compression — Phase 2.

출처: Jiang et al. ACL 2024, arXiv:2310.06839 (LongLLMLingua).
       docs/RAG_ENHANCEMENT_PLAN.md §2.3 + §4 Phase 2 (D+1 = 2026-06-12 시작).

목적:
- RAG 의 KB context + few-shot 예시 + 액션 결과를 LLM 호출 직전에 압축.
- "lost in the middle" 완화 + 토큰 비용 절감 + TTFT 단축.
- 논문 보고치: NaturalQuestions 4× 압축 + 21.4%p 성능 향상,
  LooGLE 비용 94% 감소, 10k 토큰 압축 시 1.4–2.6× latency 개선.

AJIN 통합 정책:
- onboarding.py 의 prompt 합성 직후, Ollama 호출 직전에 적용 (별도 PR — main 의
  onboarding.py 에 load_kb_context 통합 commit 머지 후 wiring).
- 본 PR 은 라이브러리만 제공 — 호출 위치는 onboarding/draft 통합 시 결정.

모델 선택 (RAG_ENHANCEMENT_PLAN.md §2.3 권장):
- `microsoft/llmlingua-2-xlm-roberta-large-meetingbank` (~1.1GB) — 다국어 (한국어 포함)
- 더 가벼운 옵션: `microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank` (~340MB)
- 원논문의 `microsoft/phi-2` (~5GB) 는 Cloud Run 부적합

조건부 활성 (config.LLMLINGUA_*):
- LLMLINGUA_ENABLED=true 일 때만 모델 로드
- 압축 대상 길이가 LLMLINGUA_THRESHOLD_CHARS (기본 2000) 초과 시에만 압축
- 압축률 LLMLINGUA_TARGET_RATIO (기본 0.5)
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CompressionResult:
    """단일 압축 호출 결과.

    Attributes:
        compressed: 압축 후 텍스트. 압축 비활성 또는 임계치 미만 시 원본 반환.
        original_chars: 원본 문자 수.
        compressed_chars: 압축 후 문자 수.
        ratio: compressed_chars / original_chars (0~1).
        compressed_by_lingua: True 면 실제 LLMLingua 모델이 압축. False 면 통과 (no-op).
        elapsed_ms: 압축에 소요된 millisecond. no-op 시 0.
    """

    compressed: str
    original_chars: int
    compressed_chars: int
    ratio: float
    compressed_by_lingua: bool
    elapsed_ms: float


class LLMLinguaCompressor:
    """Microsoft LLMLingua singleton — 한 프로세스에 1개 인스턴스, lazy load."""

    _instance: Optional["LLMLinguaCompressor"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):  # noqa: ANN204
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(self, model_name: str | None = None):
        if self._initialized:
            return
        from config import LLMLINGUA_MODEL

        self.model_name = model_name or LLMLINGUA_MODEL
        self._model = None
        self._model_loaded = False
        self._load_failed = False
        self._initialized = True
        logger.info("LLMLinguaCompressor 인스턴스 생성 (model=%s, lazy)", self.model_name)

    def _ensure_loaded(self) -> bool:
        """모델 lazy 로드. 실패 시 _load_failed=True 로 기록 (재시도 안 함)."""
        if self._model_loaded:
            return True
        if self._load_failed:
            return False

        try:
            from llmlingua import PromptCompressor
        except ImportError as e:
            logger.warning(
                "llmlingua import 실패 — 압축 비활성, 원본 그대로 반환. (%s)",
                e,
            )
            self._load_failed = True
            return False

        try:
            logger.info("LLMLingua 모델 로드 시작: %s", self.model_name)
            import time

            t0 = time.time()
            # LLMLingua-2 사용 (xlm-roberta / bert-multilingual 기반).
            self._model = PromptCompressor(
                model_name=self.model_name,
                use_llmlingua2=True,
            )
            elapsed = time.time() - t0
            self._model_loaded = True
            logger.info("LLMLingua 로드 완료 (%.1fs)", elapsed)
            return True
        except Exception as e:
            logger.exception("LLMLingua 모델 로드 실패: %s", e)
            self._load_failed = True
            return False

    def compress(
        self,
        context: str,
        instruction: str = "",
        rate: float | None = None,
        target_token: int | None = None,
    ) -> str:
        """LLMLingua 압축 호출 — 실패 시 원본 그대로 반환.

        Args:
            context: 압축 대상 텍스트 (KB context + few-shot + action 결과 등).
            instruction: 사용자 질의 (LLMLingua-2 가 질의 보존 가중치에 활용).
            rate: 압축률 (0~1). None 이면 1.0 (변경 없음).
            target_token: 압축 후 목표 토큰 수. rate 와 함께 사용 시 더 강한 조건.

        Returns:
            압축된 텍스트. 모델 로드 실패 또는 압축 실패 시 원본 그대로.
        """
        if not context:
            return context
        if not self._ensure_loaded():
            return context

        kwargs: dict = {"context": context, "instruction": instruction}
        if rate is not None:
            kwargs["rate"] = rate
        if target_token is not None:
            kwargs["target_token"] = target_token

        try:
            result = self._model.compress_prompt(**kwargs)
            if isinstance(result, dict):
                return str(result.get("compressed_prompt") or context)
            return str(result) if result else context
        except Exception as e:
            logger.exception("LLMLingua compress 실패 — 원본 반환. (%s)", e)
            return context


_global_compressor: Optional[LLMLinguaCompressor] = None


def get_compressor() -> LLMLinguaCompressor | None:
    """전역 LLMLinguaCompressor 싱글톤 반환. LLMLINGUA_ENABLED=false 면 None.

    onboarding/draft 흐름에서 호출. None 일 때는 압축 단계 skip.
    """
    global _global_compressor

    try:
        from config import LLMLINGUA_ENABLED
    except ImportError:
        return None

    if not LLMLINGUA_ENABLED:
        logger.info("LLMLINGUA_ENABLED=false — 압축 비활성")
        return None

    if _global_compressor is None:
        _global_compressor = LLMLinguaCompressor()
    return _global_compressor


def maybe_compress_context(
    context: str,
    instruction: str = "",
    threshold_chars: int | None = None,
    target_ratio: float | None = None,
) -> CompressionResult:
    """조건부 압축 — context 길이가 threshold 초과 시에만 LLMLingua 호출.

    Args:
        context: 압축 대상 텍스트.
        instruction: 사용자 질의 (LLMLingua 가 보존 가중치에 활용).
        threshold_chars: 이 길이 미만이면 압축 skip. None 이면 config 값.
        target_ratio: 압축률. None 이면 config 값.

    Returns:
        CompressionResult — compressed / original_chars / compressed_chars / ratio /
        compressed_by_lingua / elapsed_ms.
    """
    import time

    original_chars = len(context)
    if not context:
        return CompressionResult(
            compressed="",
            original_chars=0,
            compressed_chars=0,
            ratio=1.0,
            compressed_by_lingua=False,
            elapsed_ms=0.0,
        )

    try:
        from config import LLMLINGUA_TARGET_RATIO, LLMLINGUA_THRESHOLD_CHARS
    except ImportError:
        LLMLINGUA_THRESHOLD_CHARS, LLMLINGUA_TARGET_RATIO = 2000, 0.5

    threshold = threshold_chars if threshold_chars is not None else LLMLINGUA_THRESHOLD_CHARS
    rate = target_ratio if target_ratio is not None else LLMLINGUA_TARGET_RATIO

    if original_chars <= threshold:
        return CompressionResult(
            compressed=context,
            original_chars=original_chars,
            compressed_chars=original_chars,
            ratio=1.0,
            compressed_by_lingua=False,
            elapsed_ms=0.0,
        )

    compressor = get_compressor()
    if compressor is None:
        return CompressionResult(
            compressed=context,
            original_chars=original_chars,
            compressed_chars=original_chars,
            ratio=1.0,
            compressed_by_lingua=False,
            elapsed_ms=0.0,
        )

    t0 = time.time()
    compressed = compressor.compress(context=context, instruction=instruction, rate=rate)
    elapsed_ms = (time.time() - t0) * 1000.0
    compressed_chars = len(compressed)

    return CompressionResult(
        compressed=compressed,
        original_chars=original_chars,
        compressed_chars=compressed_chars,
        ratio=compressed_chars / original_chars if original_chars else 1.0,
        compressed_by_lingua=True,
        elapsed_ms=elapsed_ms,
    )
