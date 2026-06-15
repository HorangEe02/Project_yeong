"""CRAG (Corrective Retrieval-Augmented Generation) — Retrieval Evaluator.

출처: Yan et al. 2024, arXiv:2401.15884
       docs/RAG_ENHANCEMENT_PLAN.md §2.2, §4 Phase 1 PR2 (D-3 머지 목표)

AJIN 변형 (사용자 §11 #3 확정 — incorrect 강제 차단):
- 원논문의 "incorrect 시 web search fallback" 은 사내 KB only 정책상 금지
- 대신 "incorrect 시 LLM 호출 우회 + 사내 자료 없음 안내" 로 강제 차단
- ambiguous 는 경고 배지 + LLM 답변 (출처 신뢰도 낮음 명시)
- correct 는 정상 답변

Phase 1: 단순 threshold (top-1 rerank_score 기반)
- upper = config.CRAG_UPPER_THRESHOLD (기본 0.70)
- lower = config.CRAG_LOWER_THRESHOLD (기본 0.40)

Phase 2 (D+1 시작, 본선 후): Ollama qwen2.5:3b LLM-as-judge
- query-doc 적합도 LLM 직접 판단
- CRAG_LLM_JUDGE_ENABLED=true 시 활성

threshold 튜닝 (RAG_ENHANCEMENT_PLAN §12):
- BAAI/bge-reranker-v2-m3 score 분포 0.501–0.725 → upper 0.60 도 검토 가능
- 본선 후 production verdict 통계 기반 자동 조정 권장
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal, Sequence

logger = logging.getLogger(__name__)

CRAGVerdict = Literal["correct", "ambiguous", "incorrect"]


@dataclass
class CRAGResult:
    """단일 query 에 대한 CRAG 판정 결과.

    Attributes:
        verdict: correct / ambiguous / incorrect 중 하나.
        confidence: top-1 reranker score (또는 LLM judge score). [0, 1].
        rationale: 판정 근거 문구 — UI/log 용.
        top_score: confidence 와 동일하지만 명시적 노출 (frontend metadata 직렬화).
        evaluated_count: 평가에 사용된 검색 결과 수.
    """

    verdict: CRAGVerdict
    confidence: float
    rationale: str
    top_score: float
    evaluated_count: int = 0


def _score_of(result: Any) -> float:
    """검색 결과에서 점수 추출.

    우선순위:
      1. metadata.rerank_score (Phase 1 PR1 reranker 적용 후)
      2. .score (rerank 미적용 또는 reranker fallback 시 RRF 점수)
    """
    metadata = getattr(result, "metadata", None) or {}
    if isinstance(metadata, dict):
        rerank_score = metadata.get("rerank_score")
        if isinstance(rerank_score, (int, float)):
            return float(rerank_score)
    score = getattr(result, "score", 0.0)
    try:
        return float(score)
    except (TypeError, ValueError):
        return 0.0


def evaluate_retrieval(
    results: Sequence[Any],
    upper: float | None = None,
    lower: float | None = None,
) -> CRAGResult:
    """Phase 1 단순 threshold 평가.

    Args:
        results: searcher.search() 가 반환한 SearchResult sequence.
        upper: correct 판정 cutoff. None 이면 config.CRAG_UPPER_THRESHOLD.
        lower: incorrect 판정 cutoff (그 미만). None 이면 config.CRAG_LOWER_THRESHOLD.

    Returns:
        CRAGResult — verdict / confidence / rationale / top_score / evaluated_count.

    Phase 2 (LLM-as-judge) 는 별도 함수 evaluate_retrieval_llm() 로 분리 예정.
    """
    # threshold 기본값은 config 에서 lazy 로드 (test 환경에서 명시 가능)
    if upper is None or lower is None:
        try:
            from config import CRAG_LOWER_THRESHOLD, CRAG_UPPER_THRESHOLD
        except ImportError:
            CRAG_UPPER_THRESHOLD, CRAG_LOWER_THRESHOLD = 0.70, 0.40
        upper = upper if upper is not None else CRAG_UPPER_THRESHOLD
        lower = lower if lower is not None else CRAG_LOWER_THRESHOLD

    if not results:
        return CRAGResult(
            verdict="incorrect",
            confidence=0.0,
            rationale="검색 결과 0건",
            top_score=0.0,
            evaluated_count=0,
        )

    top_score = _score_of(results[0])
    n = len(results)

    if top_score >= upper:
        verdict: CRAGVerdict = "correct"
        rationale = f"top-1 score={top_score:.3f} ≥ upper={upper:.2f}"
    elif top_score >= lower:
        verdict = "ambiguous"
        rationale = f"top-1 score={top_score:.3f} ∈ [{lower:.2f}, {upper:.2f}) — 출처 신뢰도 낮음"
    else:
        verdict = "incorrect"
        rationale = f"top-1 score={top_score:.3f} < lower={lower:.2f} — 사내 자료에서 확인 불가"

    logger.info(
        "[CRAG] verdict=%s top_score=%.3f n=%d (upper=%.2f, lower=%.2f)",
        verdict,
        top_score,
        n,
        upper,
        lower,
    )
    return CRAGResult(
        verdict=verdict,
        confidence=top_score,
        rationale=rationale,
        top_score=top_score,
        evaluated_count=n,
    )


def should_block_llm(verdict: CRAGVerdict) -> bool:
    """사용자 §11 #3 확정 — incorrect → LLM 호출 우회 (강제 차단).

    onboarding/chat 흐름에서 verdict 가 incorrect 면 LLM 호출 skip 후
    "사내 자료 없음 안내" 만 반환.

    Returns:
        True — incorrect (LLM 호출 우회). False — correct/ambiguous (정상 진행).
    """
    return verdict == "incorrect"


def blocked_response_message(rationale: str = "") -> str:
    """LLM 호출 차단 시 사용자에게 노출할 안내 메시지.

    Args:
        rationale: CRAG 판정 근거 (운영 로그 / UI debug 노출용).

    Returns:
        사내 자료 없음 안내 + 담당 부서 문의 메시지.
    """
    base = (
        "사내 자료에서 관련 정보를 확인할 수 없습니다.\n"
        "정확한 답변을 위해 인사관리팀 또는 안전보건팀에 직접 문의해 주세요."
    )
    if rationale:
        return f"{base}\n\n(retrieval 진단: {rationale})"
    return base
