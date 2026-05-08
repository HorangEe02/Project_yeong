"""FastAPI 의존성 주입 (Dependency Injection).

v3.0: 사용자 인증 + 권한 검사 의존성 추가
- get_current_user: JWT → UserContext (필수 인증)
- get_optional_user: JWT → UserContext | None (선택 인증)
- require_permission: 권한 검사 팩토리
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 사용자 인증 의존성
# ═══════════════════════════════════════════════════════════

async def get_current_user(request: Request):
    """JWT 토큰에서 현재 사용자를 추출한다 (필수 인증).

    Authorization: Bearer <token> 헤더가 없거나 무효하면 401.
    """
    from backend.auth_middleware import extract_token_from_header, extract_user_from_token

    auth_header = request.headers.get("Authorization", "")
    token = extract_token_from_header(auth_header)

    if not token:
        raise HTTPException(
            status_code=401,
            detail="인증이 필요합니다. Authorization 헤더에 Bearer 토큰을 포함하세요.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = extract_user_from_token(token)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="토큰이 만료되었거나 유효하지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_optional_user(request: Request):
    """JWT 토큰이 있으면 UserContext, 없으면 None (선택 인증).

    공개 엔드포인트에서 사용자 추적만 할 때 사용.
    """
    from backend.auth_middleware import extract_token_from_header, extract_user_from_token

    auth_header = request.headers.get("Authorization", "")
    token = extract_token_from_header(auth_header)

    if not token:
        return None

    return extract_user_from_token(token)


def require_permission(permission_key: str):
    """권한 검사 의존성 팩토리.

    사용법:
        @router.post("/check")
        async def check(user=Depends(get_current_user),
                        _=Depends(require_permission("compliance.run_analysis"))):
    """
    async def _check_permission(request: Request, user=Depends(get_current_user)):
        from core.auth.permissions import check_permission

        # 요청 본문에서 target_department 추출 (있으면)
        target_dept = ""
        try:
            if request.method == "POST":
                body = await request.json()
                target_dept = body.get("target_department", "")
        except Exception:
            pass

        allowed = check_permission(user, permission_key, target_department=target_dept)
        if not allowed:
            from backend.auth_middleware import log_api_access
            log_api_access(
                endpoint=str(request.url.path),
                method=request.method,
                status_code=403,
                detail=f"권한 부족: {permission_key}",
                ip_address=request.client.host if request.client else "",
                user=user,
            )
            raise HTTPException(
                status_code=403,
                detail=f"권한이 부족합니다: {permission_key} (현재 역할: {user.role}, 부서: {user.department})",
            )
        return True

    return _check_permission


# ═══════════════════════════════════════════════════════════
# 기존 서비스 의존성 (변경 없음)
# ═══════════════════════════════════════════════════════════

def get_searcher(request: Request):
    """HybridSearcher 싱글톤을 반환한다."""
    return request.app.state.searcher


def get_employee_engine(request: Request):
    """EmployeeSearchEngine 싱글톤을 반환한다."""
    return request.app.state.employee_engine


def get_employee_db(request: Request):
    """EmployeeDatabase 싱글톤을 반환한다."""
    return request.app.state.employee_db


def get_draft_pipeline(request: Request):
    """DraftPipeline 싱글톤을 반환한다."""
    return request.app.state.draft_pipeline


def get_compliance_checker(request: Request):
    """ComplianceChecker를 반환한다."""
    return request.app.state.compliance_checker


def get_scenario_loader(request: Request):
    """ScenarioLoader를 반환한다."""
    return request.app.state.scenario_loader


def get_facility_db(request: Request):
    """FacilityDB를 반환한다."""
    return request.app.state.facility_db
