#!/usr/bin/env python3
"""아진산업 AJIN — employee_embeddings 시드 검증 스크립트.

5단계 검증:
  1) row count = 30
  2) 페르소나 3명 존재 확인 (employee_id 조회)
  3) embedding_dim=1024 일관성
  4) 임베딩 L2 norm 정상 범위 (bge-m3 정규화 범위 확인)
  5) 시연 쿼리: "박성훈 안전관리자" → private.match_employee_profiles() top-1 확인

사용 예:
    python3 scripts/verify_seeded_employees.py
    python3 scripts/verify_seeded_employees.py --json
    python3 scripts/verify_seeded_employees.py --ollama-url=http://localhost:11434
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
# 페르소나 상수
# ---------------------------------------------------------------------------

PERSONA_IDS = [
    "EMP-A-20260301-001",   # 김민준 (신입)
    "EMP-A-20150412-014",   # 박성훈 (안전관리자)
    "EMP-A-20220305-008",   # 이현아 (품질보증팀·8D)
]

EXPECTED_ROW_COUNT = 30
EXPECTED_EMBEDDING_DIM = 1024

# bge-m3 L2 norm: 정규화 출력이므로 norm ≈ 1.0 (허용 범위 0.9 ~ 1.1)
NORM_MIN = 0.9
NORM_MAX = 1.1

# 시연 쿼리 텍스트 → 박성훈이 top-1이어야 함
DEMO_QUERY_TEXT = "박성훈 안전관리자"
DEMO_EXPECTED_TOP1_ID = "EMP-A-20150412-014"   # 박성훈


# ---------------------------------------------------------------------------
# 임베딩 (Ollama bge-m3)
# ---------------------------------------------------------------------------

async def embed_single_async(
    text: str,
    ollama_url: str = "http://localhost:11434",
    model: str = "bge-m3",
) -> list[float]:
    """단일 텍스트 임베딩 생성."""
    try:
        import httpx
    except ImportError as exc:
        raise RuntimeError("httpx 패키지가 필요합니다: pip install httpx") from exc

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{ollama_url.rstrip('/')}/api/embed",
            json={"model": model, "input": [text]},
        )
        resp.raise_for_status()
        data = resp.json()

    embeddings = data.get("embeddings", [])
    if not embeddings:
        raise RuntimeError(f"Ollama 응답에 embeddings 없음: {list(data.keys())}")

    emb = embeddings[0]
    if len(emb) != EXPECTED_EMBEDDING_DIM:
        raise RuntimeError(
            f"임베딩 차원 불일치: 실제={len(emb)}, 기대={EXPECTED_EMBEDDING_DIM}"
        )
    return emb


def embed_single_sync(
    text: str,
    ollama_url: str = "http://localhost:11434",
) -> list[float]:
    """embed_single_async의 동기 래퍼."""
    return asyncio.run(embed_single_async(text, ollama_url))


# ---------------------------------------------------------------------------
# L2 norm 계산
# ---------------------------------------------------------------------------

def l2_norm(vec: list[float]) -> float:
    return math.sqrt(sum(x * x for x in vec))


# ---------------------------------------------------------------------------
# 검증 단계별 함수
# ---------------------------------------------------------------------------

def check_row_count(sb_client: Any) -> dict[str, Any]:
    """Step 1: row count = 30 확인."""
    result = (
        sb_client.table("employee_embeddings")
        .select("employee_id", count="exact")
        .execute()
    )
    count = result.count if result.count is not None else len(result.data or [])
    passed = count == EXPECTED_ROW_COUNT
    return {
        "step": 1,
        "name": "row_count",
        "passed": passed,
        "actual": count,
        "expected": EXPECTED_ROW_COUNT,
        "message": f"row count={count} (기대={EXPECTED_ROW_COUNT})",
    }


def check_personas_exist(sb_client: Any) -> dict[str, Any]:
    """Step 2: 페르소나 3명 존재 확인."""
    result = (
        sb_client.table("employee_embeddings")
        .select("employee_id, display_name")
        .in_("employee_id", PERSONA_IDS)
        .execute()
    )
    found_ids = {row["employee_id"] for row in (result.data or [])}
    missing = [pid for pid in PERSONA_IDS if pid not in found_ids]
    passed = len(missing) == 0
    return {
        "step": 2,
        "name": "personas_exist",
        "passed": passed,
        "found": list(found_ids),
        "missing": missing,
        "message": (
            f"페르소나 {len(found_ids)}/3명 확인"
            + (f" | 누락: {missing}" if missing else "")
        ),
    }


def check_embedding_dim(sb_client: Any) -> dict[str, Any]:
    """Step 3: embedding_dim=1024 일관성 확인."""
    result = (
        sb_client.table("employee_embeddings")
        .select("embedding_dim")
        .execute()
    )
    rows = result.data or []
    dims = {row["embedding_dim"] for row in rows}
    all_1024 = dims == {EXPECTED_EMBEDDING_DIM}
    passed = all_1024
    return {
        "step": 3,
        "name": "embedding_dim_consistency",
        "passed": passed,
        "distinct_dims": sorted(dims),
        "row_count": len(rows),
        "message": (
            f"embedding_dim 분포: {sorted(dims)} (전체 {len(rows)}행)"
        ),
    }


def check_embedding_norms(sb_client: Any) -> dict[str, Any]:
    """Step 4: 임베딩 L2 norm 정상 범위 확인 (bge-m3 정규화).

    페르소나 3명의 임베딩만 샘플 확인 (전체 30명 로드는 느릴 수 있으므로).
    """
    result = (
        sb_client.table("employee_embeddings")
        .select("employee_id, display_name, embedding")
        .in_("employee_id", PERSONA_IDS)
        .execute()
    )
    rows = result.data or []

    norm_results: list[dict[str, Any]] = []
    all_passed = True

    for row in rows:
        emb = row.get("embedding")
        if not emb:
            norm_results.append({
                "employee_id": row["employee_id"],
                "display_name": row.get("display_name"),
                "norm": None,
                "in_range": False,
            })
            all_passed = False
            continue

        # Supabase Python 클라이언트는 vector를 list로 반환할 수도, 문자열로 반환할 수도 있음
        if isinstance(emb, str):
            # "[0.1,0.2,...]" 형태 파싱
            emb = json.loads(emb)

        norm = l2_norm(emb)
        in_range = NORM_MIN <= norm <= NORM_MAX
        if not in_range:
            all_passed = False

        norm_results.append({
            "employee_id": row["employee_id"],
            "display_name": row.get("display_name"),
            "norm": round(norm, 6),
            "in_range": in_range,
        })

    passed = all_passed and len(norm_results) == len(PERSONA_IDS)
    return {
        "step": 4,
        "name": "embedding_norms",
        "passed": passed,
        "norm_range": [NORM_MIN, NORM_MAX],
        "samples": norm_results,
        "message": (
            f"L2 norm 샘플 {len(norm_results)}건 확인 "
            f"(허용범위 {NORM_MIN}~{NORM_MAX})"
        ),
    }


def check_demo_query(sb_client: Any, ollama_url: str) -> dict[str, Any]:
    """Step 5: 시연 쿼리 '박성훈 안전관리자' → top-1이 박성훈인지 확인.

    private.match_employee_profiles() RPC 호출.
    """
    # 쿼리 임베딩 생성
    try:
        query_emb = embed_single_sync(DEMO_QUERY_TEXT, ollama_url)
    except Exception as exc:
        return {
            "step": 5,
            "name": "demo_query_top1",
            "passed": False,
            "error": str(exc),
            "message": f"임베딩 생성 실패: {exc}",
        }

    # private.match_employee_profiles() RPC 호출
    try:
        result = sb_client.rpc(
            "match_employee_profiles",
            {
                "query_embedding": query_emb,
                "match_count": 5,
                "department_filter": None,
                "metadata_filter": {},
            },
        ).execute()
    except Exception as exc:
        return {
            "step": 5,
            "name": "demo_query_top1",
            "passed": False,
            "error": str(exc),
            "message": f"RPC 호출 실패: {exc}",
        }

    rows = result.data or []
    if not rows:
        return {
            "step": 5,
            "name": "demo_query_top1",
            "passed": False,
            "results": [],
            "message": "match_employee_profiles 결과가 비어 있습니다.",
        }

    top1 = rows[0]
    top1_id = top1.get("employee_id", "")
    top1_name = top1.get("display_name", "")
    top1_sim = top1.get("similarity", 0.0)
    passed = top1_id == DEMO_EXPECTED_TOP1_ID

    return {
        "step": 5,
        "name": "demo_query_top1",
        "passed": passed,
        "query": DEMO_QUERY_TEXT,
        "expected_top1_id": DEMO_EXPECTED_TOP1_ID,
        "actual_top1_id": top1_id,
        "actual_top1_name": top1_name,
        "actual_top1_similarity": round(float(top1_sim), 6),
        "top5": [
            {
                "rank": i + 1,
                "employee_id": r.get("employee_id"),
                "display_name": r.get("display_name"),
                "department": r.get("department"),
                "similarity": round(float(r.get("similarity", 0.0)), 6),
            }
            for i, r in enumerate(rows[:5])
        ],
        "message": (
            f"top-1: {top1_name} ({top1_id}) sim={top1_sim:.4f} "
            + ("[PASS]" if passed else f"[FAIL] 기대={DEMO_EXPECTED_TOP1_ID}")
        ),
    }


# ---------------------------------------------------------------------------
# 메인 검증 흐름
# ---------------------------------------------------------------------------

def verify_main(args: argparse.Namespace) -> int:
    """검증 메인 흐름.

    Args:
        args: argparse 파싱 결과.

    Returns:
        종료 코드 (0=전체 통과, 1=일부 실패).
    """
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_SECRET_KEY", "")
    ollama_url = args.ollama_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

    if not supabase_url:
        print("[오류] SUPABASE_URL 환경변수가 설정되지 않았습니다.", file=sys.stderr)
        return 1
    if not supabase_key:
        print("[오류] SUPABASE_SECRET_KEY 환경변수가 설정되지 않았습니다.", file=sys.stderr)
        return 1

    if not args.json_output:
        print(f"[정보] Supabase URL: {supabase_url}")
        print(f"[정보] Ollama URL:   {ollama_url}")
        print()

    # Supabase 클라이언트
    try:
        from supabase import create_client
    except ImportError:
        print(
            "[오류] supabase 패키지가 필요합니다: pip install supabase",
            file=sys.stderr,
        )
        return 1

    sb = create_client(supabase_url, supabase_key)

    # 검증 단계 실행
    steps: list[dict[str, Any]] = []

    step1 = check_row_count(sb)
    steps.append(step1)

    step2 = check_personas_exist(sb)
    steps.append(step2)

    step3 = check_embedding_dim(sb)
    steps.append(step3)

    step4 = check_embedding_norms(sb)
    steps.append(step4)

    step5 = check_demo_query(sb, ollama_url)
    steps.append(step5)

    # 결과 집계
    total = len(steps)
    passed_count = sum(1 for s in steps if s.get("passed", False))
    all_passed = passed_count == total

    report: dict[str, Any] = {
        "summary": {
            "total_steps": total,
            "passed": passed_count,
            "failed": total - passed_count,
            "all_passed": all_passed,
        },
        "steps": steps,
    }

    if args.json_output:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_report(report)

    return 0 if all_passed else 1


def _print_report(report: dict[str, Any]) -> None:
    """사람이 읽기 좋은 형태로 검증 결과 출력."""
    summary = report["summary"]
    steps = report["steps"]

    print("=" * 60)
    print("[employee_embeddings 검증 결과]")
    print(f"  통과: {summary['passed']}/{summary['total_steps']} 단계")
    print("=" * 60)

    for step in steps:
        status = "PASS" if step.get("passed") else "FAIL"
        print(f"\n  [Step {step['step']}] {step['name']} [{status}]")
        print(f"    {step.get('message', '')}")

        # 단계별 추가 정보
        if step["name"] == "personas_exist" and step.get("missing"):
            print(f"    누락 ID: {step['missing']}")

        if step["name"] == "embedding_norms" and step.get("samples"):
            for s in step["samples"]:
                nr = s.get("norm")
                ir = s.get("in_range")
                norm_str = f"{nr:.6f}" if nr is not None else "N/A"
                flag = "OK" if ir else "RANGE_ERROR"
                print(f"    {s['employee_id']} {s['display_name']}: norm={norm_str} [{flag}]")

        if step["name"] == "demo_query_top1" and step.get("top5"):
            print(f"    쿼리: '{step['query']}'")
            for r in step["top5"]:
                mark = "<-- TOP-1" if r["rank"] == 1 else ""
                print(
                    f"    [{r['rank']}] {r['display_name']} ({r['employee_id']}) "
                    f"sim={r['similarity']:.4f} {mark}"
                )

        if step.get("error"):
            print(f"    오류: {step['error']}")

    print("\n" + "=" * 60)
    overall = "ALL PASSED" if summary["all_passed"] else f"FAILED ({summary['failed']} 단계)"
    print(f"[최종] {overall}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=False,
        help="검증 결과를 JSON으로 출력 (CI 통합용)",
    )
    parser.add_argument(
        "--ollama-url",
        default=None,
        help="Ollama 서버 URL (기본: http://localhost:11434 또는 OLLAMA_BASE_URL 환경변수)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# 엔트리포인트
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    raise SystemExit(verify_main(parse_args()))
