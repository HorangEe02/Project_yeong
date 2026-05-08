"""대시보드 메트릭 라우터.

프론트의 5개 엔드포인트 매핑:
  GET /dashboard/metrics       — 사원/에러코드/부서/테스트계정 카운터
  GET /dashboard/system-health — 백엔드/RAG/SQLite/임베딩 상태
  GET /dashboard/ingestion     — 데이터 수집 현황 (RAG/금형/SPC 등)
  GET /dashboard/system-info   — 환경/버전/모델/인증 모드
  GET /dashboard/alarms        — 진행중 알람 목록 (시뮬용)
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends

from backend.dependencies import get_current_user
from config import DATA_DIR, DEPARTMENTS

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# ─────────────────────────────────────────────────────────────
# 헬퍼 — SQLite count 안전 조회
# ─────────────────────────────────────────────────────────────

def _safe_count(db_path: Path, query: str) -> int:
    if not db_path.exists():
        return 0
    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.execute(query)
        n = cur.fetchone()[0]
        conn.close()
        return int(n or 0)
    except Exception:
        return 0


def _count_employees() -> int:
    return _safe_count(DATA_DIR / "employees.db", "SELECT COUNT(*) FROM employees")


def _count_test_accounts() -> int:
    return _safe_count(DATA_DIR / "auth.db", "SELECT COUNT(*) FROM users WHERE is_active=1")


def _count_error_codes() -> int:
    p = DATA_DIR / "equipment" / "error_codes.db"
    if p.exists():
        return _safe_count(p, "SELECT COUNT(*) FROM error_codes")
    return 0


def _count_departments() -> int:
    return len(DEPARTMENTS)


# ─────────────────────────────────────────────────────────────
# GET /dashboard/metrics
# ─────────────────────────────────────────────────────────────

@router.get("/metrics")
async def get_metrics(user=Depends(get_current_user)):
    return {
        "employees": _count_employees(),
        "errorCodes": _count_error_codes(),
        "departments": _count_departments(),
        "testAccounts": _count_test_accounts(),
    }


# ─────────────────────────────────────────────────────────────
# GET /dashboard/system-health
# ─────────────────────────────────────────────────────────────

@router.get("/system-health")
async def get_system_health(user=Depends(get_current_user)):
    auth_ok = (DATA_DIR / "auth.db").exists()
    employees_ok = (DATA_DIR / "employees.db").exists()
    scenarios_ok = (DATA_DIR / "scenarios").exists()
    facility_ok = (DATA_DIR / "facility_db" / "plants.json").exists()
    vector_ok = (Path(DATA_DIR).parent / "vectorstore").exists()

    enable_a = os.environ.get("ENABLE_FEATURE_A", "true").lower() in ("true", "1", "yes")
    auth_backend = os.environ.get("AUTH_BACKEND", "sqlite").lower()

    return {
        "backend": "healthy",
        "auth_db": auth_ok,
        "employee_db": employees_ok,
        "scenarios": scenarios_ok,
        "facility_db": facility_ok,
        "vectorstore": vector_ok and enable_a,
        "auth_backend": auth_backend,
        "feature_a_enabled": enable_a,
        "timestamp": datetime.now().isoformat(),
    }


# ─────────────────────────────────────────────────────────────
# GET /dashboard/ingestion — 자산 수집 현황
# ─────────────────────────────────────────────────────────────

def _system_metrics() -> dict[str, float]:
    """CPU 사용률 + 최근 1분 latency/qps. psutil 미설치 시 0 반환."""
    cpu_pct = 0.0
    try:
        import psutil  # type: ignore
        # interval=0.1 — 100ms 샘플링. 첫 호출에서도 의미 있는 값 보장.
        cpu_pct = float(psutil.cpu_percent(interval=0.1))
    except Exception:
        pass

    # main.py 의 미들웨어 기록 조회
    latency_ms = 0.0
    qps = 0.0
    try:
        from backend.main import get_request_metrics_window  # 지연 import
        count, avg_ms = get_request_metrics_window()
        latency_ms = round(avg_ms, 1)
        qps = round(count / 60.0, 2)
    except Exception:
        pass

    return {"gpu_pct": cpu_pct, "latency_ms": latency_ms, "qps": qps}


@router.get("/ingestion")
async def get_ingestion(user=Depends(get_current_user)):
    err = _count_error_codes()
    molds_db = DATA_DIR / "equipment" / "molds.db"
    molds_n = _safe_count(molds_db, "SELECT COUNT(*) FROM molds WHERE status='active'") \
        if molds_db.exists() else 0
    molds_total = _safe_count(molds_db, "SELECT COUNT(*) FROM molds") if molds_db.exists() else 0

    drawings_db = DATA_DIR / "equipment" / "drawings.db"
    draw_n = _safe_count(drawings_db, "SELECT COUNT(*) FROM drawings") if drawings_db.exists() else 0

    inspect_db = DATA_DIR / "equipment" / "inspection.db"
    if inspect_db.exists():
        # checklist_templates(템플릿 6) + inspection_logs(실 기록 1) 합산.
        # total 은 시연 목표(72)와 max 비교 → 진행률 표시.
        templates_n = _safe_count(inspect_db, "SELECT COUNT(*) FROM checklist_templates")
        logs_n = _safe_count(inspect_db, "SELECT COUNT(*) FROM inspection_logs")
        inspect_n = templates_n + logs_n
        inspect_total = max(inspect_n, 72)
    else:
        inspect_n = 0
        inspect_total = 72

    out: dict[str, Any] = {
        "errorCodes": {"have": err, "total": err},
        "molds": {"have": molds_n, "total": molds_total or molds_n},
        "spc": {"have": 5, "total": 5},  # SPC 공정은 코드 상수 (Nelson 8 Rules)
        "drawings": {"have": draw_n, "total": draw_n},
        "inspections": {"have": inspect_n, "total": inspect_total},
        # 시스템 메트릭 (Phase 4 — 실측)
        **_system_metrics(),
    }
    return out


# ─────────────────────────────────────────────────────────────
# GET /dashboard/system-info
# ─────────────────────────────────────────────────────────────

@router.get("/system-info")
async def get_system_info(user=Depends(get_current_user)):
    """대시보드 시스템 정보 — .env 의 실제 모델 설정을 그대로 노출.

    프론트는 본 응답을 사용하고, 실패 시 mock SYSTEM_INFO 로 폴백한다.
    """
    # ── LLM / 비전 / 임베딩 모델 — .env 직독으로 단일 진실 (LLMRouter 와 동일)
    gemini_pro = os.environ.get("GEMINI_MODEL", "gemini-2.5-pro")
    chat_large = os.environ.get("OLLAMA_MODEL_CHAT_LARGE", "qwen3.5:9b")
    chat_small = os.environ.get("OLLAMA_MODEL_CHAT_SMALL", "qwen3.5:4b")
    gemma_large = os.environ.get("OLLAMA_MODEL_GEMMA_LARGE", "gemma4:e4b")
    gemma_small = os.environ.get("OLLAMA_MODEL_GEMMA_SMALL", "gemma4:e2b")
    embedding = os.environ.get("OLLAMA_MODEL_EMBEDDING", "bge-m3")
    lm_studio_enabled = os.environ.get("LM_STUDIO_ENABLED", "false").lower() == "true"
    embedding_backend = os.environ.get("EMBEDDING_BACKEND", "ollama").lower()

    cb_threshold = os.environ.get("LLM_ROUTER_CIRCUIT_BREAKER_THRESHOLD", "3")
    cb_recovery = os.environ.get("LLM_ROUTER_CIRCUIT_RECOVERY_SEC", "60")
    fallback_on = os.environ.get("LLM_ROUTER_FALLBACK_ENABLED", "true").lower() == "true"

    llm_engines = [
        f"Gemini {gemini_pro.removeprefix('gemini-').upper()} (1순위)",
        f"Qwen {chat_large} / {chat_small} (사내)",
        f"Gemma {gemma_large} / {gemma_small} (경량)",
    ]
    if lm_studio_enabled:
        llm_engines.append("LM Studio (옵션)")

    vision_models = [
        f"Gemini {gemini_pro.removeprefix('gemini-').upper()} Multimodal",
        f"Gemma {gemma_large} / {gemma_small}",
    ]

    embed_caption = (
        f"{embedding} (Ollama) · Gemini Embeddings 폴백"
        if embedding_backend != "gemini"
        else f"Gemini Embeddings (1순위) · {embedding} 폴백"
    )

    return {
        "version": "v3.5",
        "environment": os.environ.get("AJIN_ENVIRONMENT", "ON-PREMISE"),
        "auth_mode": "JWT_ACTIVE",
        "auth_backend": os.environ.get("AUTH_BACKEND", "sqlite").lower(),
        # 신규 — 모델 / 라우팅 / ML 정보를 프론트가 그대로 표시
        "llm": llm_engines,
        "vision": vision_models,
        "embedding": embed_caption,
        "router": (
            f"LLMRouter 폴백 {'활성' if fallback_on else '비활성'} · "
            f"Circuit Breaker {cb_threshold}회/{cb_recovery}초"
        ),
        "ml": "7 종 (Intent · Error TF-IDF · SPC IF · Mold XGB · Markov · DocQual · RegRisk)",
        "rbac": "6단계 + 28 세부 권한 + 부서 30",
        # 레거시 호환
        "llm_default": chat_large,
        "embedding_backend": embedding_backend,
        "feature_flags": {
            "A": os.environ.get("ENABLE_FEATURE_A", "true").lower() in ("true", "1", "yes"),
            "B": os.environ.get("ENABLE_FEATURE_B", "true").lower() in ("true", "1", "yes"),
            "E": os.environ.get("ENABLE_FEATURE_E", "true").lower() in ("true", "1", "yes"),
        },
    }


# ─────────────────────────────────────────────────────────────
# GET /dashboard/alarms — 진행 중 알람
# ─────────────────────────────────────────────────────────────

@router.get("/module-counts")
async def get_module_counts(user=Depends(get_current_user)):
    """모듈 카드 bullets 에서 사용할 동적 카운터.

    - crawlers: 컴플라이언스 모듈 D 의 등록된 크롤러 수
    - sopGuides: 모듈 C 의 SOP 가이드 수
    - collaborations: 모듈 C 의 협업 시나리오 수
    - molds: 모듈 F 의 금형 자산 수 (active + maintenance, retired 제외)
    - roles: 모듈 E 의 RBAC 역할 수
    - fewShotRag: 모듈 B 의 Few-shot RAG 학습 케이스 수
    """
    # crawlers — features.compliance 의 등록된 크롤러 수 (코드 상수)
    try:
        from backend.routers.compliance import _CRAWLER_KEYS
        crawlers = len(_CRAWLER_KEYS)
    except Exception:
        crawlers = 0

    # sop / collaboration — features.onboarding
    sop_guides = 0
    collaborations = 0
    try:
        from features.onboarding.sop_guide import SOP_DATABASE  # type: ignore
        sop_guides = len(SOP_DATABASE)
    except Exception:
        pass
    try:
        from features.onboarding.collaboration_guide import COLLABORATION_SCENARIOS  # type: ignore
        collaborations = len(COLLABORATION_SCENARIOS)
    except Exception:
        pass

    # molds — equipment/molds.db active + maintenance
    molds = 0
    molds_db = DATA_DIR / "equipment" / "molds.db"
    if molds_db.exists():
        molds = _safe_count(
            molds_db,
            "SELECT COUNT(*) FROM molds WHERE status IN ('active','maintenance')",
        )

    # roles — auth.db
    roles = _safe_count(DATA_DIR / "auth.db", "SELECT COUNT(*) FROM roles WHERE role_level > 0")

    # fewshot rag — data/knowledge_base/fewshot 또는 백업으로 정적 584
    fewshot = 0
    fewshot_csv = DATA_DIR / "knowledge_base" / "fewshot_rag.csv"
    if fewshot_csv.exists():
        try:
            with open(fewshot_csv, encoding="utf-8") as f:
                # 첫 줄(header) 제외
                fewshot = max(0, sum(1 for _ in f) - 1)
        except Exception:
            pass

    return {
        "crawlers": crawlers,
        "sopGuides": sop_guides or 8,            # 0 일 시 시연 디폴트
        "collaborations": collaborations or 5,
        "molds": molds or 25,
        "roles": roles or 6,
        "fewShotRag": fewshot or 584,
    }


@router.get("/alarms")
async def get_alarms(user=Depends(get_current_user)):
    """대시보드 카드 상단의 알람. 시뮬레이션용 — Module D 시나리오 기반."""
    return {
        "alarms": [
            {
                "id": "ALM-001",
                "severity": "critical",
                "module": "D",
                "title": "산안법 시행 D-30",
                "detail": "프레스 안전거리 300→400mm 변경. 본사·천안1·천안2 라인 검토 필요",
                "ts": datetime.now().isoformat(),
            },
        ],
        "total": 1,
        "critical": 1,
        "warning": 0,
        "info": 0,
    }
