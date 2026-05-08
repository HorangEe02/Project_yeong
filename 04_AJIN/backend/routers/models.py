"""모델 관리 라우터."""

import os

from fastapi import APIRouter, Query

from backend.schemas.common import (
    AutoSelectResponse,
    AvailableModelsResponse,
    ModelInfo,
    ModelListResponse,
)
from backend.schemas.draft import LLMOption, LLMOptionsResponse
from core.llm_client import (
    auto_select_model,
    auto_select_vision_model,
    get_available_chat_models,
    get_installed_models,
    get_vision_models,
    invalidate_model_cache,
)
from config import MODEL_PROFILES

router = APIRouter(prefix="/models", tags=["models"])


# ───────────────────────────────────────────────────────────
# Plan v1.0 — Feature B 모델 셀렉터: Gemini 차단 정책
# ───────────────────────────────────────────────────────────

# Feature B(=draft) 에서 보안상 차단되는 provider — 사내 보안 정책.
# Plan v1.0 — 환경변수 FEATURE_B_BLOCK_GEMINI 로 토글 (default true).
# 클라우드 시연(Ollama 미배포 환경)에서는 false 로 설정해 Gemini 자동 허용.
def _feature_b_blocks_gemini() -> bool:
    return os.environ.get("FEATURE_B_BLOCK_GEMINI", "true").strip().lower() in ("1", "true", "yes", "on")

# 셀렉터에 노출할 패밀리 (UI 일관성)
# v3.3 Feature C — Qwen 3.5 + Gemma 4 + EXAONE 3.5 + Gemini 2.5 노출
_VISIBLE_FAMILIES: dict[str, str] = {
    "qwen3.5": "qwen",
    "qwen3": "qwen",
    "gemma4": "gemma",
    "gemma3": "gemma",
    "exaone3.5": "exaone",
    "exaone-deep": "exaone",
}


def _ollama_family(model_id: str) -> str | None:
    for prefix, fam in _VISIBLE_FAMILIES.items():
        if model_id.startswith(prefix):
            return fam
    return None


def _build_llm_options(feature: str) -> LLMOptionsResponse:
    """Feature 별 모델 셀렉터 옵션 빌드."""
    options: list[LLMOption] = []

    # Ollama 로컬 모델
    installed = set(get_installed_models())
    for mid in sorted(installed):
        fam = _ollama_family(mid)
        if not fam:
            continue
        profile = MODEL_PROFILES.get(mid, {})
        label = profile.get("display") or mid
        options.append(
            LLMOption(
                provider="ollama",
                id=mid,
                label=label,
                available=True,
                blocked=False,
                family=fam,  # type: ignore[arg-type]
            )
        )

    # Gemini Cloud 모델 — Pro + Flash 둘 다 노출 (사용자가 thinking 비용 vs 응답 속도 선택)
    gemini_key = bool(os.environ.get("GEMINI_API_KEY", "").strip())
    gemini_pro = os.environ.get("GEMINI_MODEL", "gemini-2.5-pro")
    gemini_flash = os.environ.get("GEMINI_MODEL_FLASH", "gemini-2.5-flash")
    blocked_in_feature = _feature_b_blocks_gemini() and feature == "draft"

    gemini_variants: list[tuple[str, str]] = []
    seen_ids: set[str] = set()
    for variant_id in (gemini_pro, gemini_flash):
        if variant_id and variant_id not in seen_ids:
            gemini_variants.append((variant_id, _humanize_gemini(variant_id)))
            seen_ids.add(variant_id)

    for variant_id, variant_label in gemini_variants:
        if gemini_key:
            options.append(
                LLMOption(
                    provider="gemini",
                    id=variant_id,
                    label=f"{variant_label} (Cloud)",
                    available=not blocked_in_feature,
                    blocked=blocked_in_feature,
                    blocked_reason=(
                        "Feature B(문서 작성)에서는 사내 보안 정책에 따라 Gemini 사용이 차단됩니다."
                        if blocked_in_feature
                        else ""
                    ),
                    family="gemini",
                )
            )
        else:
            # 키 없음 — UI 에서 회색 처리 + 안내
            options.append(
                LLMOption(
                    provider="gemini",
                    id=variant_id,
                    label=f"{variant_label} (Cloud)",
                    available=False,
                    blocked=False,
                    blocked_reason="GEMINI_API_KEY 가 .env 에 설정되지 않았습니다.",
                    family="gemini",
                )
            )

    # 기본값: 가장 우선순위 높은 사용 가능 옵션 (qwen3.5:9b > qwen3.5:4b > gemma4:* > 그 외)
    priority = ["qwen3.5:9b", "qwen3.5:4b", "qwen3.5:latest", "gemma4:latest", "gemma4:e4b", "gemma4:e2b"]
    default_opt: LLMOption | None = None
    for pid in priority:
        for o in options:
            if o.provider == "ollama" and o.id == pid and o.available and not o.blocked:
                default_opt = o
                break
        if default_opt:
            break
    if default_opt is None:
        for o in options:
            if o.available and not o.blocked:
                default_opt = o
                break

    return LLMOptionsResponse(
        options=options,
        default_provider=default_opt.provider if default_opt else None,
        default_id=default_opt.id if default_opt else None,
        feature=feature,
    )


def _humanize_gemini(mid: str) -> str:
    if "2.5-pro" in mid:
        return "Gemini 2.5 Pro"
    if "2.5-flash" in mid:
        return "Gemini 2.5 Flash"
    return mid


@router.get("/installed", response_model=ModelListResponse)
async def list_installed_models():
    """설치된 Ollama 모델 목록을 반환한다."""
    models = get_installed_models()
    return ModelListResponse(models=models, total=len(models))


@router.get("/available", response_model=AvailableModelsResponse)
async def list_available_models():
    """프로필 정보가 포함된 사용 가능한 채팅 모델 목록을 반환한다."""
    models = get_available_chat_models()
    items = [
        ModelInfo(
            id=m["id"],
            display=m.get("display", m["id"]),
            size_gb=m.get("size_gb", 0),
            lang=m.get("lang", ""),
            vision=m.get("vision", False),
            speed=m.get("speed", ""),
            quality=m.get("quality", ""),
            best_for=m.get("best_for", []),
        )
        for m in models
    ]
    return AvailableModelsResponse(models=items, total=len(items))


@router.get("/vision", response_model=AvailableModelsResponse)
async def list_vision_models():
    """비전 모델만 반환한다."""
    models = get_vision_models()
    items = [
        ModelInfo(
            id=m["id"],
            display=m.get("display", m["id"]),
            vision=True,
            quality=m.get("quality", ""),
        )
        for m in models
    ]
    return AvailableModelsResponse(models=items, total=len(items))


@router.get("/auto-select", response_model=AutoSelectResponse)
async def auto_select(feature: str = Query(default="onboarding")):
    """기능에 맞는 최적 모델을 자동 선택한다."""
    model = auto_select_model(feature)
    return AutoSelectResponse(model=model, feature=feature)


@router.post("/invalidate-cache")
async def invalidate_cache():
    """모델 캐시를 무효화한다."""
    invalidate_model_cache()
    return {"status": "cache_invalidated"}


# ───────────────────────────────────────────────────────────
# Plan v1.0 — Feature 별 LLM 셀렉터 옵션
# ───────────────────────────────────────────────────────────


@router.get("/llm-options", response_model=LLMOptionsResponse)
async def list_llm_options(feature: str = Query(default="draft")):
    """Feature 별 LLM 모델 셀렉터 옵션 목록.

    - feature="draft": Qwen 3.5 + Gemma 4 사용 가능, Gemini 2.5 Pro 는 보안 정책으로 blocked=true.
    - feature 그 외:    설치된 모든 패밀리 + Gemini 노출 (선택 가능).
    """
    return _build_llm_options(feature)
