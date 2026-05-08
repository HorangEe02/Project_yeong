"""헬스체크 라우터.

v3.3 Phase H — `/health/llm-status` 통합 진단 엔드포인트 추가.
시연 환경(Cloudflare Tunnel) 의 OLLAMA_BASE_URL 이 모든 기능(A~F) 에 적용되는지
한 번에 검증하기 위함. docker/demo-tunnel/entrypoint.sh 가 호출.
"""

import os
from typing import Literal

import requests
from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.schemas.common import HealthResponse
from config import OLLAMA_BASE_URL, VECTORSTORE_DIR, ollama_headers

router = APIRouter(tags=["health"])


# v3.3 Phase H — 6 기능 ↔ LLM backend 매핑 (단일 진실 원천)
# 각 기능이 어떤 LLM 경로를 사용하는지 명시 — 시연 환경 검증 시 사용자에게 노출.
FEATURE_LLM_MATRIX = [
    {
        "id": "A",
        "name": "문서 검색",
        "endpoint": "/api/search/documents",
        "uses": ["ollama"],
        "via": "core.llm_client.stream_generate",
        "notes": "검색 결과 요약에 LLM 사용 (Ollama 단독)",
    },
    {
        "id": "B",
        "name": "문서 작성",
        "endpoint": "/api/draft/stream-v2",
        "uses": ["ollama", "gemini"],
        "via": "core.llm_router.LLMRouter + core.llm_client.stream_generate",
        "notes": "FEATURE_B_BLOCK_GEMINI=true 시 Gemini 차단, false 시 LLMRouter 폴백",
    },
    {
        "id": "C",
        "name": "AI 업무 도우미",
        "endpoint": "/api/onboarding/chat",
        "uses": ["ollama", "gemini"],
        "via": "core.llm_router.LLMRouter (싱글톤)",
        "notes": "v3.3 — ModelSelect UI 로 사용자 강제 가능, force_provider 미설정 시 폴백",
    },
    {
        "id": "D",
        "name": "컴플라이언스",
        "endpoint": "/api/compliance/*",
        "uses": ["ollama"],
        "via": "core.embedding_client (RAG) + LLMRouter (요약)",
        "notes": "BGE-M3 임베딩 + LLM 요약",
    },
    {
        "id": "E",
        "name": "인사 검색",
        "endpoint": "/api/employee/search",
        "uses": ["ollama"],
        "via": "features.search.employee.semantic_search.OllamaEmbeddings",
        "notes": "BGE-M3 의미 검색 (LLM 호출 없음, 임베딩만)",
    },
    {
        "id": "F",
        "name": "설비/공정 AI",
        "endpoint": "/api/equipment/*",
        "uses": [],
        "via": "TF-IDF / Markov ML (LLM 미사용)",
        "notes": "에러코드 ML 검색 — LLM 무관",
    },
]


# ──────────────────────────────────────────────
# 응답 스키마
# ──────────────────────────────────────────────


class OllamaStatus(BaseModel):
    ok: bool
    base_url: str
    is_tunnel: bool = False  # trycloudflare.com 도메인 여부
    model_count: int = 0
    models: list[str] = Field(default_factory=list)
    error: str = ""


class GeminiStatus(BaseModel):
    api_key_present: bool
    model: str
    feature_b_blocked: bool  # FEATURE_B_BLOCK_GEMINI 토글 결과


class FeatureLLMStatus(BaseModel):
    id: str
    name: str
    endpoint: str
    uses: list[str]
    via: str
    notes: str
    ok: bool = True  # 의존하는 backend 가 모두 도달 가능하면 true


class CircuitState(BaseModel):
    provider: str
    state: Literal["closed", "open", "half_open"] = "closed"


class LLMStatusResponse(BaseModel):
    status: Literal["ok", "degraded", "error"]
    summary: str  # 사람이 읽는 요약 한 줄
    ollama: OllamaStatus
    gemini: GeminiStatus
    features: list[FeatureLLMStatus]
    circuit_breakers: list[CircuitState] = Field(default_factory=list)
    feature_flags: dict[str, bool] = Field(default_factory=dict)
    tunnel_active: bool = False  # OLLAMA_BASE_URL 가 trycloudflare.com 이면 true


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Ollama + ChromaDB 연결 상태를 확인한다."""
    llm_connected = False
    models_loaded: list[str] = []
    chroma_connected = False
    chroma_doc_count = 0

    # Ollama 연결 확인 (Plan A 변형: Caddy 경유 시 X-AJIN-Secret 부착)
    try:
        resp = requests.get(
            f"{OLLAMA_BASE_URL}/api/tags",
            headers=ollama_headers(),
            timeout=3,
        )
        if resp.status_code == 200:
            llm_connected = True
            models_loaded = [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        pass

    # ChromaDB 연결 확인
    try:
        from chromadb import PersistentClient
        client = PersistentClient(path=str(VECTORSTORE_DIR / "documents"))
        col = client.get_collection("ajin_documents")
        chroma_doc_count = col.count()
        chroma_connected = True
    except Exception:
        pass

    status = "ok" if llm_connected and chroma_connected else "degraded"
    if not llm_connected and not chroma_connected:
        status = "error"

    return HealthResponse(
        status=status,
        llm_connected=llm_connected,
        chroma_connected=chroma_connected,
        chroma_doc_count=chroma_doc_count,
        models_loaded=models_loaded,
    )


# ════════════════════════════════════════════════════════════
# v3.3 Phase H — 통합 LLM 상태 엔드포인트
# 시연 환경(Cloudflare Tunnel) 의 OLLAMA_BASE_URL 이 모든 기능에
# 적용되었는지 한 번에 검증.
# ════════════════════════════════════════════════════════════


def _check_ollama() -> OllamaStatus:
    """Ollama 도달성 + Tunnel 여부 + 설치 모델 목록."""
    is_tunnel = "trycloudflare.com" in (OLLAMA_BASE_URL or "")
    if not OLLAMA_BASE_URL or not OLLAMA_BASE_URL.strip():
        return OllamaStatus(
            ok=False,
            base_url="",
            is_tunnel=False,
            error="OLLAMA_BASE_URL 비어있음 (Gemini 단독 모드)",
        )
    try:
        resp = requests.get(
            f"{OLLAMA_BASE_URL}/api/tags",
            headers=ollama_headers(),
            timeout=5,
        )
        if resp.status_code != 200:
            return OllamaStatus(
                ok=False,
                base_url=OLLAMA_BASE_URL,
                is_tunnel=is_tunnel,
                error=f"HTTP {resp.status_code}",
            )
        models = [m.get("name", "") for m in resp.json().get("models", [])]
        return OllamaStatus(
            ok=True,
            base_url=OLLAMA_BASE_URL,
            is_tunnel=is_tunnel,
            model_count=len(models),
            models=models,
        )
    except Exception as e:
        return OllamaStatus(
            ok=False,
            base_url=OLLAMA_BASE_URL,
            is_tunnel=is_tunnel,
            error=str(e)[:200],
        )


def _check_gemini() -> GeminiStatus:
    """Gemini API 키 + Feature B 차단 정책."""
    api_key = bool(os.environ.get("GEMINI_API_KEY", "").strip())
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-pro")
    block_b = os.environ.get("FEATURE_B_BLOCK_GEMINI", "true").strip().lower() in (
        "1", "true", "yes", "on",
    )
    return GeminiStatus(
        api_key_present=api_key,
        model=model,
        feature_b_blocked=block_b,
    )


def _evaluate_features(ollama_ok: bool, gemini_ok: bool) -> list[FeatureLLMStatus]:
    """6 기능별로 의존 backend 가 모두 도달 가능한지 평가."""
    out: list[FeatureLLMStatus] = []
    for spec in FEATURE_LLM_MATRIX:
        uses = list(spec.get("uses", []))
        # 의존성 평가 — uses 가 비어있으면 LLM 무관 → 항상 ok
        if not uses:
            ok = True
        else:
            ok = (
                ("ollama" not in uses or ollama_ok)
                and ("gemini" not in uses or gemini_ok)
                # 한 쪽만 이용 가능해도 LLMRouter 폴백으로 동작 가능 (B/C)
                or any(
                    p == "ollama" and ollama_ok or p == "gemini" and gemini_ok
                    for p in uses
                )
            )
        out.append(FeatureLLMStatus(
            id=spec["id"],
            name=spec["name"],
            endpoint=spec["endpoint"],
            uses=uses,
            via=spec["via"],
            notes=spec["notes"],
            ok=ok,
        ))
    return out


@router.get("/health/llm-status", response_model=LLMStatusResponse)
async def llm_status() -> LLMStatusResponse:
    """v3.3 Phase H — 모든 기능의 LLM 도달 상태 통합 진단.

    시연 환경(Cloudflare Tunnel) 활성 시 ``OLLAMA_BASE_URL`` 이 trycloudflare.com 으로
    설정되며, 이 환경변수는 Cloud Run 의 모든 기능(A/B/C/D/E/F) 가 공유한다.
    본 엔드포인트로 6 기능 모두 동일 Tunnel 을 통해 Ollama 에 도달하는지 확인.
    """
    ollama = _check_ollama()
    gemini = _check_gemini()
    features = _evaluate_features(ollama.ok, gemini.api_key_present)

    # LLMRouter Circuit Breaker 스냅샷 (있으면)
    breakers: list[CircuitState] = []
    try:
        from core.llm_router import LLMRouter

        router_inst = LLMRouter()
        snapshot = router_inst.health.snapshot()
        for provider in router_inst.providers.keys():
            state = snapshot.get(provider, {}).get("state", "closed")
            breakers.append(CircuitState(provider=provider, state=state))
    except Exception:
        pass

    # v3.3 Feature C 피처 플래그
    flags_dict: dict[str, bool] = {}
    try:
        from core.feature_flags import feature_c_flags_dict

        flags_dict = feature_c_flags_dict()
    except Exception:
        pass

    # 종합 상태 — 의존 LLM 1개 이상 ok 면 'ok', 모두 down 이면 'error'
    has_llm = ollama.ok or gemini.api_key_present
    all_features_ok = all(f.ok for f in features)
    if has_llm and all_features_ok:
        status: Literal["ok", "degraded", "error"] = "ok"
    elif has_llm:
        status = "degraded"
    else:
        status = "error"

    # 사람이 읽는 요약
    parts = []
    if ollama.is_tunnel:
        parts.append("🚇 Cloudflare Tunnel 활성")
    if ollama.ok:
        parts.append(f"🟢 Ollama OK ({ollama.model_count} 모델)")
    else:
        parts.append("🔴 Ollama 도달 불가")
    if gemini.api_key_present:
        parts.append("🟢 Gemini 키 OK")
    else:
        parts.append("⚪ Gemini 키 없음")
    parts.append(f"기능 A~F 매핑: {sum(1 for f in features if f.ok)}/{len(features)}")
    summary = " · ".join(parts)

    return LLMStatusResponse(
        status=status,
        summary=summary,
        ollama=ollama,
        gemini=gemini,
        features=features,
        circuit_breakers=breakers,
        feature_flags=flags_dict,
        tunnel_active=ollama.is_tunnel,
    )
