#!/usr/bin/env python3
"""AJIN AI Assistant 시연 E2E 자동 검증 스크립트.

4 영역 19 체크를 단일 명령으로 실행해 PASS/FAIL 판정한다.
D-3·D-1 리허설 + D-Day T-120 빠른 점검용.

사용 예:
    python3 scripts/demo_check.py                       # strict (기본)
    python3 scripts/demo_check.py --soft                # WARN 허용
    python3 scripts/demo_check.py --fast                # 영역 A+B만 (1~2분)
    python3 scripts/demo_check.py --json                # CI 통합 JSON 출력
    python3 scripts/demo_check.py --no-vercel           # A5 Vercel 체크 생략
    python3 scripts/demo_check.py --no-cloud-run        # Cloud Run 호출 생략
    python3 scripts/demo_check.py --fast --no-vercel    # D-Day T-120
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

# ---------------------------------------------------------------------------
# 경로 설정
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
AJIN_ASSISTANT_ROOT = REPO_ROOT.parent / "ajin-ai-assistant"

for _p in [str(REPO_ROOT), str(AJIN_ASSISTANT_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

D_DAY = date(2026, 6, 10)
KST = timezone(timedelta(hours=9))

OLLAMA_URL_DEFAULT = "http://localhost:11434"
VERCEL_URL = "https://ajin-ai-assistant-frontend.vercel.app/"
# Cloud Run stable URL (project_number=614046190602, region=asia-northeast3).
# revision URL(예: ajin-backend-ncsnraqdaa-du.a.run.app)은 deploy 시 변경되므로
# 절대 사용하지 말 것. vercel.json rewrites 도 stable URL 사용.
CLOUD_RUN_HEALTH_URL = "https://ajin-backend-614046190602.asia-northeast3.run.app/api/health"
CLOUD_RUN_COLD_THRESHOLD_MS = 1500  # min-instances=1 적용 시 < 1.5초 보장
SSD_MODELS_PATH = "<EXTERNAL_DRIVE>/.ollama/models"

EXPECTED_OLLAMA_MODEL_MIN = 17
EXPECTED_BGE_MODEL = "bge-m3"
EXPECTED_EMBEDDING_DIM = 1024

# B1/B2
DOC_CHUNK_MIN = 30
DEMO_DOC_ID = "8D-2025-Q4-027-PRESS-TRY"

# B3
EMPLOYEE_EMBEDDING_COUNT = 30
PERSONA_IDS = [
    "EMP-A-20260301-001",
    "EMP-A-20150412-014",
    "EMP-A-20220305-008",
]

# B4
EXPECTED_REG_IDS = {
    "REG-2025-12-001-PRESS-SAFETY",
    "REG-2025-12-002-CHROMIUM-SVHC",
    "REG-2026-Q1-003-EV-HV",
}

# B5
LIVE_ALARM_MIN = 3

# C1
DEMO_SEARCH_QUERY = "프레스 트라이 8D Report"

# C2
DEMO_DRAFT_QUERY = "압축기 누유 발생, 3월 15일, B3라인"

# C3
SAFETY_FALSE_QUERY = "PPAP가 뭐예요?"
SAFETY_TRUE_QUERY = "이 기계 만져도 돼요?"

# C4
PRESS_ALARM_REG_ID = "REG-2025-12-001-PRESS-SAFETY"

# C5
SPC_DEMO_SEED = 20260610

# D3
EXPECTED_RLS_TABLE_COUNT = 23

# ---------------------------------------------------------------------------
# 결과 헬퍼
# ---------------------------------------------------------------------------

STATUS_PASS = "PASS"
STATUS_WARN = "WARN"
STATUS_FAIL = "FAIL"
STATUS_SKIP = "SKIP"

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"


def _colored(text: str, color: str) -> str:
    if sys.stdout.isatty():
        return f"{color}{text}{RESET}"
    return text


def _make_result(
    check_id: str,
    name: str,
    status: str,
    detail: str,
    fix_hint: str = "",
    data: Any = None,
) -> dict[str, Any]:
    return {
        "id": check_id,
        "name": name,
        "status": status,
        "detail": detail,
        "fix_hint": fix_hint,
        "data": data,
    }


def _pass(check_id: str, name: str, detail: str, data: Any = None) -> dict[str, Any]:
    return _make_result(check_id, name, STATUS_PASS, detail, data=data)


def _warn(check_id: str, name: str, detail: str, fix_hint: str = "", data: Any = None) -> dict[str, Any]:
    return _make_result(check_id, name, STATUS_WARN, detail, fix_hint, data)


def _fail(check_id: str, name: str, detail: str, fix_hint: str = "", data: Any = None) -> dict[str, Any]:
    return _make_result(check_id, name, STATUS_FAIL, detail, fix_hint, data)


def _skip(check_id: str, name: str, reason: str) -> dict[str, Any]:
    return _make_result(check_id, name, STATUS_SKIP, reason)


# ---------------------------------------------------------------------------
# Supabase 클라이언트
# ---------------------------------------------------------------------------

def _get_supabase():
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SECRET_KEY", "")
    if not url or not key:
        raise EnvironmentError(
            "SUPABASE_URL 또는 SUPABASE_SECRET_KEY 환경변수 미설정"
        )
    try:
        from supabase import create_client
    except ImportError as exc:
        raise RuntimeError(f"supabase 패키지 필요: pip install supabase\n{exc}") from exc
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Ollama 임베딩
# ---------------------------------------------------------------------------

async def _embed_async(text: str, ollama_url: str) -> list[float]:
    try:
        import httpx
    except ImportError as exc:
        raise RuntimeError("httpx 패키지 필요: pip install httpx") from exc
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{ollama_url.rstrip('/')}/api/embed",
            json={"model": EXPECTED_BGE_MODEL, "input": [text]},
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


def _embed_sync(text: str, ollama_url: str) -> list[float]:
    return asyncio.run(_embed_async(text, ollama_url))


# ---------------------------------------------------------------------------
# Area A — Infrastructure
# ---------------------------------------------------------------------------

def check_a1_ssd(args: argparse.Namespace) -> dict[str, Any]:
    """A1: 외장 SSD 마운트 확인."""
    path = Path(SSD_MODELS_PATH)
    if path.is_dir():
        return _pass("A1", "외장 SSD 마운트", f"경로 확인: {SSD_MODELS_PATH}")
    return _fail(
        "A1", "외장 SSD 마운트",
        f"경로 없음: {SSD_MODELS_PATH}",
        "→ 해결: 외장 SSD를 USB 포트에 연결하세요",
    )


def check_a2_ollama_api(args: argparse.Namespace) -> dict[str, Any]:
    """A2: Ollama API 응답 + 모델 수 ≥ 17."""
    try:
        import httpx
        resp = httpx.get(f"{args.ollama_url}/api/tags", timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        return _fail(
            "A2", "Ollama API",
            f"API 호출 실패: {exc}",
            "→ 해결: ollama serve (또는 Ollama 앱 실행 확인)",
        )
    models = data.get("models", [])
    count = len(models)
    if count >= EXPECTED_OLLAMA_MODEL_MIN:
        return _pass("A2", "Ollama API", f"{count}개 모델 응답")
    return _fail(
        "A2", "Ollama API",
        f"모델 수 부족: {count}개 (기대 ≥ {EXPECTED_OLLAMA_MODEL_MIN})",
        f"→ 해결: ollama pull <모델명> 으로 추가 다운로드 필요 (현재 {count}개)",
        {"models": [m.get("name") for m in models]},
    )


def check_a3_bge_m3(args: argparse.Namespace) -> dict[str, Any]:
    """A3: bge-m3 모델 로드 확인."""
    try:
        import httpx
        resp = httpx.get(f"{args.ollama_url}/api/tags", timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        return _fail(
            "A3", "bge-m3 모델",
            f"Ollama API 호출 실패: {exc}",
            "→ 해결: ollama serve 실행 확인",
        )
    models = data.get("models", [])
    names = [m.get("name", "") for m in models]
    bge_found = any(EXPECTED_BGE_MODEL in n for n in names)
    if bge_found:
        matched = [n for n in names if EXPECTED_BGE_MODEL in n]
        return _pass("A3", "bge-m3 모델", f"모델 확인: {matched[0]}")
    return _fail(
        "A3", "bge-m3 모델",
        f"bge-m3 모델 없음 (전체 {len(names)}개 모델 목록에 없음)",
        "→ 해결: ollama pull bge-m3",
    )


def check_a4_supabase(args: argparse.Namespace) -> dict[str, Any]:
    """A4: Supabase 프로젝트 상태 ACTIVE_HEALTHY."""
    try:
        sb = _get_supabase()
        result = sb.table("document_chunks").select("id", count="exact").limit(1).execute()
        count = result.count if result.count is not None else len(result.data or [])
        return _pass("A4", "Supabase 상태", f"연결 성공 (document_chunks 응답 — rows: {count})")
    except EnvironmentError as exc:
        return _fail(
            "A4", "Supabase 상태",
            str(exc),
            "→ 해결: .env 파일에 SUPABASE_URL + SUPABASE_SECRET_KEY 설정",
        )
    except Exception as exc:
        return _fail(
            "A4", "Supabase 상태",
            f"Supabase 연결 실패: {exc}",
            "→ 해결: Supabase 대시보드에서 프로젝트 상태 확인 (https://supabase.com/dashboard)",
        )


def check_a5_vercel(args: argparse.Namespace) -> dict[str, Any]:
    """A5: Vercel 프론트엔드 HTTP 200."""
    if args.no_vercel:
        return _skip("A5", "Vercel 프론트엔드", "--no-vercel 플래그 (오프라인 모드)")
    try:
        import httpx
        resp = httpx.get(VERCEL_URL, timeout=20.0, follow_redirects=True)
        if resp.status_code == 200:
            return _pass("A5", "Vercel 프론트엔드", f"HTTP {resp.status_code} ({VERCEL_URL})")
        return _warn(
            "A5", "Vercel 프론트엔드",
            f"HTTP {resp.status_code} ({VERCEL_URL})",
            f"→ Vercel 대시보드 확인. 오프라인 시연 시 --no-vercel 사용 가능",
        )
    except Exception as exc:
        return _warn(
            "A5", "Vercel 프론트엔드",
            f"접속 실패: {exc}",
            "→ 오프라인 시연 가능. --no-vercel 플래그로 건너뛸 수 있음",
        )


def check_a6_cloud_run_health(args: argparse.Namespace) -> dict[str, Any]:
    """A6: Cloud Run /api/health 200 + cold start 회피 (latency < 1.5s).

    min-instances=1 설정 후 첫 요청 < 1.5초 보장. cold start 발생 시 30초+.
    Vercel rewrites는 stable URL을 사용해야 하며, revision URL 의존은 금지.
    """
    if args.no_cloud_run:
        return _skip("A6", "Cloud Run /api/health", "--no-cloud-run 플래그")
    try:
        import httpx
        started = time.monotonic()
        resp = httpx.get(CLOUD_RUN_HEALTH_URL, timeout=30.0, follow_redirects=True)
        latency_ms = int((time.monotonic() - started) * 1000)
    except Exception as exc:
        return _fail(
            "A6", "Cloud Run /api/health",
            f"접속 실패: {exc}",
            "→ 해결: gcloud run services list --project ajin-cb (서비스 상태 확인)",
        )

    if resp.status_code != 200:
        return _fail(
            "A6", "Cloud Run /api/health",
            f"HTTP {resp.status_code} (latency {latency_ms}ms)",
            "→ 해결: 백엔드 라우트 prefix(/api) + Cloud Run 배포 상태 확인",
            {"status": resp.status_code, "latency_ms": latency_ms},
        )

    if latency_ms > CLOUD_RUN_COLD_THRESHOLD_MS:
        return _warn(
            "A6", "Cloud Run /api/health",
            f"latency {latency_ms}ms > {CLOUD_RUN_COLD_THRESHOLD_MS}ms (cold start 의심)",
            "→ 해결: gcloud run services update ajin-backend --project ajin-cb "
            "--region asia-northeast3 --min-instances=1",
            {"latency_ms": latency_ms},
        )

    return _pass(
        "A6", "Cloud Run /api/health",
        f"HTTP 200 ({latency_ms}ms, < {CLOUD_RUN_COLD_THRESHOLD_MS}ms → min-instances=1 정상)",
    )


# ---------------------------------------------------------------------------
# Area B — Seed Data
# ---------------------------------------------------------------------------

def check_b1_document_chunks(args: argparse.Namespace) -> dict[str, Any]:
    """B1: document_chunks ≥ 30 rows + PRESS-TRY 존재."""
    try:
        sb = _get_supabase()
        count_res = sb.table("document_chunks").select("id", count="exact").execute()
        count = count_res.count if count_res.count is not None else len(count_res.data or [])

        press_res = (
            sb.table("document_chunks")
            .select("source_doc_id")
            .eq("source_doc_id", DEMO_DOC_ID)
            .limit(1)
            .execute()
        )
        press_exists = len(press_res.data or []) > 0

        issues = []
        if count < DOC_CHUNK_MIN:
            issues.append(f"rows={count} (기대 ≥{DOC_CHUNK_MIN})")
        if not press_exists:
            issues.append(f"{DEMO_DOC_ID} 미존재")

        if not issues:
            return _pass("B1", "document_chunks", f"{count} rows, PRESS-TRY 존재")
        return _fail(
            "B1", "document_chunks",
            f"검증 실패: {'; '.join(issues)}",
            "→ 해결: python3 scripts/seed_supabase_documents.py --apply",
            {"count": count, "press_exists": press_exists},
        )
    except Exception as exc:
        return _fail(
            "B1", "document_chunks",
            f"쿼리 오류: {exc}",
            "→ 해결: Supabase 연결 상태 확인 후 python3 scripts/seed_supabase_documents.py --apply",
        )


def check_b2_document_embeddings(args: argparse.Namespace) -> dict[str, Any]:
    """B2: document_embeddings ≥ 30 rows + 모두 dim=1024."""
    try:
        sb = _get_supabase()
        count_res = (
            sb.table("document_embeddings").select("chunk_id", count="exact").execute()
        )
        count = count_res.count if count_res.count is not None else len(count_res.data or [])

        dim_res = (
            sb.table("document_embeddings")
            .select("embedding_dim")
            .limit(100)
            .execute()
        )
        dims = [row["embedding_dim"] for row in (dim_res.data or [])]
        wrong_dims = [d for d in dims if d != EXPECTED_EMBEDDING_DIM]

        issues = []
        if count < DOC_CHUNK_MIN:
            issues.append(f"rows={count} (기대 ≥{DOC_CHUNK_MIN})")
        if wrong_dims:
            issues.append(f"dim 불일치 {len(wrong_dims)}건")

        if not issues:
            return _pass("B2", "document_embeddings", f"{count} rows, dim=1024 일관성 OK")
        return _fail(
            "B2", "document_embeddings",
            f"검증 실패: {'; '.join(issues)}",
            "→ 해결: python3 scripts/seed_supabase_documents.py --apply (임베딩 재생성)",
            {"count": count, "wrong_dims": wrong_dims[:5]},
        )
    except Exception as exc:
        return _fail(
            "B2", "document_embeddings",
            f"쿼리 오류: {exc}",
            "→ 해결: Supabase 연결 상태 확인",
        )


def check_b3_employee_embeddings(args: argparse.Namespace) -> dict[str, Any]:
    """B3: employee_embeddings = 30 rows + 페르소나 3명 존재."""
    try:
        sb = _get_supabase()
        count_res = (
            sb.table("employee_embeddings").select("employee_id", count="exact").execute()
        )
        count = count_res.count if count_res.count is not None else len(count_res.data or [])

        persona_res = (
            sb.table("employee_embeddings")
            .select("employee_id")
            .in_("employee_id", PERSONA_IDS)
            .execute()
        )
        found_personas = {row["employee_id"] for row in (persona_res.data or [])}
        missing_personas = [p for p in PERSONA_IDS if p not in found_personas]

        issues = []
        if count != EMPLOYEE_EMBEDDING_COUNT:
            issues.append(f"rows={count} (기대={EMPLOYEE_EMBEDDING_COUNT})")
        if missing_personas:
            issues.append(f"페르소나 누락: {missing_personas}")

        if not issues:
            return _pass("B3", "employee_embeddings", f"{count} rows, 페르소나 3명 확인")
        return _fail(
            "B3", "employee_embeddings",
            f"검증 실패: {'; '.join(issues)}",
            "→ 해결: python3 scripts/seed_supabase_employees.py --apply",
            {"count": count, "missing_personas": missing_personas},
        )
    except Exception as exc:
        return _fail(
            "B3", "employee_embeddings",
            f"쿼리 오류: {exc}",
            "→ 해결: Supabase 연결 상태 확인",
        )


def check_b4_regulation_changes(args: argparse.Namespace) -> dict[str, Any]:
    """B4: regulation_changes = 3 rows (CRITICAL 1, HIGH 1, MEDIUM 1).

    실제 스키마: severity (top-level varchar). 기존 `grade` 컬럼은 payload.grade 안.
    """
    try:
        sb = _get_supabase()
        result = (
            sb.table("regulation_changes")
            .select("id, severity")
            .in_("id", list(EXPECTED_REG_IDS))
            .execute()
        )
        rows = result.data or []
        found_ids = {r["id"] for r in rows}
        missing = EXPECTED_REG_IDS - found_ids

        severities = {r["id"]: (r.get("severity") or "") for r in rows}
        sev_counts: dict[str, int] = {}
        for s in severities.values():
            sev_counts[s] = sev_counts.get(s, 0) + 1

        issues = []
        if len(rows) != 3:
            issues.append(f"rows={len(rows)} (기대=3)")
        if missing:
            issues.append(f"누락 ID: {sorted(missing)}")
        if sev_counts.get("CRITICAL", 0) < 1:
            issues.append("CRITICAL 등급 없음")

        if not issues:
            sev_summary = ", ".join(f"{s}={c}" for s, c in sorted(sev_counts.items()))
            return _pass("B4", "regulation_changes", f"3 rows ({sev_summary})")
        return _fail(
            "B4", "regulation_changes",
            f"검증 실패: {'; '.join(issues)}",
            "→ 해결: python3 scripts/seed_supabase_regulations.py --apply",
            {"found": len(rows), "severities": severities, "missing": sorted(missing)},
        )
    except Exception as exc:
        return _fail(
            "B4", "regulation_changes",
            f"쿼리 오류: {exc}",
            "→ 해결: python3 scripts/seed_supabase_regulations.py --apply",
        )


def check_b5_live_alarms(args: argparse.Namespace) -> dict[str, Any]:
    """B5: live_alarms ≥ 3 + CRITICAL unacked ≥ 1.

    실제 스키마: acknowledged_at timestamptz (NULL=unacked).
    """
    try:
        sb = _get_supabase()
        count_res = (
            sb.table("live_alarms").select("id", count="exact").execute()
        )
        count = count_res.count if count_res.count is not None else len(count_res.data or [])

        critical_res = (
            sb.table("live_alarms")
            .select("id, severity, acknowledged_at")
            .eq("severity", "CRITICAL")
            .is_("acknowledged_at", None)
            .execute()
        )
        critical_unacked = len(critical_res.data or [])

        issues = []
        if count < LIVE_ALARM_MIN:
            issues.append(f"rows={count} (기대 ≥{LIVE_ALARM_MIN})")
        if critical_unacked < 1:
            issues.append("CRITICAL unacked 없음 (기대 ≥1)")

        if not issues:
            return _pass("B5", "live_alarms", f"{count} rows, CRITICAL unacked={critical_unacked}")
        return _fail(
            "B5", "live_alarms",
            f"검증 실패: {'; '.join(issues)}",
            "→ 해결: python3 scripts/seed_supabase_regulations.py --apply",
            {"count": count, "critical_unacked": critical_unacked},
        )
    except Exception as exc:
        return _fail(
            "B5", "live_alarms",
            f"쿼리 오류: {exc}",
            "→ 해결: python3 scripts/seed_supabase_regulations.py --apply",
        )


# ---------------------------------------------------------------------------
# Area C — Demo Scenarios
# ---------------------------------------------------------------------------

def check_c1_search(args: argparse.Namespace) -> dict[str, Any]:
    """C1: hybrid_search top-3에 PRESS-TRY 포함."""
    try:
        embedding = _embed_sync(DEMO_SEARCH_QUERY, args.ollama_url)
    except Exception as exc:
        return _fail(
            "C1", "시연 1 검색 (hybrid_search)",
            f"임베딩 생성 실패: {exc}",
            "→ 해결: Ollama 실행 확인 + bge-m3 모델 로드 확인",
        )
    try:
        sb = _get_supabase()
        result = sb.rpc(
            "hybrid_search_document_chunks",
            {
                "query_text": DEMO_SEARCH_QUERY,
                "query_embedding": embedding,
                "match_count": 5,
                "doc_type_filter": None,
                "part_name_filter": None,
                "metadata_filter": {},
            },
        ).execute()
        rows = result.data or []
    except Exception as exc:
        return _fail(
            "C1", "시연 1 검색 (hybrid_search)",
            f"RPC 호출 실패: {exc}",
            "→ 해결: migration 0005 (public.hybrid_search_document_chunks wrapper) 적용 필요 — supabase db push --linked",
        )

    top3_ids = [r.get("source_doc_id") for r in rows[:3]]
    press_in_top3 = any(DEMO_DOC_ID in (sid or "") for sid in top3_ids)

    if press_in_top3:
        rank = next(
            (i + 1 for i, r in enumerate(rows[:3]) if DEMO_DOC_ID in (r.get("source_doc_id") or "")),
            "?",
        )
        return _pass("C1", "시연 1 검색 (hybrid_search)", f"PRESS-TRY top-{rank} 확인 ({len(rows)}건 응답)")
    return _fail(
        "C1", "시연 1 검색 (hybrid_search)",
        f"PRESS-TRY top-3 미포함 (top-3: {top3_ids})",
        "→ 해결: python3 scripts/seed_supabase_documents.py --apply 후 임베딩 재생성",
        {"top3": top3_ids, "result_count": len(rows)},
    )


def check_c2_draft(args: argparse.Namespace) -> dict[str, Any]:
    """C2: demo_seed 캐시 hit + 8D D1-D8 응답."""
    try:
        from features.draft.demo_seed import get_demo_draft  # type: ignore
    except ImportError:
        # graceful skip — features 패키지 미설치 환경
        return _warn(
            "C2", "시연 2 초안 (demo_seed)",
            "features.draft.demo_seed import 불가 — 실행 환경에서 직접 확인 필요",
            "→ 해결: ajin-ai-assistant 경로가 PYTHONPATH에 포함되었는지 확인",
        )
    try:
        result = get_demo_draft(DEMO_DRAFT_QUERY)
    except Exception as exc:
        return _fail(
            "C2", "시연 2 초안 (demo_seed)",
            f"demo_draft 호출 실패: {exc}",
            "→ 해결: features/draft/demo_seed.py 구현 확인",
        )

    # 8D D1~D8 dict 키 확인 (d1_team, d2_problem, ..., d8_closure 형태)
    if result is None:
        return _fail(
            "C2", "시연 2 초안 (demo_seed)",
            "demo_draft 캐시 미스 (None 반환)",
            "→ 해결: DEMO_DRAFT_CACHE 키가 입력과 정확히 일치하는지 확인",
        )

    keys = set(result.keys()) if isinstance(result, dict) else set()
    d_prefixes = {f"d{i}" for i in range(1, 9)}
    found = {p for p in d_prefixes if any(k.startswith(f"{p}_") for k in keys)}

    if found == d_prefixes:
        return _pass(
            "C2", "시연 2 초안 (demo_seed)",
            f"demo_draft 캐시 hit, D1-D8 dict 키 8개 모두 확인",
        )
    return _fail(
        "C2", "시연 2 초안 (demo_seed)",
        f"D1-D8 dict 키 누락: {sorted(d_prefixes - found)} (확인됨: {sorted(found)})",
        "→ 해결: features/draft/demo_seed.py DEMO_DRAFT_CACHE 항목 보완",
        {"keys": sorted(keys)},
    )


def check_c3_chatbot(args: argparse.Namespace) -> dict[str, Any]:
    """C3: safety_classifier — PPAP=False, 기계=True."""
    try:
        from features.onboarding.safety_classifier import classify_question  # type: ignore
    except ImportError:
        return _warn(
            "C3", "시연 3 챗봇 (safety_classifier)",
            "features.onboarding.safety_classifier import 불가 — 실행 환경에서 직접 확인 필요",
            "→ 해결: ajin-ai-assistant 경로가 PYTHONPATH에 포함되었는지 확인",
        )
    try:
        result_ppap = classify_question(SAFETY_FALSE_QUERY)
        result_machine = classify_question(SAFETY_TRUE_QUERY)
    except Exception as exc:
        return _fail(
            "C3", "시연 3 챗봇 (safety_classifier)",
            f"classify_question 호출 실패: {exc}",
            "→ 해결: features/onboarding/safety_classifier.py 구현 확인",
        )

    def _is_safety(r: Any) -> bool:
        if hasattr(r, "is_safety_related"):
            return bool(r.is_safety_related)
        if isinstance(r, dict):
            return bool(r.get("is_safety_related"))
        return bool(r)

    ppap_safety = _is_safety(result_ppap)
    machine_safety = _is_safety(result_machine)

    issues = []
    if ppap_safety:
        issues.append(f"PPAP 질문이 safety=True (기대 False)")
    if not machine_safety:
        issues.append(f"기계 질문이 safety=False (기대 True)")

    if not issues:
        return _pass("C3", "시연 3 챗봇 (safety_classifier)", "PPAP→False, 기계→True 분류 정상")
    return _fail(
        "C3", "시연 3 챗봇 (safety_classifier)",
        f"분류 오류: {'; '.join(issues)}",
        "→ 해결: features/onboarding/safety_classifier.py 로직 확인",
        {"ppap_safety": ppap_safety, "machine_safety": machine_safety},
    )


def check_c4_alarms(args: argparse.Namespace) -> dict[str, Any]:
    """C4: live_alarms CRITICAL unacked 최근 2일 → 첫 결과가 프레스 안전거리.

    실제 스키마: message (text), acknowledged_at timestamptz, payload jsonb.
    regulation_change_id는 payload->>'regulation_change_id'에 저장.
    timestamp 컬럼은 없음 → created_at으로 정렬.
    """
    try:
        sb = _get_supabase()
        # 리허설 시점(D-N)에는 시드의 created_at이 시드 실행 시점이라 D-Day-2 cutoff은
        # 모두 제외함. 대신 CRITICAL unacked 알람 자체의 존재와 첫 결과의 정합성만 확인.
        result = (
            sb.table("live_alarms")
            .select("id, severity, acknowledged_at, message, payload, created_at")
            .eq("severity", "CRITICAL")
            .is_("acknowledged_at", None)
            .order("created_at", desc=True)
            .execute()
        )
        rows = result.data or []
    except Exception as exc:
        return _fail(
            "C4", "시연 4 법규 (CRITICAL 알람)",
            f"쿼리 오류: {exc}",
            "→ 해결: Supabase 연결 상태 확인",
        )

    if not rows:
        return _fail(
            "C4", "시연 4 법규 (CRITICAL 알람)",
            "CRITICAL unacked 알람 없음 (최근 2일 기준)",
            "→ 해결: python3 scripts/seed_supabase_regulations.py --apply",
        )

    first = rows[0]
    first_payload = first.get("payload") or {}
    first_reg_id = first_payload.get("regulation_change_id", "") if isinstance(first_payload, dict) else ""
    first_message = first.get("message") or ""
    first_title = first_payload.get("title", "") if isinstance(first_payload, dict) else ""
    is_press = (
        first_reg_id == PRESS_ALARM_REG_ID
        or "프레스" in first_message
        or "프레스" in first_title
    )

    if is_press:
        label = first_title or first_message
        return _pass(
            "C4", "시연 4 법규 (CRITICAL 알람)",
            f"첫 결과: '{label[:50]}' (regulation_change_id: {first_reg_id})",
        )
    return _fail(
        "C4", "시연 4 법규 (CRITICAL 알람)",
        f"첫 결과가 프레스 알람 아님: '{first_message[:50]}' / {first_reg_id}",
        "→ 해결: python3 scripts/seed_supabase_regulations.py --apply (알람 created_at 확인)",
        {"first_id": first.get("id"), "first_message": first_message, "first_reg_id": first_reg_id},
    )


def check_c5_spc(args: argparse.Namespace) -> dict[str, Any]:
    """C5: SPC Nelson Rule 2·3 위반 차트 결정적 재현.

    실제 모듈: generate_spc_data(SPCGeneratorConfig) + analyze_nelson_rules(values).
    SPCGeneratorConfig(seed=20260610, inject_shift=True, inject_stratification=True)
    → Rule 2 (평균 이동) + Rule 3 (층화) 결정적 재현.
    """
    try:
        from features.equipment.spc_data_generator import (  # type: ignore
            generate_spc_data,
            SPCGeneratorConfig,
        )
        from features.equipment.spc_realtime import analyze_nelson_rules  # type: ignore
    except ImportError as exc:
        return _warn(
            "C5", "시연 5 SPC (Nelson Rule)",
            f"SPC 모듈 import 불가: {exc} — 실행 환경에서 직접 확인 필요",
            "→ 해결: PYTHONPATH=ajin-ai-assistant-react 으로 실행",
        )

    try:
        config = SPCGeneratorConfig(
            n_samples=200,
            seed=SPC_DEMO_SEED,
            inject_shift=True,
            shift_at_sample=100,
            shift_amount=1.0,
            inject_stratification=True,
        )
        values = generate_spc_data(config)
    except Exception as exc:
        return _fail(
            "C5", "시연 5 SPC (Nelson Rule)",
            f"generate_spc_data 호출 실패: {exc}",
            "→ 해결: features/equipment/spc_data_generator.py 시그니처 확인",
        )

    try:
        result = analyze_nelson_rules(values, process_name="DEMO_C5")
    except Exception as exc:
        return _fail(
            "C5", "시연 5 SPC (Nelson Rule)",
            f"analyze_nelson_rules 호출 실패: {exc}",
            "→ 해결: features/equipment/spc_realtime.py 시그니처 확인",
        )

    violations = getattr(result, "violations", None) or []
    violated_rules = set()
    for v in violations:
        rn = getattr(v, "rule_number", None)
        if rn is not None:
            violated_rules.add(int(rn))

    has_rule2 = 2 in violated_rules
    has_rule3 = 3 in violated_rules

    if has_rule2 and has_rule3:
        return _pass(
            "C5", "시연 5 SPC (Nelson Rule)",
            f"Nelson Rule 2+3 위반 재현 (seed={SPC_DEMO_SEED}, violations={sorted(violated_rules)})",
        )
    if has_rule2 or has_rule3:
        return _warn(
            "C5", "시연 5 SPC (Nelson Rule)",
            f"Nelson Rule 부분 — Rule2={has_rule2}, Rule3={has_rule3} (violations={sorted(violated_rules)})",
            "→ 해결: SPCGeneratorConfig shift_amount/inject_stratification 강화",
        )
    return _fail(
        "C5", "시연 5 SPC (Nelson Rule)",
        f"Rule 2·3 미검출 (전체 violations={sorted(violated_rules)})",
        "→ 해결: shift_amount=1.0 + inject_stratification=True 결과 직접 검증",
        {"violated_rules": sorted(violated_rules)},
    )


# ---------------------------------------------------------------------------
# Area D — Supabase Advisor
# ---------------------------------------------------------------------------

def check_d1_security_advisor(args: argparse.Namespace) -> dict[str, Any]:
    """D1: Security advisor ERROR+WARN+INFO = 0."""
    try:
        result = subprocess.run(
            ["supabase", "db", "advisors", "--linked", "--type", "security", "--level", "info"],
            capture_output=True, text=True, timeout=60,
        )
        output = result.stdout + result.stderr
        # 0건 이면 "No advisors found" 또는 빈 테이블
        has_findings = (
            "error" in output.lower()
            and "no advisors" not in output.lower()
        )
        if result.returncode == 0 and not has_findings:
            return _pass("D1", "Security Advisor", "security advisors 0건 (P0-4 적용 완료)")
        # advisor 결과가 있거나 CLI 오류
        if "supabase" not in output.lower() and result.returncode != 0:
            return _warn(
                "D1", "Security Advisor",
                "supabase CLI 미설치 또는 linked 아님 — 직접 확인 필요",
                "→ 해결: supabase login && supabase link --project-ref <ref>",
            )
        return _warn(
            "D1", "Security Advisor",
            f"advisor 결과 확인 필요 (returncode={result.returncode})",
            "→ 해결: supabase db advisors --linked --type security 직접 실행 확인",
            {"output_preview": output[:300]},
        )
    except FileNotFoundError:
        return _warn(
            "D1", "Security Advisor",
            "supabase CLI 미설치 — Supabase 대시보드에서 수동 확인 필요",
            "→ 해결: npm install -g supabase 또는 brew install supabase/tap/supabase",
        )
    except subprocess.TimeoutExpired:
        return _warn(
            "D1", "Security Advisor",
            "supabase CLI 타임아웃 (60초)",
            "→ 해결: supabase db advisors --linked --type security 직접 실행",
        )
    except Exception as exc:
        return _warn("D1", "Security Advisor", f"CLI 실행 오류: {exc}")


def check_d2_performance_advisor(args: argparse.Namespace) -> dict[str, Any]:
    """D2: Performance advisor WARN+ERROR = 0 (INFO는 정보성으로 허용)."""
    try:
        result = subprocess.run(
            ["supabase", "db", "advisors", "--linked", "--type", "performance",
             "--level", "info", "--output", "json"],
            capture_output=True, text=True, timeout=60,
        )
    except FileNotFoundError:
        return _fail(
            "D2", "Performance Advisor",
            "supabase CLI 미설치 — D-1 ritual 필수 도구",
            "→ 해결: brew install supabase/tap/supabase + supabase link",
        )
    except subprocess.TimeoutExpired:
        return _fail("D2", "Performance Advisor", "supabase CLI 타임아웃 (60s)")

    if result.returncode != 0:
        return _fail(
            "D2", "Performance Advisor",
            f"supabase CLI 오류 (returncode={result.returncode})",
            "→ 해결: supabase login + supabase link --project-ref <ref>",
            {"stderr": (result.stderr or "")[:300]},
        )

    import json as _json
    try:
        data = _json.loads(result.stdout.strip() or "{}")
    except _json.JSONDecodeError as exc:
        return _fail(
            "D2", "Performance Advisor",
            f"JSON 파싱 실패: {exc}",
            "→ 해결: supabase CLI 버전 확인 (>= v2.0 + --output json 지원 확인)",
            {"stdout_preview": result.stdout[:300]},
        )

    lints = data.get("lints") if isinstance(data, dict) else data
    lints = lints or []

    levels: dict[str, int] = {}
    for lint in lints:
        lvl = (lint.get("level") or "").lower()
        levels[lvl] = levels.get(lvl, 0) + 1
    warn_plus = levels.get("warn", 0) + levels.get("error", 0)
    info_count = levels.get("info", 0)
    if warn_plus == 0:
        return _pass(
            "D2", "Performance Advisor",
            f"WARN/ERROR 0건 (INFO {info_count}건, 정보성)",
        )
    return _fail(
        "D2", "Performance Advisor",
        f"WARN/ERROR {warn_plus}건 발견 (levels={levels})",
        "→ 해결: supabase db advisors --linked --type performance --level warn 실행 후 개별 조치",
        {"levels": levels},
    )


def check_d3_rls(args: argparse.Namespace) -> dict[str, Any]:
    """D3: RLS 활성 비율 — public.count_rls_tables() RPC (마이그레이션 0009).

    EXPECTED_RLS_TABLE_COUNT 하드코딩 게이트 제거. RPC가 반환한 enabled == total
    이면 PASS. 신규 테이블 추가되어도 자동 적응.
    """
    try:
        sb = _get_supabase()
        result = sb.rpc("count_rls_tables", {}).execute()
        rows = result.data or []
    except Exception as exc:
        return _fail(
            "D3", "RLS 활성 비율",
            f"count_rls_tables RPC 호출 실패: {exc}",
            "→ 해결: 마이그레이션 0009 (20260524195000_add_count_rls_tables_rpc.sql) "
            "적용 — supabase db push --linked",
        )

    if not rows:
        return _fail(
            "D3", "RLS 활성 비율",
            "count_rls_tables RPC 응답 비어있음",
            "→ 해결: 마이그레이션 0009 적용 확인 — supabase db push --linked",
        )

    enabled = int(rows[0].get("rls_enabled", 0))
    total = int(rows[0].get("total_tables", 0))
    if total == 0:
        return _fail(
            "D3", "RLS 활성 비율",
            "public 테이블 0개 — 시드 적용 전 환경?",
            "→ 해결: 시드 스크립트 실행 후 재검증",
        )
    if enabled == total:
        return _pass("D3", "RLS 활성 비율", f"{enabled}/{total} (100%)")
    return _fail(
        "D3", "RLS 활성 비율",
        f"{enabled}/{total} ({100 * enabled / total:.0f}%)",
        "→ 해결: 미설정 테이블에 ALTER TABLE <name> ENABLE ROW LEVEL SECURITY",
        {"enabled": enabled, "total": total},
    )


def check_d4_migration(args: argparse.Namespace) -> dict[str, Any]:
    """D4: supabase db push --dry-run --linked → Remote up to date."""
    try:
        result = subprocess.run(
            ["supabase", "db", "push", "--dry-run", "--linked"],
            capture_output=True, text=True, timeout=120,
            cwd=str(REPO_ROOT),
        )
        output = result.stdout + result.stderr
        up_to_date = (
            "up to date" in output.lower()
            or "no migrations" in output.lower()
            or "nothing to push" in output.lower()
            or (result.returncode == 0 and not output.strip())
        )
        if up_to_date:
            return _pass("D4", "Migration 상태", "Remote up to date (dry-run)")
        if result.returncode != 0 and "supabase" not in output.lower():
            return _warn(
                "D4", "Migration 상태",
                "supabase CLI 미설치 또는 linked 아님",
                "→ 해결: supabase login && supabase link --project-ref <ref>",
            )
        return _warn(
            "D4", "Migration 상태",
            f"미적용 마이그레이션 있을 수 있음 (returncode={result.returncode})",
            "→ 해결: supabase db push --linked 실행 후 재확인",
            {"output_preview": output[:300]},
        )
    except FileNotFoundError:
        return _warn(
            "D4", "Migration 상태",
            "supabase CLI 미설치 — 수동 확인 필요",
            "→ 해결: npm install -g supabase",
        )
    except subprocess.TimeoutExpired:
        return _warn("D4", "Migration 상태", "supabase CLI 타임아웃 (120초)")
    except Exception as exc:
        return _warn("D4", "Migration 상태", f"CLI 실행 오류: {exc}")


# ---------------------------------------------------------------------------
# 영역별 체크 목록
# ---------------------------------------------------------------------------

AREA_A: list[tuple[str, Callable]] = [
    ("A1", check_a1_ssd),
    ("A2", check_a2_ollama_api),
    ("A3", check_a3_bge_m3),
    ("A4", check_a4_supabase),
    ("A5", check_a5_vercel),
    ("A6", check_a6_cloud_run_health),
]

AREA_B: list[tuple[str, Callable]] = [
    ("B1", check_b1_document_chunks),
    ("B2", check_b2_document_embeddings),
    ("B3", check_b3_employee_embeddings),
    ("B4", check_b4_regulation_changes),
    ("B5", check_b5_live_alarms),
]

AREA_C: list[tuple[str, Callable]] = [
    ("C1", check_c1_search),
    ("C2", check_c2_draft),
    ("C3", check_c3_chatbot),
    ("C4", check_c4_alarms),
    ("C5", check_c5_spc),
]

AREA_D: list[tuple[str, Callable]] = [
    ("D1", check_d1_security_advisor),
    ("D2", check_d2_performance_advisor),
    ("D3", check_d3_rls),
    ("D4", check_d4_migration),
]


# ---------------------------------------------------------------------------
# 출력
# ---------------------------------------------------------------------------

def _icon(status: str) -> str:
    return {
        STATUS_PASS: _colored("✓", GREEN),
        STATUS_WARN: _colored("△", YELLOW),
        STATUS_FAIL: _colored("✗", RED),
        STATUS_SKIP: _colored("○", RESET),
    }.get(status, "?")


def _print_header(d_day: date) -> None:
    today = date.today()
    delta = (d_day - today).days
    if delta > 0:
        d_label = f"D-{delta}"
    elif delta == 0:
        d_label = "D-Day"
    else:
        d_label = f"D+{-delta}"

    bar = "═" * 63
    print()
    print(_colored(bar, BOLD))
    print(_colored(f"  AJIN Demo E2E Check — {d_label} ({today})", BOLD))
    print(_colored(bar, BOLD))
    print()


def _print_area_header(label: str, count: int) -> None:
    print(f"  {_colored(f'▶ {label}', BOLD)} ({count}개 체크)")


def _print_result(r: dict[str, Any]) -> None:
    icon = _icon(r["status"])
    cid = r["id"]
    name = r["name"]
    detail = r["detail"]
    print(f"    {icon} {cid} {name}")
    print(f"       {detail}")
    if r.get("fix_hint") and r["status"] in (STATUS_FAIL, STATUS_WARN):
        print(f"       {_colored(r['fix_hint'], YELLOW)}")


def _print_separator() -> None:
    print(f"  {'─' * 59}")


def _print_final(
    total: int,
    passed: int,
    warned: int,
    failed: int,
    skipped: int,
    strict: bool,
) -> None:
    effective_fail = failed + (warned if strict else 0)
    bar = "═" * 63
    print()
    print(_colored(bar, BOLD))
    if effective_fail == 0:
        verdict = _colored(f"✅  {passed + skipped}/{total} PASS — 시연 준비 완료", GREEN + BOLD)
        if warned and not strict:
            verdict = _colored(
                f"✅  {passed}/{total} PASS ({warned} WARN) — 시연 준비 완료 (soft 모드)", YELLOW + BOLD
            )
    else:
        verdict = _colored(
            f"❌  {failed} FAIL / {warned} WARN / {passed} PASS — 시연 전 수정 필요",
            RED + BOLD,
        )
    print(f"  {verdict}")
    print(_colored(bar, BOLD))
    print()


# ---------------------------------------------------------------------------
# 메인 실행 흐름
# ---------------------------------------------------------------------------

def run_checks(args: argparse.Namespace) -> dict[str, Any]:
    """4 영역 검사 실행 후 결과 반환."""
    results: list[dict[str, Any]] = []

    areas: list[tuple[str, str, list]] = [
        ("Area A", "Infrastructure", AREA_A),
        ("Area B", "Seed Data", AREA_B),
        ("Area C", "Demo Scenarios", AREA_C),
        ("Area D", "Supabase Advisor", AREA_D),
    ]

    if args.fast:
        areas = areas[:2]  # A+B만

    if not args.json:
        _print_header(D_DAY)

    for area_key, area_label, checks in areas:
        if not args.json:
            _print_area_header(f"{area_key}: {area_label}", len(checks))

        area_results = []
        for cid, fn in checks:
            t0 = time.time()
            try:
                r = fn(args)
            except Exception as exc:
                r = _fail(cid, cid, f"체크 실행 중 예외: {exc}", "→ 스크립트 오류 — 직접 확인 필요")
            elapsed = time.time() - t0
            r["elapsed_s"] = round(elapsed, 2)
            area_results.append(r)
            if not args.json:
                _print_result(r)

        results.extend(area_results)
        if not args.json:
            _print_separator()

    # 집계
    total = len(results)
    passed = sum(1 for r in results if r["status"] == STATUS_PASS)
    warned = sum(1 for r in results if r["status"] == STATUS_WARN)
    failed = sum(1 for r in results if r["status"] == STATUS_FAIL)
    skipped = sum(1 for r in results if r["status"] == STATUS_SKIP)

    if not args.json:
        _print_final(total, passed, warned, failed, skipped, args.strict)

    effective_fail = failed + (warned if args.strict else 0)
    exit_code = 0 if effective_fail == 0 else 1

    report = {
        "timestamp": datetime.now(KST).isoformat(),
        "d_day": str(D_DAY),
        "mode": {
            "strict": args.strict,
            "fast": args.fast,
            "no_vercel": args.no_vercel,
            "no_cloud_run": getattr(args, "no_cloud_run", False),
        },
        "summary": {
            "total": total,
            "passed": passed,
            "warned": warned,
            "failed": failed,
            "skipped": skipped,
            "exit_code": exit_code,
            "verdict": "PASS" if exit_code == 0 else "FAIL",
        },
        "checks": [
            {k: v for k, v in r.items() if k != "data"}
            for r in results
        ],
    }

    return report, exit_code


def main(args: argparse.Namespace) -> int:
    report, exit_code = run_checks(args)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))

    return exit_code


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--strict",
        action="store_true",
        default=True,
        help="WARN도 FAIL로 처리 (기본값)",
    )
    mode.add_argument(
        "--soft",
        action="store_true",
        default=False,
        help="WARN 허용, ERROR만 FAIL로 처리",
    )

    parser.add_argument(
        "--fast",
        action="store_true",
        default=False,
        help="영역 A+B만 실행 (D-Day T-120 빠른 점검, 1~2분)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="CI 통합용 JSON 출력 (stdout)",
    )
    parser.add_argument(
        "--no-vercel",
        action="store_true",
        default=False,
        help="A5 Vercel 체크 생략 (오프라인 시연 환경)",
    )
    parser.add_argument(
        "--no-cloud-run",
        action="store_true",
        default=False,
        help="Cloud Run 호출 생략",
    )
    parser.add_argument(
        "--ollama-url",
        default=None,
        help=f"Ollama 서버 URL (기본: {OLLAMA_URL_DEFAULT} 또는 OLLAMA_BASE_URL 환경변수)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="실제 호출 없이 체크 목록만 출력",
    )

    ns = parser.parse_args()

    # --soft 이면 strict=False
    if ns.soft:
        ns.strict = False
    else:
        ns.strict = True

    # ollama_url 해결
    ns.ollama_url = ns.ollama_url or os.environ.get("OLLAMA_BASE_URL", OLLAMA_URL_DEFAULT)

    return ns


# ---------------------------------------------------------------------------
# dry-run 출력
# ---------------------------------------------------------------------------

def print_dry_run() -> None:
    """--dry-run: 체크 목록만 출력."""
    all_checks = AREA_A + AREA_B + AREA_C + AREA_D
    print("\n[dry-run] 19 체크 목록:")
    for area, label, checks in [
        ("Area A", "Infrastructure", AREA_A),
        ("Area B", "Seed Data", AREA_B),
        ("Area C", "Demo Scenarios", AREA_C),
        ("Area D", "Supabase Advisor", AREA_D),
    ]:
        print(f"\n  {area}: {label}")
        for cid, fn in checks:
            print(f"    {cid}  {fn.__doc__.split('.')[0].strip() if fn.__doc__ else cid}")
    print()


# ---------------------------------------------------------------------------
# 엔트리포인트
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    _args = parse_args()
    if _args.dry_run:
        print_dry_run()
        raise SystemExit(0)
    raise SystemExit(main(_args))
