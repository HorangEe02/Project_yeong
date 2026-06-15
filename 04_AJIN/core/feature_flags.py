"""v3.3 Feature C — 피처 플래그 (Phase 0-4).

환경변수로 단계별 롤아웃을 제어한다.
- 기본값은 모두 False (안전한 점진 활성화).
- Phase별 머지 후 .env 또는 docker-compose 환경변수로 개별 토글.
- 롤백: 환경변수 한 줄 변경 + 서버 재시작 (5분 이내 복구 보장).

(주의) `core/feature_bridge.py` 는 Streamlit 구버전 모듈이며 본 모듈과 무관하다.
React 프런트엔드 + FastAPI 백엔드는 본 파일을 단일 진실 원천으로 사용한다.
"""

import os
from dataclasses import dataclass


def _truthy(v: str | None) -> bool:
    return (v or "").strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class FeatureCFlags:
    """Feature C — AI 업무 도우미 v3.3 플래그 묶음."""

    # Phase A — 멀티 LLM 셀렉터 + 비교 모드
    multi_llm: bool
    compare_mode: bool

    # Phase B — 부서 컨텍스트 RBAC + 본부 경계
    dept_lock: bool
    division_boundary: bool

    # Phase C — 업무 모드 풀화면 레이아웃
    work_fullscreen: bool

    # Phase D — Quick Questions 개인화
    quick_questions_v2: bool

    # Phase E·F — 인-챗 액션 카드 (5종)
    inline_actions: bool

    # Phase G — CAD/HWP 업로드 확장
    cad_upload: bool

    # v4.7 C reliability — department-specific analyzers are sealed by default.
    analyzers_enabled: bool


@dataclass(frozen=True)
class FeatureDFlags:
    """Feature D 플래그 묶음.

    Attributes:
        d1_alerts: 변경감지, 크롤러 실행, 변경 피드, 알림 MVP 활성 여부.
        d2_rag: 규정 검색, 문서, RAG, 판례/계약 분석 활성 여부.
        d3_whatif: What-if, 관세, 시나리오 시뮬레이션 활성 여부.
        d4_workflow: 협업 티켓, 결재, 학습, SOP, 보고서 활성 여부.
        d5_supply: 공급망, 협력사, 산업 트렌드 활성 여부.
    """

    d1_alerts: bool
    d2_rag: bool
    d3_whatif: bool
    d4_workflow: bool
    d5_supply: bool


@dataclass(frozen=True)
class FirebaseCostFlags:
    """Firebase 비용 차단 플래그 묶음.

    Attributes:
        write_enabled: Firestore, RTDB, Storage 신규 쓰기 허용 여부.
        read_fallback_enabled: Firebase read-only fallback 허용 여부.
        dryrun_capture_enabled: RTDB write 차단 시 로컬 dry-run 캡처 허용 여부.
    """

    write_enabled: bool
    read_fallback_enabled: bool
    dryrun_capture_enabled: bool


def load_feature_c_flags() -> FeatureCFlags:
    """환경변수에서 v3.3 Feature C 플래그를 로드한다.

    각 플래그는 독립이며, 일부만 켜져 있어도 안전하게 동작해야 한다 (방어적 분기).
    """
    return FeatureCFlags(
        multi_llm=_truthy(os.environ.get("FEATURE_C_MULTI_LLM")),
        compare_mode=_truthy(os.environ.get("FEATURE_C_COMPARE_MODE")),
        dept_lock=_truthy(os.environ.get("FEATURE_C_DEPT_LOCK")),
        division_boundary=_truthy(os.environ.get("FEATURE_C_DIVISION_BOUNDARY")),
        work_fullscreen=_truthy(os.environ.get("FEATURE_C_WORK_FULLSCREEN")),
        quick_questions_v2=_truthy(os.environ.get("FEATURE_C_QUICK_QUESTIONS_V2")),
        inline_actions=_truthy(os.environ.get("FEATURE_C_INLINE_ACTIONS")),
        cad_upload=_truthy(os.environ.get("FEATURE_C_CAD_UPLOAD")),
        analyzers_enabled=_truthy(os.environ.get("FEATURE_C_ANALYZERS_ENABLED")),
    )


def load_feature_d_flags() -> FeatureDFlags:
    """환경변수에서 Feature D 플래그를 로드한다.

    Returns:
        FeatureDFlags: D1은 기본 활성, D2~D5는 기본 비활성인 런타임 플래그.
    """
    return FeatureDFlags(
        d1_alerts=_truthy(os.environ.get("FEATURE_D_D1_ALERTS", "true")),
        d2_rag=_truthy(os.environ.get("FEATURE_D_D2_RAG")),
        d3_whatif=_truthy(os.environ.get("FEATURE_D_D3_WHATIF")),
        d4_workflow=_truthy(os.environ.get("FEATURE_D_D4_WORKFLOW")),
        d5_supply=_truthy(os.environ.get("FEATURE_D_D5_SUPPLY")),
    )


def load_firebase_cost_flags() -> FirebaseCostFlags:
    """환경변수에서 Firebase 비용 차단 플래그를 로드한다.

    Returns:
        FirebaseCostFlags: 신규 Firebase write는 기본 차단, read fallback은
        임시 호환 경로로 기본 허용하는 런타임 플래그.
    """
    return FirebaseCostFlags(
        write_enabled=_truthy(os.environ.get("FIREBASE_WRITE_ENABLED")),
        read_fallback_enabled=_truthy(os.environ.get("FIREBASE_READ_FALLBACK_ENABLED", "true")),
        dryrun_capture_enabled=_truthy(os.environ.get("FIREBASE_DRYRUN_CAPTURE_ENABLED", "true")),
    )


def feature_c_flags_dict() -> dict[str, bool]:
    """프런트엔드로 노출할 dict 형태."""
    flags = load_feature_c_flags()
    return {
        "multi_llm": flags.multi_llm,
        "compare_mode": flags.compare_mode,
        "dept_lock": flags.dept_lock,
        "division_boundary": flags.division_boundary,
        "work_fullscreen": flags.work_fullscreen,
        "quick_questions_v2": flags.quick_questions_v2,
        "inline_actions": flags.inline_actions,
        "cad_upload": flags.cad_upload,
        "analyzers_enabled": flags.analyzers_enabled,
    }


def firebase_cost_flags_dict() -> dict[str, bool]:
    """프런트엔드와 system health가 소비할 Firebase 비용 플래그 dict.

    Returns:
        dict[str, bool]: Firebase write/read fallback/dry-run 활성 상태.
    """
    flags = load_firebase_cost_flags()
    return {
        "write_enabled": flags.write_enabled,
        "read_fallback_enabled": flags.read_fallback_enabled,
        "dryrun_capture_enabled": flags.dryrun_capture_enabled,
    }


def firebase_writes_enabled() -> bool:
    """Firebase 신규 write 허용 여부를 반환한다.

    Returns:
        bool: `FIREBASE_WRITE_ENABLED=true`일 때만 True.
    """
    return load_firebase_cost_flags().write_enabled


def firebase_read_fallback_enabled() -> bool:
    """Firebase read-only fallback 허용 여부를 반환한다.

    Returns:
        bool: `FIREBASE_READ_FALLBACK_ENABLED`가 truthy이거나 기본값일 때 True.
    """
    return load_firebase_cost_flags().read_fallback_enabled


def feature_d_flags_dict() -> dict[str, bool]:
    """프런트엔드와 OpenAPI 생성에서 사용할 Feature D 플래그 dict.

    Returns:
        dict[str, bool]: Feature D 하위 축별 활성 상태.
    """
    flags = load_feature_d_flags()
    return {
        "d1_alerts": flags.d1_alerts,
        "d2_rag": flags.d2_rag,
        "d3_whatif": flags.d3_whatif,
        "d4_workflow": flags.d4_workflow,
        "d5_supply": flags.d5_supply,
    }
