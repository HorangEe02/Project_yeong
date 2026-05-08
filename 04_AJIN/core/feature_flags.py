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
    }
