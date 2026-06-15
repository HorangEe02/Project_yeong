"""Reranker 한국어 변형 비교 평가 스크립트.

출처: docs/RAG_ENHANCEMENT_PLAN.md §11 #4 (사용자 확정 — Reranker 한국어 변형 비교 진행)
목적: BAAI/bge-reranker-v2-m3 (다국어 cross-encoder) vs 한국어 임베딩 모델 기반 scoring 비교
       (참고: dragonkue/BGE-m3-ko 는 임베딩 모델이라 cross-encoder 가 아님 — embedding-based
        cosine scoring 으로 비교한다. 두 모델군의 한국어 retrieval 품질을 동등 비교하기 위함.)

골든셋: data/eval/golden_qa_kosha.jsonl (긍정 20 + 부정 5)
메트릭: MRR@5, nDCG@5, Hit@5, Verdict Accuracy (CRAG threshold 적용 시)

사용:
    python scripts/eval_rerank_korean.py \
        --candidates BAAI/bge-reranker-v2-m3,dragonkue/BGE-m3-ko \
        --golden data/eval/golden_qa_kosha.jsonl \
        --top-k-input 20 \
        --top-k-output 5

권장 환경:
    # FlagEmbedding 로딩에 ~1GB RAM, 첫 실행 시 HF 모델 다운로드 (~600MB)
    pip install FlagEmbedding>=1.2.10
    export HF_HOME=~/.cache/huggingface  # 모델 캐시 경로
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# 부모 디렉토리 (04_AJIN) 에도 동명의 config.py / features/ 가 있어 sys.path 충돌 발생.
# 항상 ajin-ai-assistant-react 프로젝트 루트를 sys.path 최상위에 두고 cwd 도 그쪽으로 고정한다.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
os.chdir(_PROJECT_ROOT)

logger = logging.getLogger("eval.rerank")


# ---------------------------------------------------------------------------
# 데이터 모델
# ---------------------------------------------------------------------------


@dataclass
class GoldenItem:
    """골든셋 단일 항목."""

    id: str
    query: str
    expected_doc_id_prefix: str | None
    expected_verdict: str
    category: str
    note: str = ""


@dataclass
class ModelResult:
    """단일 모델의 전체 평가 결과."""

    model_name: str
    mrr_at_5: float = 0.0
    ndcg_at_5: float = 0.0
    hit_at_5: float = 0.0
    verdict_accuracy: float = 0.0
    avg_latency_ms: float = 0.0
    peak_memory_mb: float = 0.0
    per_query: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 골든셋 로드
# ---------------------------------------------------------------------------


def load_golden(path: Path) -> list[GoldenItem]:
    items: list[GoldenItem] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            items.append(
                GoldenItem(
                    id=obj["id"],
                    query=obj["query"],
                    expected_doc_id_prefix=obj.get("expected_doc_id_prefix"),
                    expected_verdict=obj["expected_verdict"],
                    category=obj.get("category", ""),
                    note=obj.get("note", ""),
                )
            )
    return items


# ---------------------------------------------------------------------------
# AJIN 검색 어댑터 — 기존 HybridSearcher 활용
# ---------------------------------------------------------------------------


def get_hybrid_candidates(query: str, top_k_input: int) -> list[dict[str, Any]]:
    """HybridSearcher 로 top-K 후보 가져오기 (BM25 + pgvector RRF).

    rerank 입력 후보. 각 항목은 {doc_id, title, content, score, metadata} 형식.
    """
    try:
        from features.search.searcher import HybridSearcher
    except ImportError as e:
        logger.error("HybridSearcher import 실패: %s", e)
        return []

    searcher = HybridSearcher()
    results = searcher.search(query=query, k=top_k_input)
    return [
        {
            "doc_id": r.doc_id,
            "title": r.title,
            "content": r.content,
            "score": r.score,
            "metadata": r.metadata,
        }
        for r in results
    ]


# ---------------------------------------------------------------------------
# Reranker 추상화 — cross-encoder + embedding-cosine 두 종류 비교 가능
# ---------------------------------------------------------------------------


class CrossEncoderReranker:
    """sentence-transformers CrossEncoder 기반 reranker.

    bge-reranker-v2-m3 처럼 (query, doc) pair 를 받아 직접 relevance score 출력.
    FlagEmbedding.FlagReranker 는 transformers 5.x 에서 prepare_for_model deprecation
    으로 동작 불가 — sentence-transformers 가 표준 호환 경로.
    """

    def __init__(self, model_name: str, use_fp16: bool = True):
        from sentence_transformers import CrossEncoder
        self.model_name = model_name
        self.model = CrossEncoder(model_name, max_length=512)
        if use_fp16:
            try:
                self.model.model.half()
            except Exception:
                pass

    def rerank(self, query: str, candidates: list[dict]) -> list[tuple[dict, float]]:
        if not candidates:
            return []
        import math
        pairs = [[query, c["content"][:512]] for c in candidates]
        raw = self.model.predict(pairs)
        # sigmoid normalize → [0, 1]
        scores = [1.0 / (1.0 + math.exp(-float(s))) for s in raw]
        scored = list(zip(candidates, scores))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored


class EmbeddingCosineReranker:
    """sentence-transformers 임베딩 모델의 cosine 유사도로 재정렬.

    cross-encoder 가 아닌 dual-encoder 모델 비교용 (dragonkue/BGE-m3-ko 등).
    """

    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    def rerank(self, query: str, candidates: list[dict]) -> list[tuple[dict, float]]:
        if not candidates:
            return []
        import numpy as np
        q_vec = self.model.encode([query], normalize_embeddings=True)
        d_vecs = self.model.encode(
            [c["content"][:512] for c in candidates], normalize_embeddings=True
        )
        scores = (q_vec @ d_vecs.T).flatten().tolist()
        scored = list(zip(candidates, scores))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored


def build_reranker(model_name: str):
    """모델명 패턴으로 cross-encoder vs embedding 자동 판별."""
    name_lower = model_name.lower()
    if "reranker" in name_lower:
        return CrossEncoderReranker(model_name)
    return EmbeddingCosineReranker(model_name)


# ---------------------------------------------------------------------------
# 메트릭
# ---------------------------------------------------------------------------


def matches_expected(doc_id: str, expected_prefix: str | None) -> bool:
    if expected_prefix is None:
        return False
    return doc_id.startswith(expected_prefix)


def reciprocal_rank(reranked: list[tuple[dict, float]], expected_prefix: str | None, k: int = 5) -> float:
    if expected_prefix is None:
        return 0.0
    for rank, (cand, _) in enumerate(reranked[:k], start=1):
        if matches_expected(cand["doc_id"], expected_prefix):
            return 1.0 / rank
    return 0.0


def ndcg_at_k(reranked: list[tuple[dict, float]], expected_prefix: str | None, k: int = 5) -> float:
    if expected_prefix is None:
        return 0.0
    relevances = [
        1.0 if matches_expected(cand["doc_id"], expected_prefix) else 0.0
        for cand, _ in reranked[:k]
    ]
    if sum(relevances) == 0:
        return 0.0
    dcg = sum(rel / math.log2(rank + 2) for rank, rel in enumerate(relevances))
    idcg = 1.0  # 정답 1개 가정 → ideal DCG = 1/log2(2) = 1
    return dcg / idcg


def hit_at_k(reranked: list[tuple[dict, float]], expected_prefix: str | None, k: int = 5) -> float:
    if expected_prefix is None:
        return 0.0
    return 1.0 if any(
        matches_expected(cand["doc_id"], expected_prefix) for cand, _ in reranked[:k]
    ) else 0.0


def crag_verdict(top_score: float, upper: float = 0.70, lower: float = 0.40) -> str:
    if top_score >= upper:
        return "correct"
    if top_score >= lower:
        return "ambiguous"
    return "incorrect"


# ---------------------------------------------------------------------------
# 평가 루프
# ---------------------------------------------------------------------------


def evaluate_model(
    model_name: str,
    golden: list[GoldenItem],
    top_k_input: int,
    top_k_output: int,
    crag_upper: float,
    crag_lower: float,
) -> ModelResult:
    logger.info("=" * 60)
    logger.info("평가 시작: %s", model_name)
    logger.info("=" * 60)

    import psutil
    process = psutil.Process()
    mem_before = process.memory_info().rss / 1024 / 1024

    t0 = time.time()
    reranker = build_reranker(model_name)
    load_time = time.time() - t0
    logger.info("모델 로드: %.1fs", load_time)

    result = ModelResult(model_name=model_name)
    rr_sum = 0.0
    ndcg_sum = 0.0
    hit_sum = 0.0
    verdict_correct = 0
    latency_sum = 0.0

    for item in golden:
        candidates = get_hybrid_candidates(item.query, top_k_input)
        if not candidates and item.expected_verdict != "incorrect":
            logger.warning("후보 0건: %s", item.query)

        t_start = time.time()
        reranked = reranker.rerank(item.query, candidates)
        latency_ms = (time.time() - t_start) * 1000
        latency_sum += latency_ms

        top_score = reranked[0][1] if reranked else 0.0
        predicted_verdict = crag_verdict(top_score, crag_upper, crag_lower)

        rr = reciprocal_rank(reranked, item.expected_doc_id_prefix, top_k_output)
        ndcg = ndcg_at_k(reranked, item.expected_doc_id_prefix, top_k_output)
        hit = hit_at_k(reranked, item.expected_doc_id_prefix, top_k_output)
        v_match = 1 if predicted_verdict == item.expected_verdict else 0

        rr_sum += rr
        ndcg_sum += ndcg
        hit_sum += hit
        verdict_correct += v_match

        result.per_query.append(
            {
                "id": item.id,
                "query": item.query,
                "expected_verdict": item.expected_verdict,
                "predicted_verdict": predicted_verdict,
                "top_score": top_score,
                "rr": rr,
                "ndcg": ndcg,
                "hit": hit,
                "verdict_match": bool(v_match),
                "latency_ms": latency_ms,
                "top_doc_id": reranked[0][0]["doc_id"] if reranked else None,
            }
        )

    n = len(golden)
    result.mrr_at_5 = rr_sum / n
    result.ndcg_at_5 = ndcg_sum / n
    result.hit_at_5 = hit_sum / n
    result.verdict_accuracy = verdict_correct / n
    result.avg_latency_ms = latency_sum / n
    result.peak_memory_mb = process.memory_info().rss / 1024 / 1024 - mem_before

    return result


# ---------------------------------------------------------------------------
# 출력
# ---------------------------------------------------------------------------


def print_summary(results: list[ModelResult]) -> None:
    print()
    print("=" * 78)
    print("Reranker 비교 결과 — golden_qa_kosha.jsonl (긍정 20 + 부정 5)")
    print("=" * 78)
    print(
        f"{'Model':<55} {'MRR@5':>7} {'nDCG@5':>7} {'Hit@5':>7} {'VerdictAcc':>11} {'Latency(ms)':>12}"
    )
    print("-" * 78)
    for r in results:
        print(
            f"{r.model_name:<55} "
            f"{r.mrr_at_5:>7.3f} {r.ndcg_at_5:>7.3f} {r.hit_at_5:>7.3f} "
            f"{r.verdict_accuracy:>11.3f} {r.avg_latency_ms:>12.1f}"
        )
    print("-" * 78)
    print()

    if len(results) >= 2:
        best = max(results, key=lambda r: r.mrr_at_5)
        print(f"✅ 권장 모델 (MRR@5 기준): {best.model_name}")
        print(f"   → RAG_ENHANCEMENT_PLAN.md 의 RERANKER_MODEL 환경변수 기본값으로 채택")
        print()


def save_results(results: list[ModelResult], output_path: Path) -> None:
    payload = [
        {
            "model_name": r.model_name,
            "mrr_at_5": r.mrr_at_5,
            "ndcg_at_5": r.ndcg_at_5,
            "hit_at_5": r.hit_at_5,
            "verdict_accuracy": r.verdict_accuracy,
            "avg_latency_ms": r.avg_latency_ms,
            "peak_memory_mb": r.peak_memory_mb,
            "per_query": r.per_query,
        }
        for r in results
    ]
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("결과 저장: %s", output_path)


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Reranker 한국어 변형 비교 평가")
    parser.add_argument(
        "--candidates",
        default="BAAI/bge-reranker-v2-m3,dragonkue/BGE-m3-ko",
        help="비교할 모델 후보 (쉼표 구분). 'reranker' 패턴이 있으면 cross-encoder, "
        "아니면 embedding cosine 으로 판별",
    )
    parser.add_argument(
        "--golden",
        default="data/eval/golden_qa_kosha.jsonl",
        help="골든셋 JSONL 경로",
    )
    parser.add_argument("--top-k-input", type=int, default=20, help="rerank 입력 후보 수")
    parser.add_argument("--top-k-output", type=int, default=5, help="최종 top-K (메트릭 기준)")
    parser.add_argument("--crag-upper", type=float, default=0.70)
    parser.add_argument("--crag-lower", type=float, default=0.40)
    parser.add_argument(
        "--output",
        default="data/eval/rerank_eval_results.json",
        help="평가 결과 저장 경로",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    golden_path = Path(args.golden)
    if not golden_path.exists():
        logger.error("골든셋 없음: %s", golden_path)
        return 1
    golden = load_golden(golden_path)
    logger.info("골든셋 로드: %d 항목", len(golden))

    candidates = [c.strip() for c in args.candidates.split(",") if c.strip()]
    logger.info("비교 후보 %d개: %s", len(candidates), candidates)

    results: list[ModelResult] = []
    for model_name in candidates:
        try:
            result = evaluate_model(
                model_name=model_name,
                golden=golden,
                top_k_input=args.top_k_input,
                top_k_output=args.top_k_output,
                crag_upper=args.crag_upper,
                crag_lower=args.crag_lower,
            )
            results.append(result)
        except Exception as e:
            logger.exception("모델 평가 실패: %s — %s", model_name, e)
            continue

    if not results:
        logger.error("평가 결과 없음")
        return 1

    print_summary(results)
    save_results(results, Path(args.output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
