"""v3.3 Feature C — 피처 플래그 노출 라우터 (Phase 0-4).

프런트엔드가 GET /api/feature-flags/c 로 현재 활성 플래그를 조회한다.
환경변수가 단일 진실 원천이며, 응답은 캐시 없이 매 요청마다 새로 읽는다.
"""

from fastapi import APIRouter

from core.feature_flags import (
    feature_c_flags_dict,
    feature_d_flags_dict,
    firebase_cost_flags_dict,
)

router = APIRouter(prefix="/feature-flags", tags=["feature-flags"])


@router.get("/c")
async def get_feature_c_flags():
    """Feature C(AI 업무 도우미) 플래그 8종을 dict 로 반환한다.

    프런트엔드 `useFeatureCFlags` 훅이 마운트 시 1회 호출하고
    Phase 별 UI 분기에 사용한다 (예: cad_upload=false 면 CAD accept 미적용).
    """
    return {
        "version": "v3.3",
        "feature": "C",
        "flags": feature_c_flags_dict(),
    }


@router.get("/d")
async def get_feature_d_flags():
    """Feature D(법규 모니터링) 플래그를 dict 로 반환한다.

    Returns:
        dict: D1 MVP와 D2~D5 봉인 상태를 담은 프런트엔드용 응답.
    """
    return {
        "version": "p2-d1-mvp",
        "feature": "D",
        "flags": feature_d_flags_dict(),
    }


@router.get("/firebase-cost")
async def get_firebase_cost_flags():
    """Firebase 비용 차단 플래그를 반환한다.

    Returns:
        dict: 신규 Firebase write 차단 여부와 read fallback 상태.
    """
    return {
        "version": "firebase-to-supabase-phase0",
        "feature": "firebase-cost",
        "flags": firebase_cost_flags_dict(),
    }
