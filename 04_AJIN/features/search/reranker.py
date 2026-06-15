"""BGE Reranker (cross-encoder) — HybridSearcher 의 top-K 재정렬 단계.

출처: docs/RAG_ENHANCEMENT_PLAN.md §2.1 (Phase 1, P0)
모델: BAAI/bge-reranker-v2-m3 (568M params, 100+ 언어, MIT, FP16)
       또는 사용자 §11 #4 확정에 따라 한국어 변형 비교 후 채택된 모델
       (env: RERANKER_MODEL)

설계:
- searcher.py 와 의존성 최소화: query(str) + texts(list[str]) → scores(list[float])
  로 score 만 반환. SearchResult 업데이트는 searcher.py 가 담당.
- lazy init: 첫 호출 시 모델 로드. config 의 RERANKER_ENABLED=false 면 사용 안 됨.
- FP16: Cloud Run CPU 환경에서 ~600MB → 300MB 메모리, latency 약 2배 빠름.
- graceful degradation: FlagEmbedding import 실패 또는 모델 다운로드 실패 시
  None 반환 → searcher 가 reranker 없이 RRF 결과 그대로 사용 (slim image 호환).
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

logger = logging.getLogger("ajin.search.reranker")


class BgeReranker:
    """BGE cross-encoder reranker singleton.

    한 프로세스에 1개 인스턴스만 메모리에 유지. 모델 로드는 첫 호출 시 1회만 발생.
    """

    _instance: Optional["BgeReranker"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):  # noqa: ANN204
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(
        self,
        model_name: str | None = None,
        use_fp16: bool | None = None,
    ):
        if self._initialized:
            return

        from config import RERANKER_MODEL, RERANKER_USE_FP16

        self.model_name = model_name or RERANKER_MODEL
        self.use_fp16 = use_fp16 if use_fp16 is not None else RERANKER_USE_FP16
        self._model = None
        self._model_loaded = False
        self._load_failed = False
        self._initialized = True

        logger.info(
            "BgeReranker 인스턴스 생성 (model=%s, fp16=%s, lazy)",
            self.model_name,
            self.use_fp16,
        )

    def _ensure_loaded(self) -> bool:
        """모델 lazy 로드. 실패 시 self._load_failed=True 로 영구 기록 (재시도 안 함).

        sentence-transformers CrossEncoder 사용 — transformers 5.x 와 호환.
        (FlagEmbedding 의 FlagReranker 는 transformers 5.x 에서 prepare_for_model
         deprecation 으로 동작 불가, 2026-05 검증 완료.)
        """
        if self._model_loaded:
            return True
        if self._load_failed:
            return False

        try:
            from sentence_transformers import CrossEncoder
        except ImportError as e:
            logger.warning(
                "sentence-transformers import 실패 — reranker 비활성, RRF 결과 그대로 사용. (%s)",
                e,
            )
            self._load_failed = True
            return False

        try:
            logger.info("BgeReranker 모델 로드 시작: %s", self.model_name)
            import time
            t0 = time.time()
            # CrossEncoder 는 max_length 로 truncation 자동 처리. FP16 은 PyTorch 단에서.
            self._model = CrossEncoder(self.model_name, max_length=512)
            if self.use_fp16:
                try:
                    self._model.model.half()
                except Exception as e:
                    logger.info("FP16 변환 skip (CPU/MPS 미지원 가능): %s", e)
            elapsed = time.time() - t0
            self._model_loaded = True
            logger.info("BgeReranker 로드 완료 (%.1fs)", elapsed)
            return True
        except Exception as e:
            logger.exception("BgeReranker 모델 로드 실패: %s", e)
            self._load_failed = True
            return False

    def compute_scores(
        self,
        query: str,
        texts: list[str],
        normalize: bool = True,
        max_chunk_chars: int = 512,
    ) -> list[float] | None:
        """query 와 각 text 쌍의 cross-encoder relevance score 반환.

        Args:
            query: 사용자 질의.
            texts: 재정렬 대상 chunk 본문 리스트.
            normalize: True 면 sigmoid 적용 후 [0, 1] 범위. False 면 raw logit.
            max_chunk_chars: 각 chunk 본문 truncation 길이.

        Returns:
            scores: 각 text 의 점수 list. 모델 로드 실패 시 None.
        """
        if not texts:
            return []
        if not self._ensure_loaded():
            return None

        try:
            import math
            pairs = [[query, text[:max_chunk_chars]] for text in texts]
            raw_scores = self._model.predict(pairs)
            scores = [float(s) for s in raw_scores]
            if normalize:
                scores = [1.0 / (1.0 + math.exp(-s)) for s in scores]
            return scores
        except Exception as e:
            logger.exception("reranker compute_scores 실패 — RRF 결과 유지. (%s)", e)
            return None

    @property
    def is_available(self) -> bool:
        """검색 파이프라인이 reranker 사용 가능한지 사전 확인 (lazy 로드 trigger 안 함)."""
        return not self._load_failed


# ---------------------------------------------------------------------------
# 모듈 헬퍼 — 기존 검색 파이프라인이 BgeReranker 인스턴스 직접 import 안 해도 되게 wrap
# ---------------------------------------------------------------------------


_global_reranker: Optional[BgeReranker] = None


def get_reranker() -> BgeReranker | None:
    """전역 BgeReranker 싱글톤 반환. RERANKER_ENABLED=false 면 None.

    searcher.HybridSearcher 가 __init__ 단계에서 호출. None 일 때는 rerank 단계 skip.
    """
    global _global_reranker

    try:
        from config import RERANKER_ENABLED
    except ImportError:
        return None

    if not RERANKER_ENABLED:
        logger.info("RERANKER_ENABLED=false — reranker 비활성 (RRF 결과 그대로 반환)")
        return None

    if _global_reranker is None:
        _global_reranker = BgeReranker()
    return _global_reranker


def reset_reranker() -> None:
    """테스트/재시작용 — 싱글톤 인스턴스 reset."""
    global _global_reranker
    _global_reranker = None
    BgeReranker._instance = None  # type: ignore[assignment]
