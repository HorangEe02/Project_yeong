# Build marker: 20260525-130508
"""모델 관리 라우터."""

import os

from fastapi import APIRouter, Depends, Query

from backend.dependencies import get_current_user, require_role_level
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

router = APIRouter(
    prefix="/models",
    tags=["models"],
    dependencies=[Depends(get_current_user)],
)


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
# v3.5 — Nemotron Cascade 2 (NVIDIA 대형 추론) 추가
_VISIBLE_FAMILIES: dict[str, str] = {
    "qwen3.5": "qwen",
    "qwen3": "qwen",
    "gemma4": "gemma",
    "gemma3": "gemma",
    "exaone3.5": "exaone",
    "exaone-deep": "exaone",
    "nemotron-cascade": "nemotron",
    "nemotron": "nemotron",
}


def _ollama_family(model_id: str) -> str | None:
    for prefix, fam in _VISIBLE_FAMILIES.items():
        if model_id.startswith(prefix):
            return fam
    return None


# v3.5 Use case 그룹화 — Frontend ModelSelect dropdown 4 그룹 (한국어/다국어/비전/추론)
# (model_id_prefix → use_case) 매칭. _ollama_family 와 분리 — 한 family 가 여러 use_case 에
# 매핑될 수 있어 별도 dict 유지 (예: exaone3.5=korean, exaone-deep=reasoning).
_USE_CASE_MAP: dict[str, str] = {
    # 한국어 우수
    "exaone3.5": "korean",
    # 추론
    "exaone-deep": "reasoning",
    "nemotron-cascade": "reasoning",
    "nemotron": "reasoning",
    "gemini-3.5-flash": "reasoning",  # GA 2026-05-19, thinking 모드 + 1M 컨텍스트
    # 비전 (이미지·도면)
    "gemma4": "vision",
    "gemma3": "vision",
    # 다국어 (기본값 — qwen)
    "qwen3.5": "multilingual",
    "qwen3": "multilingual",
}


def _model_use_case(model_id: str) -> str:
    """model_id → use_case ('korean' | 'multilingual' | 'vision' | 'reasoning').

    매칭 prefix 가장 긴 것 우선 (예: 'exaone-deep' > 'exaone3.5').
    """
    sorted_prefixes = sorted(_USE_CASE_MAP.keys(), key=len, reverse=True)
    for prefix in sorted_prefixes:
        if model_id.startswith(prefix):
            return _USE_CASE_MAP[prefix]
    return "multilingual"  # 기본값


def _build_llm_options(feature: str) -> LLMOptionsResponse:
    """Feature 별 모델 셀렉터 옵션 빌드."""
    options: list[LLMOption] = []

    # Ollama 로컬 모델 — config.py MODEL_PROFILES 에서 한국어 메타 자동 추출
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
                summary_ko=profile.get("summary_ko", ""),
                use_when_ko=profile.get("use_when_ko", ""),
                use_case=_model_use_case(mid),  # type: ignore[arg-type]
            )
        )

    # Gemini Cloud 모델 — 3.5 Flash 단일 (GA 2026-05-19, 2.5 Pro/Flash 대체).
    # GEMINI_MODEL/GEMINI_MODEL_FLASH 둘 다 동일 ID — seen_ids 가 중복 제거하여 1개만 노출.
    gemini_key = bool(os.environ.get("GEMINI_API_KEY", "").strip())
    gemini_pro = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
    gemini_flash = os.environ.get("GEMINI_MODEL_FLASH", "gemini-3.5-flash")
    blocked_in_feature = _feature_b_blocks_gemini() and feature == "draft"

    gemini_variants: list[tuple[str, str]] = []
    seen_ids: set[str] = set()
    for variant_id in (gemini_pro, gemini_flash):
        if variant_id and variant_id not in seen_ids:
            gemini_variants.append((variant_id, _humanize_gemini(variant_id)))
            seen_ids.add(variant_id)

    for variant_id, variant_label in gemini_variants:
        gemini_meta = _GEMINI_META.get(variant_id, _GEMINI_META["_default"])
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
                    summary_ko=gemini_meta["summary_ko"],
                    use_when_ko=gemini_meta["use_when_ko"],
                    use_case=gemini_meta["use_case"],  # type: ignore[arg-type]
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
                    summary_ko=gemini_meta["summary_ko"],
                    use_when_ko=gemini_meta["use_when_ko"],
                    use_case=gemini_meta["use_case"],  # type: ignore[arg-type]
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
    if "3.5-flash" in mid:
        return "Gemini 3.5 Flash"
    if "2.5-pro" in mid:
        return "Gemini 2.5 Pro"
    if "2.5-flash" in mid:
        return "Gemini 2.5 Flash"
    return mid


# v3.5 — Gemini 한국어 호버 메타 (MODEL_PROFILES 에 미등록이라 별도 정적 dict).
# 2026-05-25: 2.5 Pro/Flash 제거 + 3.5 Flash 단일 (GA 2026-05-19 at Google I/O).
_GEMINI_META: dict[str, dict[str, str]] = {
    "gemini-3.5-flash": {
        "summary_ko": "Google Gemini 3.5 Flash — thinking 모드 + 1M 컨텍스트 + 빠른 응답.",
        "use_when_ko": "강당 발표·일반 업무·긴 컨텍스트 분석. 외부 LLM 허용 영역.",
        "use_case": "reasoning",
    },
    "_default": {
        "summary_ko": "Google Gemini 클라우드 모델.",
        "use_when_ko": "Wifi 정상 + 외부 LLM 허용 영역.",
        "use_case": "multilingual",
    },
}


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


@router.post("/invalidate-cache", dependencies=[Depends(require_role_level(5))])
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


# ───────────────────────────────────────────────────────────
# H1 v4.0 — 모델 카탈로그 (도움말 카드 데이터 단일 진실 원천)
# ───────────────────────────────────────────────────────────


@router.get("/catalog")
async def model_catalog():
    """전체 모델 메타데이터 카탈로그. 프론트 ModelHelpPopover / 비교 페이지용.

    config.py 의 MODEL_PROFILES 를 가공해 한국어 메타(summary_ko / use_when_ko /
    avoid_when_ko / tags_ko)를 포함한 카드 형태로 반환. 로그인 사용자 전용 정적 메타.
    """
    items = []
    for model_id, profile in MODEL_PROFILES.items():
        items.append(
            {
                "id": model_id,
                "display": profile.get("display", model_id),
                "size_gb": profile.get("size_gb", 0),
                "lang": profile.get("lang", "multilingual"),
                "vision": bool(profile.get("vision", False)),
                "speed": profile.get("speed", "medium"),
                "quality": profile.get("quality", "good"),
                "best_for": list(profile.get("best_for", [])),
                "tags_ko": list(profile.get("tags_ko", [])),
                "summary_ko": profile.get("summary_ko", ""),
                "use_when_ko": profile.get("use_when_ko", ""),
                "avoid_when_ko": profile.get("avoid_when_ko", ""),
            }
        )
    return {"items": items, "total": len(items)}


@router.get("/recommend")
async def recommend_model(
    feature: str = Query(default="draft"),
    department: str = Query(default=""),
    needs_vision: bool = Query(default=False),
    prefers_speed: bool = Query(default=False),
):
    """H1 휴리스틱 모델 추천.

    - 비전 필요 → gemma4:e2b/latest/26b (속도 vs 품질)
    - 한국어 격식 문서 (품질보증/법규/총무인사) → exaone3.5/exaone-deep
    - 일반 균형 → qwen3.5:9b
    - 속도 우선 → qwen3.5:4b 또는 gemma4:e2b
    """
    KOREAN_FORMAL_DEPTS = {"품질보증팀", "품질관리팀", "법무팀", "총무인사팀", "환경안전팀"}

    # 1) 비전 입력
    if needs_vision:
        primary = "gemma4:e2b" if prefers_speed else "gemma4:latest"
        reason = "이미지 입력이 필요해 비전 지원 모델을 추천합니다."
    # 2) 한국어 격식 문서 우선 부서
    elif department in KOREAN_FORMAL_DEPTS or feature == "compliance":
        primary = "exaone-deep:latest" if feature == "compliance" else "exaone3.5:latest"
        reason = "한국어 격식 표현·법규 추론 정확도를 우선해 EXAONE 계열을 추천합니다."
    # 3) 속도 우선
    elif prefers_speed:
        primary = "qwen3.5:4b"
        reason = "응답 속도 우선이라 경량 모델을 추천합니다."
    # 4) 기본 균형
    else:
        primary = "qwen3.5:9b"
        reason = "다국어 균형형 기본 모델을 추천합니다."

    profile = MODEL_PROFILES.get(primary, {})
    return {
        "recommended_model_id": primary,
        "display": profile.get("display", primary),
        "reason": reason,
        "input": {
            "feature": feature,
            "department": department,
            "needs_vision": needs_vision,
            "prefers_speed": prefers_speed,
        },
    }