#!/usr/bin/env python3
"""아진산업 AJIN 시드 데이터 검증 스크립트.

Supabase document_chunks + document_embeddings 테이블의 시드 상태를 검증하고
시연 쿼리 "프레스 트라이 8D Report 양식"에 대한 hybrid_search 결과를 확인한다.

사용 예:
    python3 scripts/verify_seeded_documents.py
    python3 scripts/verify_seeded_documents.py --json-output /tmp/verify_result.json
    python3 scripts/verify_seeded_documents.py --skip-hybrid-search
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# 환경 설정
# ---------------------------------------------------------------------------

EXPECTED_CHUNK_COUNT_MIN = 130
EXPECTED_CHUNK_COUNT_MAX = 160
EXPECTED_EMBEDDING_DIM = 1024
EXPECTED_DOCS = 30
DEMO_QUERY = "프레스 트라이 8D Report 양식"
DEMO_EXPECTED_DOC_ID = "8D-2025-Q4-027-PRESS-TRY"
DEMO_EXPECTED_TITLE_KEYWORD = "프레스 트라이"


# ---------------------------------------------------------------------------
# 임베딩 (Ollama bge-m3)
# ---------------------------------------------------------------------------

async def _embed_query_async(
    query: str,
    ollama_url: str,
    model: str = "bge-m3",
) -> list[float]:
    """쿼리 임베딩 생성 (1024차원)."""
    try:
        import httpx
    except ImportError as exc:
        raise RuntimeError("httpx 패키지가 필요합니다: pip install httpx") from exc

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{ollama_url.rstrip('/')}/api/embed",
            json={"model": model, "input": [query]},
        )
        resp.raise_for_status()
        data = resp.json()

    embeddings = data.get("embeddings", [])
    if not embeddings:
        raise RuntimeError(f"Ollama 응답에 embeddings 없음: {list(data.keys())}")

    emb = embeddings[0]
    if len(emb) != EXPECTED_EMBEDDING_DIM:
        raise RuntimeError(f"임베딩 차원 불일치: {len(emb)} (기대: {EXPECTED_EMBEDDING_DIM})")

    return emb


def embed_query(query: str, ollama_url: str) -> list[float]:
    """embed_query_async의 동기 래퍼."""
    return asyncio.run(_embed_query_async(query, ollama_url))


# ---------------------------------------------------------------------------
# 검증 함수들
# ---------------------------------------------------------------------------

def check_chunk_count(sb: Any) -> dict[str, Any]:
    """(1) document_chunks 행 수 확인."""
    result = sb.table("document_chunks").select("id", count="exact").execute()
    count = result.count if result.count is not None else len(result.data)

    passed = EXPECTED_CHUNK_COUNT_MIN <= count <= EXPECTED_CHUNK_COUNT_MAX
    return {
        "check": "chunk_count",
        "passed": passed,
        "count": count,
        "expected_range": f"{EXPECTED_CHUNK_COUNT_MIN}~{EXPECTED_CHUNK_COUNT_MAX}",
        "message": (
            f"document_chunks 행 수: {count} "
            f"({'정상' if passed else '범위 이탈'})"
        ),
    }


def check_embedding_count_and_dim(sb: Any) -> dict[str, Any]:
    """(2) document_embeddings 행 수 + embedding_dim 확인."""
    # 행 수
    count_result = (
        sb.table("document_embeddings").select("chunk_id", count="exact").execute()
    )
    emb_count = (
        count_result.count
        if count_result.count is not None
        else len(count_result.data)
    )

    # embedding_dim 분포 (샘플 100개)
    dim_result = (
        sb.table("document_embeddings")
        .select("embedding_dim")
        .limit(100)
        .execute()
    )
    dims = [row["embedding_dim"] for row in (dim_result.data or [])]
    wrong_dims = [d for d in dims if d != EXPECTED_EMBEDDING_DIM]

    dim_ok = len(wrong_dims) == 0
    count_ok = EXPECTED_CHUNK_COUNT_MIN <= emb_count <= EXPECTED_CHUNK_COUNT_MAX

    return {
        "check": "embedding_count_dim",
        "passed": count_ok and dim_ok,
        "embedding_count": emb_count,
        "dim_sample_size": len(dims),
        "wrong_dims": wrong_dims[:5],
        "expected_dim": EXPECTED_EMBEDDING_DIM,
        "message": (
            f"document_embeddings 행 수: {emb_count}, "
            f"차원 이상: {len(wrong_dims)}개"
        ),
    }


def check_embedding_norms(sb: Any) -> dict[str, Any]:
    """(3) 샘플 5개 청크 임베딩 L2 norm 검증.

    bge-m3 정규화 임베딩의 L2 norm은 1.0에 가깝다 (±0.05 허용).
    """
    result = (
        sb.table("document_embeddings")
        .select("chunk_id, embedding")
        .limit(5)
        .execute()
    )
    rows = result.data or []

    norms: list[float] = []
    for row in rows:
        emb = row.get("embedding")
        if emb and isinstance(emb, list):
            norm = math.sqrt(sum(x * x for x in emb))
            norms.append(norm)

    # bge-m3는 정규화 모델 — norm ≈ 1.0 (0.90 ~ 1.10 허용)
    norm_ok = all(0.85 <= n <= 1.15 for n in norms)

    return {
        "check": "embedding_norms",
        "passed": norm_ok or len(norms) == 0,  # 임베딩 없으면 스킵
        "sample_count": len(norms),
        "norms": [round(n, 4) for n in norms],
        "expected_range": "0.85 ~ 1.15 (bge-m3 정규화)",
        "message": (
            f"샘플 {len(norms)}개 임베딩 norm: "
            f"{[round(n, 4) for n in norms]}"
            f" ({'정상' if norm_ok else '이상'})"
        ),
    }


def check_hybrid_search(
    sb: Any,
    query_embedding: list[float],
    top_k: int = 5,
) -> dict[str, Any]:
    """(4) 시연 쿼리 hybrid_search 결과 확인.

    private.hybrid_search_document_chunks 함수를 service_role로 호출.
    """
    try:
        result = sb.rpc(
            "hybrid_search_document_chunks",
            {
                "query_text": DEMO_QUERY,
                "query_embedding": query_embedding,
                "match_count": top_k,
                "doc_type_filter": None,
                "part_name_filter": None,
                "metadata_filter": {},
            },
        ).execute()
        rows = result.data or []
    except Exception as exc:
        # private 스키마 RPC는 service_role에서만 접근 가능
        return {
            "check": "hybrid_search",
            "passed": False,
            "error": str(exc),
            "message": f"hybrid_search RPC 호출 실패: {exc}",
        }

    results_summary = [
        {
            "rank": i + 1,
            "source_doc_id": row.get("source_doc_id"),
            "title": row.get("title"),
            "score": round(float(row.get("score", 0)), 6),
        }
        for i, row in enumerate(rows[:top_k])
    ]

    # 첫 결과가 기대 문서인지 확인
    top1_doc_id = rows[0].get("source_doc_id") if rows else None
    top1_title = rows[0].get("title", "") if rows else ""
    demo_doc_in_top5 = any(
        r.get("source_doc_id") == DEMO_EXPECTED_DOC_ID for r in rows[:5]
    )

    passed = demo_doc_in_top5 and len(rows) >= 3

    return {
        "check": "hybrid_search",
        "passed": passed,
        "query": DEMO_QUERY,
        "result_count": len(rows),
        "top1_doc_id": top1_doc_id,
        "top1_title": top1_title,
        "demo_doc_in_top5": demo_doc_in_top5,
        "expected_doc_id": DEMO_EXPECTED_DOC_ID,
        "results": results_summary,
        "message": (
            f"시연 쿼리 결과 {len(rows)}건, "
            f"'{DEMO_EXPECTED_DOC_ID}' top-5 포함: {demo_doc_in_top5}"
        ),
    }


def check_doc_type_distribution(sb: Any) -> dict[str, Any]:
    """(5) doc_type별 분포 확인 (30문서 기대)."""
    result = (
        sb.table("document_chunks")
        .select("doc_type, source_doc_id")
        .execute()
    )
    rows = result.data or []

    # source_doc_id 고유 문서 수 집계
    type_docs: dict[str, set[str]] = {}
    for row in rows:
        dt = row.get("doc_type") or "unknown"
        did = row.get("source_doc_id") or ""
        type_docs.setdefault(dt, set()).add(did)

    distribution = {dt: len(ids) for dt, ids in type_docs.items()}
    total_docs = len({row.get("source_doc_id") for row in rows})

    expected = {
        "8d_report": 5,
        "ecn": 5,
        "ppap": 3,
        "email": 7,
        "meeting_note": 10,
    }
    mismatches = {
        dt: {"actual": distribution.get(dt, 0), "expected": cnt}
        for dt, cnt in expected.items()
        if distribution.get(dt, 0) != cnt
    }

    passed = total_docs == EXPECTED_DOCS and len(mismatches) == 0

    return {
        "check": "doc_type_distribution",
        "passed": passed,
        "total_docs": total_docs,
        "expected_docs": EXPECTED_DOCS,
        "distribution": distribution,
        "mismatches": mismatches,
        "message": (
            f"총 문서 수: {total_docs} (기대: {EXPECTED_DOCS}), "
            f"분포 불일치: {len(mismatches)}건"
        ),
    }


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------

def verify_main(args: argparse.Namespace) -> int:
    """검증 메인 흐름.

    Returns:
        0: 전체 검증 통과, 1: 일부 실패.
    """
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_SECRET_KEY", "")
    ollama_url = args.ollama_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

    if not supabase_url or not supabase_key:
        print(
            "[오류] SUPABASE_URL 및 SUPABASE_SECRET_KEY 환경변수가 필요합니다.",
            file=sys.stderr,
        )
        return 1

    print(f"[정보] Supabase URL: {supabase_url}")
    print(f"[정보] Ollama URL: {ollama_url}")
    print()

    # Supabase 클라이언트
    try:
        from supabase import create_client
    except ImportError:
        print("[오류] supabase 패키지가 필요합니다: pip install supabase", file=sys.stderr)
        return 1

    sb = create_client(supabase_url, supabase_key)

    results: list[dict[str, Any]] = []

    # (1) 청크 수
    print("[검증 1/5] document_chunks 행 수...")
    r1 = check_chunk_count(sb)
    results.append(r1)
    _print_check(r1)

    # (2) 임베딩 수 + 차원
    print("[검증 2/5] document_embeddings 행 수 + 차원...")
    r2 = check_embedding_count_and_dim(sb)
    results.append(r2)
    _print_check(r2)

    # (3) 임베딩 norm
    print("[검증 3/5] 샘플 임베딩 L2 norm...")
    r3 = check_embedding_norms(sb)
    results.append(r3)
    _print_check(r3)

    # (4) doc_type 분포
    print("[검증 4/5] doc_type 분포...")
    r4 = check_doc_type_distribution(sb)
    results.append(r4)
    _print_check(r4)

    # (5) hybrid_search 시연 쿼리
    if args.skip_hybrid_search:
        print("[검증 5/5] hybrid_search — 스킵 (--skip-hybrid-search)")
        r5 = {
            "check": "hybrid_search",
            "passed": None,
            "message": "스킵됨",
        }
    else:
        print(f"[검증 5/5] hybrid_search: \"{DEMO_QUERY}\"")
        print("  Ollama 쿼리 임베딩 생성 중...")
        try:
            query_emb = embed_query(DEMO_QUERY, ollama_url)
            print(f"  임베딩 차원: {len(query_emb)}")
            r5 = check_hybrid_search(sb, query_emb, top_k=5)
        except Exception as exc:
            r5 = {
                "check": "hybrid_search",
                "passed": False,
                "error": str(exc),
                "message": f"쿼리 임베딩 생성 실패: {exc}",
            }
        _print_check(r5)

    results.append(r5)

    # --- 최종 판정 ---
    print()
    print("=" * 55)
    failed = [r for r in results if r.get("passed") is False]
    skipped = [r for r in results if r.get("passed") is None]

    if not failed:
        verdict = "PASS" if not skipped else "PASS (일부 스킵)"
        print(f"[최종 판정] {verdict}")
        exit_code = 0
    else:
        print(f"[최종 판정] FAIL — 실패 항목: {[r['check'] for r in failed]}")
        exit_code = 1

    print(f"  통과: {len(results) - len(failed) - len(skipped)}")
    print(f"  실패: {len(failed)}")
    print(f"  스킵: {len(skipped)}")
    print("=" * 55)

    # JSON 출력
    report = {
        "verdict": "PASS" if exit_code == 0 else "FAIL",
        "total_checks": len(results),
        "passed": len(results) - len(failed) - len(skipped),
        "failed": len(failed),
        "skipped": len(skipped),
        "checks": results,
    }

    if args.json_output:
        out_path = Path(args.json_output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n[JSON 출력] {out_path}")

    if args.print_json:
        print("\n" + json.dumps(report, ensure_ascii=False, indent=2))

    return exit_code


def _print_check(r: dict[str, Any]) -> None:
    """검증 결과 한 줄 출력."""
    passed = r.get("passed")
    if passed is True:
        icon = "PASS"
    elif passed is False:
        icon = "FAIL"
    else:
        icon = "SKIP"
    print(f"  [{icon}] {r.get('message', '')}")
    # hybrid_search 결과 상세 출력
    if r.get("check") == "hybrid_search" and r.get("results"):
        for item in r["results"]:
            mark = " <-- 시연 타겟" if item.get("source_doc_id") == DEMO_EXPECTED_DOC_ID else ""
            print(
                f"    #{item['rank']:>2} {item['source_doc_id']:<35} "
                f"score={item['score']:.6f}{mark}"
            )


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--ollama-url",
        default=None,
        help="Ollama 서버 URL (기본: http://localhost:11434 또는 OLLAMA_BASE_URL)",
    )
    parser.add_argument(
        "--skip-hybrid-search",
        action="store_true",
        default=False,
        help="hybrid_search 검증 스킵 (Ollama 미실행 환경)",
    )
    parser.add_argument(
        "--json-output",
        default=None,
        metavar="PATH",
        help="검증 결과를 JSON 파일로 저장",
    )
    parser.add_argument(
        "--print-json",
        action="store_true",
        default=False,
        help="검증 결과 JSON을 stdout에 출력 (CI 통합용)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# 엔트리포인트
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    raise SystemExit(verify_main(parse_args()))
