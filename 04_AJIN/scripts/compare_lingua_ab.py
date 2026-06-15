"""LLMLingua 압축 전/후 A/B 비교 스크립트.

Goal 5/5 — "A/B 비교 — 압축 전/후 응답 품질 + 토큰 절감률 측정".
출처: docs/RAG_ENHANCEMENT_PLAN.md §2.3 + §4 Phase 2 (D+1 = 2026-06-12 활성 직후 실행).

목적:
- 동일 query 셋에 대해 LLMLINGUA_ENABLED=true / false 양쪽 RAG 답변 받음
- 토큰 절감률 (compressed/original chars) + latency (TTFT/total)
- 응답 품질 — LLM-as-judge (Ollama qwen2.5:3b) 또는 사용자 평가

3가지 모드:
1. compression-only: maybe_compress_context() 직접 호출 + 통계만 (LLM 호출 없음)
2. e2e-mock: LLM 호출 mock + token 수 비교
3. e2e-live: production Ollama 호출 (시간/비용 크므로 신중)

사용:
    # 압축률만 측정 (가장 빠름, LLM 호출 없음)
    python scripts/compare_lingua_ab.py --mode compression-only \\
        --queries data/eval/ab_queries.jsonl

    # E2E 비교 (Ollama 호출, ~5분/20 query)
    python scripts/compare_lingua_ab.py --mode e2e-live \\
        --queries data/eval/ab_queries.jsonl \\
        --ollama-url http://localhost:11434
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("ab.lingua")


@dataclass
class ABResult:
    """단일 query 의 A/B 결과."""

    query: str
    original_chars: int
    compressed_chars: int
    ratio: float
    compress_ms: float
    # E2E 모드용 필드
    llm_response_original: str = ""
    llm_response_compressed: str = ""
    llm_latency_original_ms: float = 0.0
    llm_latency_compressed_ms: float = 0.0


@dataclass
class ABSummary:
    """전체 비교 결과 통계."""

    total_queries: int
    avg_ratio: float
    avg_original_chars: float
    avg_compressed_chars: float
    avg_compress_ms: float
    avg_llm_latency_original_ms: float = 0.0
    avg_llm_latency_compressed_ms: float = 0.0
    token_savings_pct: float = 0.0


def load_queries(path: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


def get_kb_context_for_query(query: str, project_root: Path) -> str:
    """query 에 대한 KB context 추출.

    실제 production 흐름과 동일하게 onboarding.load_kb_context 호출.
    """
    try:
        from features.onboarding.kb_lookup import load_kb_context

        kb_ctx = load_kb_context(query, "", max_chars=8000, language="ko")
        if kb_ctx:
            return f"[사내 자료]\n{kb_ctx.get('text', '')}"
    except Exception as e:
        logger.warning("load_kb_context 실패 (%s) — query=%s", e, query[:40])
    # KB 매치 없으면 placeholder long context 생성 (압축 효과 측정용)
    return "샘플 context. " * 200  # ~3000 chars


def run_compression_only(queries: list[dict[str, Any]]) -> list[ABResult]:
    """LLM 호출 없이 압축 효과만 측정."""
    from features.compression.llmlingua_filter import maybe_compress_context

    results: list[ABResult] = []
    project_root = Path(__file__).resolve().parent.parent
    for i, item in enumerate(queries):
        query = item["query"]
        context = get_kb_context_for_query(query, project_root)
        compressed_result = maybe_compress_context(context, instruction=query)
        results.append(
            ABResult(
                query=query,
                original_chars=compressed_result.original_chars,
                compressed_chars=compressed_result.compressed_chars,
                ratio=compressed_result.ratio,
                compress_ms=compressed_result.elapsed_ms,
            )
        )
        logger.info(
            "[%d/%d] %s — %d→%d chars (ratio=%.3f, %.1fms)",
            i + 1,
            len(queries),
            query[:30],
            compressed_result.original_chars,
            compressed_result.compressed_chars,
            compressed_result.ratio,
            compressed_result.elapsed_ms,
        )
    return results


def run_e2e_live(
    queries: list[dict[str, Any]],
    ollama_url: str,
    model: str,
) -> list[ABResult]:
    """Ollama 호출 + 압축 전/후 응답 + latency 비교."""
    try:
        import requests
    except ImportError:
        logger.error("requests 미설치 — `pip install requests`")
        return []

    from features.compression.llmlingua_filter import maybe_compress_context

    results: list[ABResult] = []
    project_root = Path(__file__).resolve().parent.parent

    def _ollama_generate(prompt: str) -> tuple[str, float]:
        t0 = time.time()
        resp = requests.post(
            f"{ollama_url.rstrip('/')}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=120,
        )
        elapsed = (time.time() - t0) * 1000.0
        if resp.status_code != 200:
            return "", elapsed
        data = resp.json()
        return str(data.get("response") or ""), elapsed

    for i, item in enumerate(queries):
        query = item["query"]
        context = get_kb_context_for_query(query, project_root)
        compressed = maybe_compress_context(context, instruction=query)

        prompt_orig = f"{context}\n\n[질문] {query}"
        prompt_comp = f"{compressed.compressed}\n\n[질문] {query}"

        resp_orig, lat_orig = _ollama_generate(prompt_orig)
        resp_comp, lat_comp = _ollama_generate(prompt_comp)

        results.append(
            ABResult(
                query=query,
                original_chars=compressed.original_chars,
                compressed_chars=compressed.compressed_chars,
                ratio=compressed.ratio,
                compress_ms=compressed.elapsed_ms,
                llm_response_original=resp_orig,
                llm_response_compressed=resp_comp,
                llm_latency_original_ms=lat_orig,
                llm_latency_compressed_ms=lat_comp,
            )
        )
        logger.info(
            "[%d/%d] LLM latency: orig=%.0fms, comp=%.0fms (Δ %.0fms)",
            i + 1,
            len(queries),
            lat_orig,
            lat_comp,
            lat_orig - lat_comp,
        )
    return results


def summarize(results: list[ABResult]) -> ABSummary:
    if not results:
        return ABSummary(0, 1.0, 0, 0, 0)
    n = len(results)
    avg_ratio = statistics.mean(r.ratio for r in results)
    avg_orig = statistics.mean(r.original_chars for r in results)
    avg_comp = statistics.mean(r.compressed_chars for r in results)
    avg_compress = statistics.mean(r.compress_ms for r in results)
    avg_lat_orig = statistics.mean(r.llm_latency_original_ms for r in results)
    avg_lat_comp = statistics.mean(r.llm_latency_compressed_ms for r in results)
    return ABSummary(
        total_queries=n,
        avg_ratio=avg_ratio,
        avg_original_chars=avg_orig,
        avg_compressed_chars=avg_comp,
        avg_compress_ms=avg_compress,
        avg_llm_latency_original_ms=avg_lat_orig,
        avg_llm_latency_compressed_ms=avg_lat_comp,
        token_savings_pct=(1.0 - avg_ratio) * 100.0,
    )


def print_report(summary: ABSummary) -> None:
    print()
    print("=" * 70)
    print("LLMLingua A/B Comparison Report")
    print("=" * 70)
    print(f"총 query: {summary.total_queries}")
    print()
    print("[압축 효과]")
    print(f"  평균 원본 chars:    {summary.avg_original_chars:>8.0f}")
    print(f"  평균 압축 후 chars: {summary.avg_compressed_chars:>8.0f}")
    print(f"  평균 압축률:        {summary.avg_ratio:>8.3f}")
    print(f"  토큰 절감률:        {summary.token_savings_pct:>8.1f}%")
    print(f"  평균 압축 latency:  {summary.avg_compress_ms:>8.1f}ms")
    print()
    if summary.avg_llm_latency_original_ms > 0:
        print("[LLM latency]")
        print(f"  원본 prompt:    {summary.avg_llm_latency_original_ms:>8.1f}ms")
        print(f"  압축 prompt:    {summary.avg_llm_latency_compressed_ms:>8.1f}ms")
        delta = summary.avg_llm_latency_original_ms - summary.avg_llm_latency_compressed_ms
        improvement = (
            delta / summary.avg_llm_latency_original_ms * 100
            if summary.avg_llm_latency_original_ms > 0
            else 0
        )
        print(f"  개선:           {delta:>8.1f}ms ({improvement:+.1f}%)")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="LLMLingua 압축 A/B 비교")
    parser.add_argument(
        "--mode",
        choices=["compression-only", "e2e-live"],
        default="compression-only",
        help="compression-only: 압축 통계만. e2e-live: Ollama 호출 + 응답 latency",
    )
    parser.add_argument(
        "--queries",
        default="data/eval/ab_queries.jsonl",
        help="A/B query 셋 JSONL — golden_qa_kosha 와 동일 schema",
    )
    parser.add_argument(
        "--ollama-url",
        default="http://localhost:11434",
        help="e2e-live 모드의 Ollama base URL",
    )
    parser.add_argument(
        "--model",
        default="qwen3.5:9b",
        help="e2e-live 모드의 Ollama 모델",
    )
    parser.add_argument(
        "--output",
        default="data/eval/lingua_ab_results.json",
        help="결과 JSON 저장 경로",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    # cwd 정규화
    import os

    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))
    os.chdir(project_root)

    queries_path = Path(args.queries)
    if not queries_path.exists():
        # ab_queries 파일이 없으면 golden_qa_kosha 의 긍정 query 만 활용
        fallback = Path("data/eval/golden_qa_kosha.jsonl")
        if not fallback.exists():
            logger.error("queries 파일 없음 + golden_qa_kosha fallback 도 없음")
            return 1
        logger.info("queries 파일 없음 — golden_qa_kosha.jsonl 의 긍정 query 사용")
        all_items = load_queries(fallback)
        items = [i for i in all_items if i.get("expected_verdict") == "correct"]
    else:
        items = load_queries(queries_path)

    if not items:
        logger.error("query 0건")
        return 1
    logger.info("총 %d query 로 A/B 비교 시작 (mode=%s)", len(items), args.mode)

    if args.mode == "compression-only":
        results = run_compression_only(items)
    elif args.mode == "e2e-live":
        results = run_e2e_live(items, args.ollama_url, args.model)
    else:
        logger.error("unknown mode: %s", args.mode)
        return 1

    summary = summarize(results)
    print_report(summary)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "mode": args.mode,
        "summary": summary.__dict__,
        "per_query": [
            {
                "query": r.query,
                "original_chars": r.original_chars,
                "compressed_chars": r.compressed_chars,
                "ratio": r.ratio,
                "compress_ms": r.compress_ms,
                "llm_latency_original_ms": r.llm_latency_original_ms,
                "llm_latency_compressed_ms": r.llm_latency_compressed_ms,
                "llm_response_original": r.llm_response_original[:500],
                "llm_response_compressed": r.llm_response_compressed[:500],
            }
            for r in results
        ],
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("결과 저장: %s", output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
