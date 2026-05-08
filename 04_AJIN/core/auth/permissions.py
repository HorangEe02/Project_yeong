"""
세분화 권한 엔진 — 기능별·동작별·부서별·역할별 접근 제어

설계 원칙:
  1. 권한은 "feature.action" 형태의 문자열로 정의
  2. 각 권한에 최소 역할(min_role) + 허용 부서(departments) 지정
  3. departments=None이면 전 부서 허용
  4. 역할 계층: EMPLOYEE < MANAGER < TEAM_LEAD < HR_ADMIN < SYS_ADMIN
  5. 판정 함수는 UserContext만 받아서 bool 반환
"""
from typing import Optional, Set
from dataclasses import dataclass

from core.auth.user_context import UserContext


# ── RBAC 역할 계층 (숫자가 클수록 고권한) ──
ROLE_HIERARCHY = {
    "INACTIVE": 0,
    "EMPLOYEE": 1,
    "MANAGER": 2,
    "TEAM_LEAD": 3,
    "HR_ADMIN": 4,
    "SYS_ADMIN": 5,
}


@dataclass
class Permission:
    """단일 권한 정의"""
    key: str                               # 예: "compliance.run_crawler"
    description: str                       # 설명
    min_role: str                          # 최소 역할 (예: "TEAM_LEAD")
    departments: Optional[Set[str]]        # 허용 부서 (None=전체)
    allow_same_division: bool = False      # 같은 본부면 부서 제한 완화
    min_position_level: int = 0            # v3.3: 최소 직급 레벨 (0=무관, 3=대리+, 4=과장+, 6=부장+)


# ═══════════════════════════════════════════════
# 기능 D — 법규/규정 모니터링
# ═══════════════════════════════════════════════

COMPLIANCE_DEPARTMENTS = {
    "ESG경영팀", "품질보증팀", "품질경영팀",
    "안전보건팀", "구매팀",
}

COMPLIANCE_PERMISSIONS = {
    # ── Tier 1: VIEW (전체) ──
    "compliance.view_dashboard": Permission(
        key="compliance.view_dashboard",
        description="규제 대시보드 조회",
        min_role="EMPLOYEE",
        departments=None,
    ),
    "compliance.view_scenarios": Permission(
        key="compliance.view_scenarios",
        description="시나리오 목록 열람",
        min_role="EMPLOYEE",
        departments=None,
    ),
    "compliance.view_facility": Permission(
        key="compliance.view_facility",
        description="시설/공장 정보 조회",
        min_role="EMPLOYEE",
        departments=None,
    ),
    "compliance.view_reports": Permission(
        key="compliance.view_reports",
        description="규제 보고서 조회 (읽기 전용)",
        min_role="EMPLOYEE",
        departments=None,
    ),

    # ── Tier 2: ANALYZE (관련 부서 대리+ 또는 MANAGER+) ──
    "compliance.run_analysis": Permission(
        key="compliance.run_analysis",
        description="규제 영향 분석 실행",
        min_role="EMPLOYEE",
        departments=COMPLIANCE_DEPARTMENTS,
        min_position_level=3,  # v3.3: 대리+
    ),
    "compliance.generate_report": Permission(
        key="compliance.generate_report",
        description="규제 문서 생성 (DOCX/PDF)",
        min_role="EMPLOYEE",
        departments=COMPLIANCE_DEPARTMENTS,
        min_position_level=3,  # v3.3: 대리+
    ),
    "compliance.run_simulation": Permission(
        key="compliance.run_simulation",
        description="관세 영향 시뮬레이션 실행",
        min_role="MANAGER",
        departments=COMPLIANCE_DEPARTMENTS,
        min_position_level=4,  # v3.3: 과장+
    ),
    "compliance.run_us_simulation": Permission(
        key="compliance.run_us_simulation",
        description="미국 관세 시뮬레이터 실행",
        min_role="EMPLOYEE",
        departments={"해외지원팀", "구매팀", "영업팀", "ESG경영팀"},
        min_position_level=3,  # v3.3: 대리+
    ),
    "compliance.download_report": Permission(
        key="compliance.download_report",
        description="규제 보고서 다운로드",
        min_role="EMPLOYEE",
        departments=COMPLIANCE_DEPARTMENTS,
    ),

    # ── Tier 3: OPERATE (관련 부서 차장+/부장+) ──
    "compliance.run_crawler": Permission(
        key="compliance.run_crawler",
        description="크롤러 실행 (Run All / Run Selected)",
        min_role="TEAM_LEAD",
        departments={"ESG경영팀", "품질경영팀"},
        min_position_level=5,  # v3.3: 차장+
    ),
    "compliance.delete_data": Permission(
        key="compliance.delete_data",
        description="크롤링 데이터 RESET/삭제",
        min_role="TEAM_LEAD",
        departments={"ESG경영팀"},
        min_position_level=6,  # v3.3: 부장+ (불가역적 삭제)
    ),
    "compliance.edit_mapping": Permission(
        key="compliance.edit_mapping",
        description="시설-규제 매핑 편집",
        min_role="TEAM_LEAD",
        departments={"ESG경영팀", "품질경영팀"},
        min_position_level=5,  # v3.3: 차장+
    ),
    "compliance.manage_snapshots": Permission(
        key="compliance.manage_snapshots",
        description="버전 스냅샷 관리",
        min_role="TEAM_LEAD",
        departments={"ESG경영팀", "품질경영팀"},
        min_position_level=5,  # v3.3: 차장+
    ),
}


# ═══════════════════════════════════════════════
# 기능 E — 인사 관리
# ═══════════════════════════════════════════════

HR_DEPARTMENTS = {"총무인사팀"}

ADMIN_PERMISSIONS = {
    # ── Tier 1: SELF (전체) ──
    "admin.view_self": Permission(
        key="admin.view_self",
        description="자기 정보 조회",
        min_role="EMPLOYEE",
        departments=None,
    ),
    "admin.edit_self_password": Permission(
        key="admin.edit_self_password",
        description="자기 비밀번호 변경",
        min_role="EMPLOYEE",
        departments=None,
    ),
    "admin.edit_self_contact": Permission(
        key="admin.edit_self_contact",
        description="자기 이메일/연락처 수정",
        min_role="EMPLOYEE",
        departments=None,
    ),

    # ── Tier 2: TEAM (TEAM_LEAD+ 과장 이상) ──
    "admin.view_team": Permission(
        key="admin.view_team",
        description="자기 팀 인원 목록 조회",
        min_role="TEAM_LEAD",
        departments=None,
        min_position_level=4,  # v3.3: 과장+
    ),
    "admin.view_team_contact": Permission(
        key="admin.view_team_contact",
        description="자기 팀 인원 연락처 열람",
        min_role="TEAM_LEAD",
        departments=None,
        min_position_level=4,  # v3.3: 과장+
    ),
    "admin.view_login_history_team": Permission(
        key="admin.view_login_history_team",
        description="자기 팀 로그인 이력 조회",
        min_role="TEAM_LEAD",
        departments=None,
        min_position_level=4,  # v3.3: 과장+
    ),

    # ── Tier 3: DEPT (MANAGER + 총무인사팀 + 직급 조건) ──
    "admin.edit_user_contact": Permission(
        key="admin.edit_user_contact",
        description="사용자 이메일/연락처 수정",
        min_role="MANAGER",
        departments=HR_DEPARTMENTS,
        min_position_level=4,  # v3.3: 과장+
    ),
    "admin.edit_user_department": Permission(
        key="admin.edit_user_department",
        description="사용자 부서 이동",
        min_role="MANAGER",
        departments=HR_DEPARTMENTS,
        min_position_level=5,  # v3.3: 차장+ (인사 발령은 고직급)
    ),
    "admin.reset_password": Permission(
        key="admin.reset_password",
        description="사용자 비밀번호 초기화",
        min_role="MANAGER",
        departments=HR_DEPARTMENTS,
        min_position_level=4,  # v3.3: 과장+
    ),
    "admin.view_all_users": Permission(
        key="admin.view_all_users",
        description="전체 사용자 목록 조회",
        min_role="MANAGER",
        departments=HR_DEPARTMENTS,
        min_position_level=4,  # v3.3: 과장+
    ),
    "admin.view_login_history_all": Permission(
        key="admin.view_login_history_all",
        description="전체 로그인 이력 조회",
        min_role="MANAGER",
        departments=HR_DEPARTMENTS,
        min_position_level=5,  # v3.3: 차장+ (전사 감사 로그)
    ),

    # ── v3.3: 보안 모니터링 — 총무인사팀 + IT전략팀 ──
    "admin.view_security": Permission(
        key="admin.view_security",
        description="보안 감사 대시보드 조회",
        min_role="MANAGER",
        departments={"총무인사팀", "IT전략팀"},
        min_position_level=4,  # 과장+
    ),

    # ── Tier 4: SYSTEM (SYS_ADMIN / HR_ADMIN + 직급 조건) ──
    "admin.create_user": Permission(
        key="admin.create_user",
        description="사용자 생성",
        min_role="MANAGER",                # v3.3: HR_ADMIN → MANAGER (총무인사팀 과장 허용)
        departments=HR_DEPARTMENTS,        # v3.3: 총무인사팀만 (HR_ADMIN/SYS_ADMIN은 우회)
        min_position_level=4,              # v3.3: 과장+
    ),
    "admin.delete_user": Permission(
        key="admin.delete_user",
        description="사용자 삭제/비활성화",
        min_role="HR_ADMIN",
        departments=None,
        min_position_level=6,  # v3.3: 부장+ (불가역적 삭제)
    ),
    "admin.change_role": Permission(
        key="admin.change_role",
        description="RBAC 역할 변경",
        min_role="SYS_ADMIN",
        departments=None,
    ),
    "admin.change_status": Permission(
        key="admin.change_status",
        description="사용자 활성/비활성 상태 변경",
        min_role="HR_ADMIN",
        departments=None,
        min_position_level=5,  # v3.3: 차장+ (계정 비활성화는 고직급)
    ),
    "admin.bulk_operations": Permission(
        key="admin.bulk_operations",
        description="테스트 계정 일괄 생성 등 관리 도구",
        min_role="SYS_ADMIN",
        departments=None,
    ),
}


# ═══════════════════════════════════════════════
# v3.3: 메뉴 표시 부서 제한 — Feature D, F
# ═══════════════════════════════════════════════

# Feature D (법규 모니터링) — 관련 부서만 사이드바에 표시
COMPLIANCE_MENU_DEPARTMENTS = {
    "ESG경영팀", "품질보증팀", "품질경영팀", "안전보건팀",
    "구매팀", "해외지원팀", "상생협력팀",
    "영업팀",  # v3.3: 미국 규제 시뮬레이터 사용을 위해 추가
}

# Feature F (설비/공정 AI) — 생산/설비/기술 관련 부서만 표시
EQUIPMENT_MENU_DEPARTMENTS = {
    "품질보증팀", "안전보건팀", "생산관리팀", "생산기술팀",
    "자동화기술팀", "비전연구팀", "부품개발팀", "금형생산팀",
    "제품설계팀", "공법계획팀", "용기운영팀",
    "FA사업팀", "플랜트사업팀", "자재관리팀",
}

# slug → 허용 부서 매핑 (None = 전 부서 표시)
MENU_DEPARTMENT_FILTER: dict[str, Optional[Set[str]]] = {
    "search":     None,
    "draft":      None,
    "onboarding": None,
    "compliance": COMPLIANCE_MENU_DEPARTMENTS,
    "admin":      None,   # role_level로 제어 (기존 유지)
    "equipment":  EQUIPMENT_MENU_DEPARTMENTS,
}


def is_menu_visible(slug: str, user_department: str, user_role: str) -> bool:
    """v3.3: 사이드바 메뉴 표시 여부를 부서 기반으로 판정한다.

    SYS_ADMIN / HR_ADMIN은 항상 True (전체 접근).
    """
    # 고권한 역할은 모든 메뉴 접근 가능
    if user_role in ("SYS_ADMIN", "HR_ADMIN"):
        return True

    allowed_depts = MENU_DEPARTMENT_FILTER.get(slug)
    if allowed_depts is None:
        return True  # 부서 제한 없음

    return user_department in allowed_depts


# ═══════════════════════════════════════════════
# v3.3: 기능 F — 설비/공정 AI (3-Tier)
# ═══════════════════════════════════════════════

# 부서별 Tier 상한 그룹
EQUIPMENT_FULL_TIER_DEPARTMENTS = {
    "생산관리팀", "생산기술팀", "품질보증팀", "안전보건팀",
    "자동화기술팀", "금형생산팀", "FA사업팀",
}  # Tier 3 (MANAGE) 까지

EQUIPMENT_OPERATE_DEPARTMENTS = {
    "부품개발팀", "자재관리팀", "비전연구팀",
    "공법계획팀", "플랜트사업팀",
}  # Tier 2 (OPERATE) 까지

EQUIPMENT_VIEW_DEPARTMENTS = {
    "제품설계팀", "용기운영팀",
}  # Tier 1 (VIEW) 까지

# 전체 허용 부서 (메뉴 표시용 — 기존 EQUIPMENT_MENU_DEPARTMENTS와 동일)
_ALL_EQUIPMENT_DEPARTMENTS = (
    EQUIPMENT_FULL_TIER_DEPARTMENTS
    | EQUIPMENT_OPERATE_DEPARTMENTS
    | EQUIPMENT_VIEW_DEPARTMENTS
)

EQUIPMENT_PERMISSIONS = {
    # ── Tier 1: VIEW (관련 부서 전원) ──
    "equipment.view_dashboard": Permission(
        key="equipment.view_dashboard",
        description="설비 개요 대시보드 조회",
        min_role="EMPLOYEE",
        departments=_ALL_EQUIPMENT_DEPARTMENTS,
    ),
    "equipment.view_error_codes": Permission(
        key="equipment.view_error_codes",
        description="에러코드 직접 조회 / 키워드 검색",
        min_role="EMPLOYEE",
        departments=_ALL_EQUIPMENT_DEPARTMENTS,
    ),
    "equipment.view_templates": Permission(
        key="equipment.view_templates",
        description="점검 템플릿 목록 조회",
        min_role="EMPLOYEE",
        departments=_ALL_EQUIPMENT_DEPARTMENTS,
    ),

    # ── Tier 2: OPERATE (관련 부서 대리 이상, position_level >= 3) ──
    "equipment.run_ml_search": Permission(
        key="equipment.run_ml_search",
        description="ML 증상 검색 + 마르코프 예측 실행",
        min_role="EMPLOYEE",
        departments=_ALL_EQUIPMENT_DEPARTMENTS - EQUIPMENT_VIEW_DEPARTMENTS,
        min_position_level=3,  # 대리+
    ),
    "equipment.run_rag": Permission(
        key="equipment.run_rag",
        description="매뉴얼 RAG 검색 + AI 답변 생성",
        min_role="EMPLOYEE",
        departments=_ALL_EQUIPMENT_DEPARTMENTS - EQUIPMENT_VIEW_DEPARTMENTS,
        min_position_level=3,
    ),
    "equipment.view_inspections": Permission(
        key="equipment.view_inspections",
        description="점검 이력 조회",
        min_role="EMPLOYEE",
        departments=_ALL_EQUIPMENT_DEPARTMENTS - EQUIPMENT_VIEW_DEPARTMENTS,
        min_position_level=3,
    ),
    "equipment.view_maintenance_detail": Permission(
        key="equipment.view_maintenance_detail",
        description="예측 정비 상세 테이블 / 비용 TOP 5 조회",
        min_role="EMPLOYEE",
        departments=_ALL_EQUIPMENT_DEPARTMENTS - EQUIPMENT_VIEW_DEPARTMENTS,
        min_position_level=3,
    ),

    # ── Tier 3: MANAGE (핵심 부서 과장 이상, position_level >= 4) ──
    "equipment.save_inspection": Permission(
        key="equipment.save_inspection",
        description="신규 점검 입력 및 저장",
        min_role="MANAGER",
        departments=EQUIPMENT_FULL_TIER_DEPARTMENTS,
        min_position_level=4,  # 과장+
    ),
}


# ── 전체 권한 레지스트리 ──
ALL_PERMISSIONS: dict[str, Permission] = {}
ALL_PERMISSIONS.update(COMPLIANCE_PERMISSIONS)
ALL_PERMISSIONS.update(ADMIN_PERMISSIONS)
ALL_PERMISSIONS.update(EQUIPMENT_PERMISSIONS)


# ═══════════════════════════════════════════════
# 판정 함수
# ═══════════════════════════════════════════════

def check_permission(
    user_ctx: Optional[UserContext],
    permission_key: str,
    target_department: Optional[str] = None,
) -> bool:
    """
    사용자가 특정 권한을 가지고 있는지 판정합니다.

    Args:
        user_ctx: 현재 사용자 (None → 거부)
        permission_key: 권한 키 (예: "compliance.run_crawler")
        target_department: 대상 부서 (팀 조회 시 자기 팀 여부 판단용)

    Returns:
        True = 허용, False = 거부
    """
    if not user_ctx:
        return False

    perm = ALL_PERMISSIONS.get(permission_key)
    if not perm:
        return False

    # SYS_ADMIN은 항상 통과
    if user_ctx.role == "SYS_ADMIN":
        return True

    # HR_ADMIN도 admin.* 과 equipment.* 에서 우회 (단, 직급 조건은 유지)
    if user_ctx.role == "HR_ADMIN":
        if permission_key.startswith("admin.") or permission_key.startswith("equipment."):
            # v3.3: 직급 조건이 있는 위험 작업은 직급 검사 통과 필요
            if perm.min_position_level > 0:
                user_pos_level = getattr(user_ctx, "position_level", 0)
                if user_pos_level < perm.min_position_level:
                    return False
            return True

    # 역할 계층 검사
    user_level = ROLE_HIERARCHY.get(user_ctx.role, 0)
    min_level = ROLE_HIERARCHY.get(perm.min_role, 0)

    if user_level < min_level:
        return False

    # v3.3: 직급 레벨 검사
    if perm.min_position_level > 0:
        user_pos_level = getattr(user_ctx, "position_level", 0)
        if user_pos_level < perm.min_position_level:
            return False

    # 부서 제한 검사
    if perm.departments is not None:
        if user_ctx.department not in perm.departments:
            # HR_ADMIN은 admin.* 권한에 대해 부서 제한 면제
            if user_ctx.role == "HR_ADMIN" and permission_key.startswith("admin."):
                return True
            # MANAGER 이상은 Tier 2 compliance 접근 가능 (관련 부서 아니어도)
            # v3.3: run_us_simulation은 부서 제한 엄격 적용 (우회 제외)
            _strict_dept_perms = {"compliance.run_us_simulation"}
            if (user_level >= ROLE_HIERARCHY.get("MANAGER", 2)
                    and permission_key.startswith("compliance.")
                    and min_level <= ROLE_HIERARCHY.get("MANAGER", 2)
                    and permission_key not in _strict_dept_perms):
                return True
            return False

    # 팀 조회 시 자기 팀인지 확인
    if target_department and permission_key in ("admin.view_team", "admin.view_team_contact", "admin.view_login_history_team"):
        if user_ctx.department != target_department:
            # TEAM_LEAD는 자기 팀만, HR_ADMIN 이상은 전체
            if user_level < ROLE_HIERARCHY.get("HR_ADMIN", 4):
                return False

    return True


def get_user_permissions(user_ctx: Optional[UserContext]) -> dict[str, bool]:
    """사용자가 가진 모든 권한을 딕셔너리로 반환합니다."""
    if not user_ctx:
        return {key: False for key in ALL_PERMISSIONS}

    return {
        key: check_permission(user_ctx, key)
        for key in ALL_PERMISSIONS
    }


def get_permission_tier(user_ctx: Optional[UserContext], feature: str) -> int:
    """
    사용자의 기능별 접근 Tier를 반환합니다.

    Args:
        feature: "compliance", "admin", 또는 "equipment"

    Returns:
        0 = 접근 불가, 1~4 = Tier 레벨
    """
    if not user_ctx:
        return 0

    if feature == "compliance":
        if check_permission(user_ctx, "compliance.run_crawler"):
            return 3  # OPERATE
        elif check_permission(user_ctx, "compliance.run_analysis"):
            return 2  # ANALYZE
        elif check_permission(user_ctx, "compliance.view_dashboard"):
            return 1  # VIEW
        return 0

    elif feature == "admin":
        # v3.3: Tier 4는 change_role(SYS_ADMIN만)로 판정 (create_user가 MANAGER로 확장됨)
        if check_permission(user_ctx, "admin.change_role"):
            return 4  # SYSTEM (SYS_ADMIN)
        elif check_permission(user_ctx, "admin.create_user"):
            return 4  # SYSTEM (HR_ADMIN 또는 총무인사팀 과장+)
        elif check_permission(user_ctx, "admin.edit_user_contact"):
            return 3  # DEPT
        elif check_permission(user_ctx, "admin.view_team"):
            return 2  # TEAM
        elif check_permission(user_ctx, "admin.view_self"):
            return 1  # SELF
        return 0

    elif feature == "equipment":
        if check_permission(user_ctx, "equipment.save_inspection"):
            return 3  # MANAGE
        elif check_permission(user_ctx, "equipment.run_ml_search"):
            return 2  # OPERATE
        elif check_permission(user_ctx, "equipment.view_dashboard"):
            return 1  # VIEW
        return 0

    return 0


def require_permission(permission_key: str):
    """
    데코레이터 — 함수 실행 전 권한을 검사합니다.
    Streamlit 페이지 함수에서 사용합니다.

    사용 예:
        @require_permission("compliance.run_crawler")
        def run_crawler():
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            from core.auth.user_context import get_user_context_from_session
            user_ctx = get_user_context_from_session()

            if not check_permission(user_ctx, permission_key):
                import streamlit as st
                perm = ALL_PERMISSIONS.get(permission_key)
                desc = perm.description if perm else permission_key
                st.warning(f"권한이 필요합니다: {desc}")
                return None

            return func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator


def get_tier_label(feature: str, tier: int) -> str:
    """Tier 번호를 사람이 읽을 수 있는 라벨로 변환"""
    labels = {
        "compliance": {0: "접근 불가", 1: "열람", 2: "분석", 3: "운영"},
        "admin": {0: "접근 불가", 1: "개인", 2: "팀 조회", 3: "부서 관리", 4: "시스템 관리"},
        "equipment": {0: "접근 불가", 1: "열람", 2: "운영", 3: "관리"},
    }
    return labels.get(feature, {}).get(tier, f"Tier {tier}")
