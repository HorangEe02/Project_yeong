"""
가시성 판단 엔진 — 정보 노출 범위를 RBAC + 부서 관계로 결정

3계층 모델:
  FULL    — 모든 필드 표시 (이메일, 전화, 입사일 등)
  PARTIAL — 이름/부서/직급/내선만 표시
  HIDDEN  — 표시하지 않음 (비활성 사용자 등)

판단 기준:
  1. 대상이 INACTIVE → HIDDEN
  2. 비로그인 → PARTIAL
  3. 관리자(SYS_ADMIN/HR_ADMIN) → FULL
  4. TEAM_LEAD → FULL (전 부서)
  5. 같은 부서 → FULL
  6. 같은 본부 → PARTIAL
  7. 기본 → PARTIAL
"""
from enum import Enum
from typing import Optional

from core.auth.user_context import UserContext, DEPARTMENT_TO_DIVISION


class VisibilityLevel(Enum):
    FULL = "full"         # 전체 정보 열람
    PARTIAL = "partial"   # 기본 정보만 (이름/부서/직급/내선)
    HIDDEN = "hidden"     # 비표시


# ── 필드별 가시성 매핑 ──
FIELD_VISIBILITY = {
    # FULL에서만 보이는 필드
    "full_only": [
        "email", "phone", "hire_date", "resign_date",
        "overseas_assignment", "language_skills",
    ],
    # PARTIAL에서도 보이는 필드
    "partial": [
        "name", "department", "position", "extension", "site",
    ],
    # 항상 보이는 필드
    "always": [
        "name", "department", "position",
    ],
}


def determine_visibility(
    viewer: Optional[UserContext],
    target_department: str,
    target_role: str = "EMPLOYEE",
) -> VisibilityLevel:
    """
    현재 사용자(viewer)가 대상 부서/역할의 정보를 어느 수준까지 볼 수 있는지 판단합니다.

    Args:
        viewer: 조회하는 사용자 (None이면 비로그인 → PARTIAL)
        target_department: 조회 대상의 부서
        target_role: 조회 대상의 RBAC 역할

    Returns:
        VisibilityLevel
    """
    # 대상이 비활성이면 HIDDEN
    if target_role == "INACTIVE":
        return VisibilityLevel.HIDDEN

    # 비로그인 → PARTIAL
    if not viewer:
        return VisibilityLevel.PARTIAL

    # 관리자 → 항상 FULL
    if viewer.is_admin:
        return VisibilityLevel.FULL

    # TEAM_LEAD → 항상 FULL
    if viewer.is_leader:
        return VisibilityLevel.FULL

    # 같은 부서 → FULL
    if viewer.department == target_department:
        return VisibilityLevel.FULL

    # 같은 본부 → PARTIAL (내선번호까지)
    viewer_div = DEPARTMENT_TO_DIVISION.get(viewer.department, "")
    target_div = DEPARTMENT_TO_DIVISION.get(target_department, "")
    if viewer_div and viewer_div == target_div:
        return VisibilityLevel.PARTIAL

    # 기본: PARTIAL
    return VisibilityLevel.PARTIAL


def filter_employee_fields(
    employee: dict,
    visibility: VisibilityLevel,
) -> dict:
    """
    가시성 레벨에 따라 사원 정보 필드를 필터링합니다.

    FULL → 모든 필드
    PARTIAL → 이름/부서/직급/내선만 + 마스킹된 이메일
    HIDDEN → 빈 딕셔너리
    """
    if visibility == VisibilityLevel.HIDDEN:
        return {}

    if visibility == VisibilityLevel.FULL:
        return employee.copy()

    # PARTIAL: 기본 필드만 + 민감 필드 마스킹
    filtered = {}
    partial_fields = set(FIELD_VISIBILITY["partial"])

    for key, val in employee.items():
        if key in partial_fields:
            filtered[key] = val
        elif key == "email":
            # 이메일 마스킹: hong@ajin.co.kr → h***@ajin.co.kr
            if val and "@" in str(val):
                local, domain = str(val).split("@", 1)
                filtered[key] = f"{local[0]}***@{domain}"
            else:
                filtered[key] = "***"
        elif key == "phone":
            filtered[key] = "(내선번호로 연락)"
        elif key in ("hire_date", "resign_date"):
            filtered[key] = None  # 숨김
        else:
            # id 등 내부 키는 유지
            filtered[key] = val

    return filtered


def get_visibility_notice(visibility: VisibilityLevel) -> str:
    """사용자에게 표시할 가시성 안내 메시지"""
    if visibility == VisibilityLevel.PARTIAL:
        return "상세 연락처는 같은 부서 또는 팀장 이상만 열람 가능합니다."
    return ""


def get_visibility_badge(visibility: VisibilityLevel) -> str:
    """가시성 레벨을 배지 텍스트로 변환"""
    badges = {
        VisibilityLevel.FULL: "전체 열람",
        VisibilityLevel.PARTIAL: "기본 정보",
        VisibilityLevel.HIDDEN: "비표시",
    }
    return badges.get(visibility, "")
