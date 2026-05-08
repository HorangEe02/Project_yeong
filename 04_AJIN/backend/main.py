"""AJIN AI Assistant - FastAPI 백엔드 메인 애플리케이션.

Streamlit 프론트엔드에 REST/JSON + SSE 스트리밍 API를 제공한다.

실행 (개발):
    uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
    ※ SEC: 프로덕션에서는 절대 --host 0.0.0.0 사용 금지 (외부 노출됨)
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

# 프로젝트 루트를 sys.path에 추가 (config, core, features 접근용)
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from backend.config import CORS_ORIGINS

# ── Plan A 변형: Mac Ollama 도달성 미들웨어 의존 ──
import time as _ollama_time
import json as _ollama_json
import requests as _ollama_requests
from config import OLLAMA_BASE_URL as _OLLAMA_URL, ollama_headers as _ollama_headers


class OllamaHealthMiddleware(BaseHTTPMiddleware):
    """LLM 의존 endpoint 진입 시 Caddy → Mac Ollama 헬스체크. 503 graceful 차단.

    5초 캐시로 Cloud Run side effect 최소화. Mac off 시 한국어 안내.
    Frontend 의 axios interceptor 가 503 + AI_UNAVAILABLE 을 받아 banner 표시.
    """

    LLM_PATHS = ("/api/draft", "/api/onboarding", "/api/search/semantic", "/api/chat")
    CACHE_TTL = 5.0
    _cache = {"ok": False, "ts": 0.0}

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not any(path.startswith(p) for p in self.LLM_PATHS):
            return await call_next(request)
        if not _OLLAMA_URL:
            return self._unavailable("OLLAMA_BASE_URL 미설정")

        now = _ollama_time.time()
        if now - self._cache["ts"] > self.CACHE_TTL:
            try:
                r = _ollama_requests.get(
                    f"{_OLLAMA_URL}/api/tags",
                    headers=_ollama_headers(),
                    timeout=3,
                )
                self.__class__._cache = {"ok": r.status_code == 200, "ts": now}
            except Exception:
                self.__class__._cache = {"ok": False, "ts": now}

        if not self._cache["ok"]:
            return self._unavailable("Mac Ollama 응답 없음")
        return await call_next(request)

    @staticmethod
    def _unavailable(reason: str) -> StarletteResponse:
        body = _ollama_json.dumps(
            {
                "error": "AI_UNAVAILABLE",
                "message": "AI 서버 점검 중입니다. 잠시 후 다시 시도해주세요. (운영시간: 평일 09~18시)",
                "reason": reason,
                "retry_after": 60,
            },
            ensure_ascii=False,
        )
        return StarletteResponse(
            content=body,
            status_code=503,
            media_type="application/json; charset=utf-8",
            headers={"Retry-After": "60"},
        )


def _flag(name: str, default: str = "true") -> bool:
    """ENABLE_FEATURE_X 환경변수 파싱 (true/1/yes 만 활성)."""
    import os as _os
    return _os.environ.get(name, default).strip().lower() in ("true", "1", "yes", "on")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작 시 싱글톤 서비스를 초기화하고, 종료 시 정리한다.

    Cloud Run 슬림 배포용 환경변수:
      ENABLE_FEATURE_A=false  → HybridSearcher 스킵 (chromadb/sentence-transformers 미필요)
      ENABLE_FEATURE_B=false  → DraftPipeline 스킵
      ENABLE_FEATURE_E=false  → EmployeeSearchEngine 스킵 (employees.db 의존)
    """
    print("[AJIN Backend] 서비스 초기화 시작...")

    enable_a = _flag("ENABLE_FEATURE_A")
    enable_b = _flag("ENABLE_FEATURE_B")
    enable_e = _flag("ENABLE_FEATURE_E")

    # 0. 인증 DB 부팅 sync (AUTH_BACKEND=firestore 시 Firestore → SQLite mirror)
    try:
        from core.auth.database import init_auth_db, seed_admin_user
        init_auth_db()
        seed_admin_user()
        print("[AJIN Backend] ✓ 인증 DB 초기화 완료")
    except Exception as e:
        print(f"[AJIN Backend] ✗ 인증 DB 초기화 실패: {e}")

    # 0.5. 협업 시나리오 DB + 시드 5종 적재
    try:
        from core.scenarios.database import init_scenarios_db
        init_scenarios_db()
        print("[AJIN Backend] ✓ 협업 시나리오 DB 초기화 완료")
    except Exception as e:
        print(f"[AJIN Backend] ✗ 협업 시나리오 DB 초기화 실패: {e}")

    # 1. HybridSearcher (ChromaDB + BM25)
    app.state.searcher = None
    if enable_a:
        try:
            from features.search.searcher import HybridSearcher
            app.state.searcher = HybridSearcher()
            print("[AJIN Backend] ✓ HybridSearcher 초기화 완료")
        except Exception as e:
            print(f"[AJIN Backend] ✗ HybridSearcher 초기화 실패: {e}")
    else:
        print("[AJIN Backend] ⏭ HybridSearcher 스킵 (ENABLE_FEATURE_A=false)")

    # 2. EmployeeDatabase + EmployeeSearchEngine
    app.state.employee_db = None
    app.state.employee_engine = None
    if enable_e:
        try:
            from features.search.employee.database import EmployeeDatabase
            from features.search.employee.search import EmployeeSearchEngine
            app.state.employee_db = EmployeeDatabase()
            app.state.employee_engine = EmployeeSearchEngine(app.state.employee_db)
            print("[AJIN Backend] ✓ EmployeeSearchEngine 초기화 완료")
        except Exception as e:
            print(f"[AJIN Backend] ✗ EmployeeSearchEngine 초기화 실패: {e}")
    else:
        print("[AJIN Backend] ⏭ EmployeeSearchEngine 스킵 (ENABLE_FEATURE_E=false)")

    # 3. DraftPipeline
    app.state.draft_pipeline = None
    if enable_b:
        try:
            from features.draft import DraftPipeline
            app.state.draft_pipeline = DraftPipeline()
            print("[AJIN Backend] ✓ DraftPipeline 초기화 완료")
        except Exception as e:
            print(f"[AJIN Backend] ✗ DraftPipeline 초기화 실패: {e}")
    else:
        print("[AJIN Backend] ⏭ DraftPipeline 스킵 (ENABLE_FEATURE_B=false)")

    # 3-b. Module B 자가진단 — Plan v1.0 §1.3 (Ollama / Gemini / 템플릿 / 프롬프트)
    if enable_b:
        try:
            import os as _osB
            import requests as _reqB
            from config import OLLAMA_BASE_URL as _OLB, KNOWLEDGE_BASE_DIR as _KBB
            from pathlib import Path as _PathB
            try:
                _r = _reqB.get(f"{_OLB}/api/tags", timeout=2)
                _ok = _r.status_code == 200
                _ms = [m.get("name", "") for m in _r.json().get("models", [])] if _ok else []
                print(f"[AJIN Backend] [Module B 진단] Ollama: {'✓' if _ok else '✗'} ({len(_ms)} models)")
            except Exception as _e:
                print(f"[AJIN Backend] [Module B 진단] Ollama: ✗ ({type(_e).__name__})")
            _gk = bool(_osB.environ.get("GEMINI_API_KEY", "").strip())
            print(f"[AJIN Backend] [Module B 진단] Gemini key: {'✓' if _gk else '✗'} (.env)")
            _td = _KBB / "templates"
            _tn = len(list(_td.glob('*.j2'))) if _td.exists() else 0
            print(f"[AJIN Backend] [Module B 진단] Templates: {_tn}개 (.j2)")
            _pd = _PathB("features/draft/prompts")
            _pn = len(list(_pd.glob('*.txt'))) if _pd.exists() else 0
            print(f"[AJIN Backend] [Module B 진단] Prompts: {_pn}개")
        except Exception as _e:
            print(f"[AJIN Backend] [Module B 진단] 진단 실패: {_e}")

    # 4. Compliance (ScenarioLoader, FacilityDB)
    try:
        app.state.scenario_loader = None
        app.state.compliance_checker = None
        app.state.facility_db = None
        print("[AJIN Backend] ✓ Compliance 서비스 초기화 완료")
    except Exception as e:
        print(f"[AJIN Backend] ✗ Compliance 초기화 실패: {e}")

    print("[AJIN Backend] 서비스 초기화 완료. API 서버 시작.")
    print("[AJIN Backend] Swagger UI: http://localhost:8000/docs")

    yield  # 앱 실행

    # 종료 정리
    print("[AJIN Backend] 서버 종료 중...")
    if hasattr(app.state, "employee_db") and app.state.employee_db:
        try:
            app.state.employee_db.close()
        except Exception:
            pass


# FastAPI 앱 생성
app = FastAPI(
    title="AJIN AI Assistant API",
    description="아진산업 AI 어시스턴트 백엔드 API - LLM, 검색, 문서 생성, 규정 준수",
    version="1.1.0",
    lifespan=lifespan,
)

# ── SEC-P1: 보안 헤더 미들웨어 ──
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # SSE 응답은 라우터가 설정한 Cache-Control(no-cache, no-transform) 보존
        # — no-store/no-transform 미보장 시 Hosting↔Cloud Run 구간에서 chunked 버퍼링 발생
        if response.headers.get("content-type", "").startswith("text/event-stream"):
            response.headers.setdefault("Cache-Control", "no-cache, no-transform")
            response.headers.setdefault("X-Accel-Buffering", "no")
        else:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response

app.add_middleware(SecurityHeadersMiddleware)
# Plan A 변형: Mac Ollama 도달성 차단 (LLM endpoint 만)
app.add_middleware(OllamaHealthMiddleware)


# ── SEC-P1: 간단한 IP 기반 Rate Limiter ──
import time
from collections import defaultdict

_rate_limit_store: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_WINDOW = 60  # 60초
_RATE_LIMIT_MAX = 600    # 600회/분 (일반 엔드포인트, Day 6++.fix: SPC 5초 폴링 + 5공정 + RTDB 동시)
_LOGIN_RATE_LIMIT_MAX = 10  # 10회/분 (로그인)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        path = request.url.path

        # 로그인은 더 엄격한 제한
        max_requests = _LOGIN_RATE_LIMIT_MAX if "/auth/login" in path else _RATE_LIMIT_MAX

        # 윈도우 밖 요청 제거
        key = f"{client_ip}:{path.split('/')[2] if len(path.split('/')) > 2 else 'root'}"
        _rate_limit_store[key] = [t for t in _rate_limit_store[key] if now - t < _RATE_LIMIT_WINDOW]

        if len(_rate_limit_store[key]) >= max_requests:
            return StarletteResponse(
                content='{"detail":"Too many requests. Please try again later."}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(_RATE_LIMIT_WINDOW)},
            )

        _rate_limit_store[key].append(now)
        return await call_next(request)

app.add_middleware(RateLimitMiddleware)


# ── Dashboard 메트릭 — 최근 1분 요청 수 / 평균 latency 추적 ──
from collections import deque

_REQ_WINDOW_SEC = 60
# (timestamp, latency_ms) 튜플 보관. 1000건 cap → 1분에 1000건 넘으면 오래된 것 제거
_request_metrics: deque[tuple[float, float]] = deque(maxlen=2000)


class RequestMetricsMiddleware(BaseHTTPMiddleware):
    """모든 요청의 (시각, 응답시간 ms) 기록. /api/dashboard/* 는 자기 호출 제외."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # 대시보드 메트릭 자체 호출 제외 (5초 폴링이 통계 왜곡)
        skip = path.startswith("/api/dashboard/") or path == "/api/health/ping"
        if skip:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        _request_metrics.append((time.time(), elapsed_ms))
        return response


app.add_middleware(RequestMetricsMiddleware)


def get_request_metrics_window() -> tuple[int, float]:
    """최근 _REQ_WINDOW_SEC 초의 (요청 수, 평균 latency_ms) 반환."""
    now = time.time()
    cutoff = now - _REQ_WINDOW_SEC
    recent = [lat for ts, lat in _request_metrics if ts >= cutoff]
    if not recent:
        return 0, 0.0
    return len(recent), sum(recent) / len(recent)


# main.py 모듈에 export — dashboard 라우터에서 import 해서 사용
app.state.get_request_metrics_window = get_request_metrics_window


# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
from backend.routers import health, models, search, employee, onboarding, draft, compliance, equipment, export, dashboard, feature_flags
from backend.routers import auth as auth_router
from backend.routers import admin as admin_router
from backend.routers import admin_scenarios as admin_scenarios_router
from backend.routers import scenarios as scenarios_router

app.include_router(health.router, prefix="/api")
app.include_router(models.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(employee.router, prefix="/api")
app.include_router(onboarding.router, prefix="/api")
app.include_router(draft.router, prefix="/api")
app.include_router(compliance.router, prefix="/api")
app.include_router(auth_router.router, prefix="/api")  # v2.0: 인증 API
app.include_router(equipment.router, prefix="/api")    # Day 6: 설비/공정 AI (Module F)
app.include_router(export.router, prefix="/api")       # Phase 7: 공통 HWP/HWPX export fallback
app.include_router(dashboard.router, prefix="/api")    # 대시보드 메트릭 (사원/에러코드/부서/테스트계정/시스템상태)
app.include_router(feature_flags.router, prefix="/api")  # v3.3: Feature C 피처 플래그 노출
app.include_router(admin_router.router, prefix="/api")  # 기능 E: 인사 관리
app.include_router(admin_scenarios_router.router, prefix="/api")  # 기능 C: 협업 시나리오 관리 (HR_ADMIN+)
app.include_router(scenarios_router.router, prefix="/api")  # 기능 C: 협업 시나리오 사용자 + 즐겨찾기


@app.get("/")
async def root():
    """루트 엔드포인트 - API 정보 반환."""
    return {
        "name": "AJIN AI Assistant API",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }
