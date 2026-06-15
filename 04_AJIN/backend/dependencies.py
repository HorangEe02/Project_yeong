"""FastAPI 의존성 주입 (Dependency Injection).

v3.0: 사용자 인증 + 권한 검사 의존성 추가
- get_current_user: JWT → UserContext (필수 인증)
- get_optional_user: JWT → UserContext | None (선택 인증)
- require_permission: 권한 검사 팩토리
"""

import logging
import os
from typing import Optional

from fastapi import Depends, HTTPException, Request

logger = logging.getLogger(__name__)

# 공개 쇼케이스 게스트(읽기 전용)는 D/E/F 열람을 위해 role_level 을 올려두지만,
# 변경 작업(unsafe HTTP method)은 차단해 공개 게스트의 쓰기 권한을 막는다.
# auth._is_guest 와 동일 기준이나 dependencies→auth 순환 import 를 피해 여기서 독립 판정.
_GUEST_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _is_showcase_guest(user) -> bool:
    """현재 사용자가 공개 쇼케이스 게스트(읽기 전용)인지."""
    return (
        getattr(user, "employee_id", "") == "GUEST"
        or str(getattr(user, "role", "")) == "GUEST"
    )


# ═══════════════════════════════════════════════════════════
# 사용자 인증 의존성
# ═══════════════════════════════════════════════════════════

async def get_current_user(request: Request):
    """JWT 토큰에서 현재 사용자를 추출한다 (필수 인증).

    Browser requests use the HttpOnly ``ajin_access`` cookie. Bearer tokens are
    accepted only when ``ALLOW_BEARER_AUTH=true`` for smoke/admin automation.
    """
    from backend.auth_middleware import extract_token_from_header, extract_user_from_token
    from core.auth.cookies import access_token_from_request

    token = access_token_from_request(request)
    auth_source = "cookie" if token else ""

    allow_bearer = os.environ.get("ALLOW_BEARER_AUTH", "").strip().lower() in {"1", "true", "yes", "on"}
    if not token and allow_bearer:
        auth_header = request.headers.get("Authorization", "")
        token = extract_token_from_header(auth_header)
        auth_source = "bearer" if token else ""

    if not token:
        raise HTTPException(
            status_code=401,
            detail="인증이 필요합니다.",
        )

    user = extract_user_from_token(token)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="토큰이 만료되었거나 유효하지 않습니다.",
        )

    request.state.auth_source = auth_source
    return user


async def get_optional_user(request: Request):
    """JWT 토큰이 있으면 UserContext, 없으면 None (선택 인증).

    공개 엔드포인트에서 사용자 추적만 할 때 사용.
    """
    from backend.auth_middleware import extract_token_from_header, extract_user_from_token
    from core.auth.cookies import access_token_from_request

    token = access_token_from_request(request)
    if not token and os.environ.get("ALLOW_BEARER_AUTH", "").strip().lower() in {"1", "true", "yes", "on"}:
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
        # 게스트(쇼케이스 읽기 전용)는 변경 작업 차단 (권한 매트릭스 평가 전 조기 종료).
        if request.method not in _GUEST_SAFE_METHODS and _is_showcase_guest(user):
            raise HTTPException(status_code=403, detail="게스트(읽기 전용)는 변경 작업을 수행할 수 없습니다.")
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


def require_role_level(min_level: int):
    """role_level 기반 권한 검사 의존성 팩토리. P4.1 §8 — RBAC 헬퍼 통합.

    `require_permission` 은 RBAC matrix(permission_key) 기반, 이 헬퍼는 단순 role_level
    임계값 기반. 라우터에서 함수 본문 없이 Depends 로 부착 가능:

        @router.post("/x", dependencies=[Depends(require_role_level(4))])
    """
    def _check(request: Request, user=Depends(get_current_user)):
        lvl = _resolve_role_level(user)
        if lvl < min_level:
            raise HTTPException(
                status_code=403,
                detail=f"L{min_level} 이상 권한 필요 (현재 L{lvl})",
            )
        # 게스트(쇼케이스 읽기 전용)는 레벨을 올려 열람은 허용하되 변경 작업은 차단.
        if request.method not in _GUEST_SAFE_METHODS and _is_showcase_guest(user):
            raise HTTPException(
                status_code=403,
                detail="게스트(읽기 전용)는 변경 작업을 수행할 수 없습니다.",
            )
        return user

    return _check


def resolve_user_role_level(user) -> int:
    """Resolve a user context into the numeric RBAC role level.

    Args:
        user: User context, test double, or router dependency value.

    Returns:
        int: ``role_level`` when present, role-name fallback when possible, or 0.
    """

    return _resolve_role_level(user)


def _resolve_role_level(user) -> int:
    """UserContext의 권한 레벨을 계산한다.

    Args:
        user: ``get_current_user``가 반환한 사용자 컨텍스트.

    Returns:
        ``role_level`` 필드 또는 ``role`` 매핑에서 계산한 RBAC 레벨. 둘 다 없으면 0.
    """
    raw_level = getattr(user, "role_level", None)
    if raw_level is not None:
        try:
            return int(raw_level)
        except (TypeError, ValueError):
            pass

    try:
        from core.auth.rbac import get_role_level
        return int(get_role_level(str(getattr(user, "role", "") or "")))
    except Exception:
        return 0


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
