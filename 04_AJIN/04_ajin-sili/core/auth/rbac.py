"""RBAC (역할 기반 접근 제어) — 6단계 역할 체계

Level 0: INACTIVE — 비활성
Level 1: EMPLOYEE — 일반 사원 (기본)
Level 2: MANAGER — 관리자급 (과장 이상)
Level 3: TEAM_LEAD — 팀장
Level 4: HR_ADMIN — 인사 관리자
Level 5: SYS_ADMIN — 시스템 관리자
"""

# 역할별 최소 레벨 요구
ROLE_HIERARCHY = {
    "INACTIVE": 0,
    "EMPLOYEE": 1,
    "MANAGER": 2,
    "TEAM_LEAD": 3,
    "HR_ADMIN": 4,
    "SYS_ADMIN": 5,
}

# 기능별 최소 접근 레벨
FEATURE_PERMISSIONS = {
    # 기능 A: 인원 검색 — 전 사원 접근 가능
    "search": 1,
    # 기능 B: 문서 검색/작성 — 전 사원 접근 가능
    "draft": 1,
    # 기능 C: 온보딩 챗봇 — 전 사원 접근 가능
    "onboarding": 1,
    # 기능 D: 규정 준수 — v3.0: 전 사원 열람 가능 (내부 Tier 제어)
    "compliance": 1,
    # 대시보드 — 전 사원 접근 가능
    "dashboard": 1,
    # 인사 관리 — v3.0: TEAM_LEAD 이상 (내부에서 Tier별 세분화)
    "admin": 3,
    # 기능 F: 설비/공정 — 전 사원 접근 가능
    "equipment": 1,
}

# 사이드바 메뉴별 표시 조건
MENU_PERMISSIONS = {
    "대시보드": 1,
    "A. 인원 검색": 1,
    "B. 문서 검색/작성": 1,
    "C. AI 업무 도우미": 1,
    "D. 법규 모니터링": 1,  # v3.0: 전 사원 열람 (내부 Tier 제어)
    "E. 인사 관리": 3,  # v3.0: TEAM_LEAD부터 (자기 팀 조회)
    "F. 설비/공정 AI": 1,
}


def check_permission(role_level: int, feature: str) -> bool:
    """사용자 역할 레벨이 기능 접근 최소 레벨 이상인지 확인"""
    min_level = FEATURE_PERMISSIONS.get(feature, 1)
    return role_level >= min_level


def get_accessible_menus(role_level: int) -> list[str]:
    """역할 레벨에 따라 접근 가능한 메뉴 목록을 반환"""
    return [menu for menu, min_level in MENU_PERMISSIONS.items() if role_level >= min_level]


def get_role_level(role_name: str) -> int:
    """역할 이름에서 레벨을 반환"""
    return ROLE_HIERARCHY.get(role_name, 0)
