"""기능 E (인사 관리) 라우터 — React 프론트가 소비하는 모든 /admin/* 엔드포인트.

설계 원칙:
- 비즈니스 로직은 core/auth/* 와 features/admin/* 에 위임
- HR_ADMIN(L4) 이상만 사용자 관리 가능, SYS_ADMIN(L5) 만 시스템 도구 가능
- 응답은 backend/schemas/admin.py 에 정의된 Pydantic 모델로 직렬화
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from backend.auth_middleware import get_audit_logs, log_api_access
from backend.dependencies import get_current_user, require_role_level, resolve_user_role_level
from backend.schemas.admin import (
    AdminUserDetailResponse,
    AdminUserItem,
    AdminUserListResponse,
    AnalyticsUsageResponse,
    AuditLogResponse,
    AuditLogRow,
    CreateEmployeeRequest,
    CreateEmployeeResponse,
    DauResponse,
    DepartmentNode,
    DepartmentTreeResponse,
    DivisionGroup,
    DivisionPositionMatrixResponse,
    EmployeeIDPreviewRequest,
    EmployeeIDPreviewResponse,
    GenderResponse,
    HardDeleteRequest,
    HardDeleteResponse,
    HeadcountResponse,
    HeadcountRow,
    HeatmapResponse,
    HRSummaryResponse,
    LockUserRequest,
    LoginHistoryEntry,
    LoginHistoryResponse,
    LoginStatsResponse,
    OverseasResponse,
    OverseasStaffRow,
    ResetPasswordResponse,
    RetireResponse,
    RoiPerFeature,
    RoiResponse,
    SecurityAlertItem,
    SecurityAlertsResponse,
    SystemHealthResponse,
    TenureResponse,
    TenureRow,
    UpdateUserRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


# ════════════════════════════════════════════════════════════════
# 권한 가드
# ════════════════════════════════════════════════════════════════

def _require_role_level(user, min_level: int) -> None:
    """user.role_level 또는 role fallback 이 min_level 이상이어야 한다."""

    user_level = resolve_user_role_level(user)
    if user_level < min_level:
        raise HTTPException(
            status_code=403,
            detail=f"이 작업은 권한 레벨 L{min_level} 이상이 필요합니다 (현재 L{user_level}).",
        )


def _require_hr_admin(user) -> None:
    _require_role_level(user, 4)


def _require_sys_admin(user) -> None:
    _require_role_level(user, 5)


# ════════════════════════════════════════════════════════════════
# Feature C SOP/Glossary repo-local CMS (SYS_ADMIN L5)
# ════════════════════════════════════════════════════════════════

@router.post("/onboarding-content/validate", dependencies=[Depends(require_role_level(5))])
async def validate_onboarding_content():
    """Validate Feature C SOP/Glossary JSON content.

    Returns:
        dict: Validation summary with fail/warn issues. Published items must
        include citation and review metadata before release.
    """

    from features.onboarding.content_cms import validate_content_store

    result = validate_content_store()
    status = 200 if result["ok"] else 409
    return JSONResponse(status_code=status, content=result)


@router.get("/onboarding-content/{kind}", dependencies=[Depends(require_role_level(5))])
async def list_onboarding_content(kind: str, include_unpublished: bool = True):
    """List Feature C content files for admin CMS screens.

    Args:
        kind: Content kind, one of ``sops``, ``glossary``, or ``glossary_aliases``.
        include_unpublished: Include draft and archived files.

    Returns:
        dict: Content file summaries.
    """

    from features.onboarding.content_cms import list_content

    try:
        items = list_content(kind, include_unpublished=include_unpublished)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"kind": kind, "items": items, "total": len(items)}


@router.get("/onboarding-content/{kind}/{object_id}", dependencies=[Depends(require_role_level(5))])
async def get_onboarding_content(kind: str, object_id: str):
    """Read one Feature C content object.

    Args:
        kind: Content kind.
        object_id: File id without the optional ``.json`` suffix.

    Returns:
        dict: Content payload and repository path.
    """

    from features.onboarding.content_cms import get_content

    try:
        return get_content(kind, object_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="content_not_found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/onboarding-content/{kind}/{object_id}", dependencies=[Depends(require_role_level(5))])
async def put_onboarding_content(kind: str, object_id: str, payload: dict):
    """Create or update one Feature C content object.

    Args:
        kind: Content kind.
        object_id: File id without the optional ``.json`` suffix.
        payload: JSON object to persist.

    Returns:
        dict: Saved object metadata.
    """

    from features.onboarding.content_cms import upsert_content

    try:
        return upsert_content(kind, object_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/onboarding-content/{kind}/{object_id}/archive", dependencies=[Depends(require_role_level(5))])
async def archive_onboarding_content(kind: str, object_id: str):
    """Archive one Feature C content object without deleting it.

    Args:
        kind: Content kind.
        object_id: File id without the optional ``.json`` suffix.

    Returns:
        dict: Archived object metadata.
    """

    from features.onboarding.content_cms import archive_content

    try:
        return archive_content(kind, object_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="content_not_found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ════════════════════════════════════════════════════════════════
# 부서/직급/역할 트리
# ════════════════════════════════════════════════════════════════

@router.get("/departments", response_model=DepartmentTreeResponse)
async def list_departments(user=Depends(get_current_user)):
    """본부 → 부서 트리 + 직급/역할 목록을 반환한다.

    L1(EMPLOYEE) 이상이면 누구나 조회 가능 (드롭다운 옵션용).
    """
    from core.auth.department_config import (
        DEPARTMENT_CATEGORIES,
        POSITION_LIST,
        ROLE_LIST,
    )

    divisions = [
        DivisionGroup(
            division=div,
            departments=[
                DepartmentNode(name=name, prefix=meta[0], description=meta[1])
                for name, meta in depts.items()
            ],
        )
        for div, depts in DEPARTMENT_CATEGORIES.items()
    ]
    return DepartmentTreeResponse(
        divisions=divisions,
        positions=list(POSITION_LIST),
        roles=list(ROLE_LIST),
    )


# ════════════════════════════════════════════════════════════════
# 사용자 목록 / 상세 / 수정 / 잠금
# ════════════════════════════════════════════════════════════════

def _row_to_user_item(row: sqlite3.Row, division: str = "") -> AdminUserItem:
    # resign_date 컬럼은 v2.7 마이그레이션 이후 존재. 누락 가능성 대비 방어 처리.
    try:
        resign_date = row["resign_date"] or ""
    except (KeyError, IndexError):
        resign_date = ""
    return AdminUserItem(
        employee_id=row["employee_id"],
        username=row["username"],
        department=row["department"] or "",
        division=division,
        position=row["position"] or "",
        role_name=row["role_name"],
        role_level=row["role_level"],
        email=row["email"] or "",
        phone=row["phone"] or "",
        is_active=bool(row["is_active"]),
        must_change_pw=bool(row["must_change_pw"]),
        last_login=row["last_login"],
        locked_until=row["locked_until"],
        failed_attempts=int(row["failed_attempts"] or 0),
        hire_date=row["hire_date"] or "",
        resign_date=resign_date,
    )


@router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    division: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    position: Optional[str] = Query(None),
    role_name: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="active|inactive|locked|all"),
    q: Optional[str] = Query(None, description="이름/사번/이메일 부분 일치"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user=Depends(get_current_user),
):
    """사용자 목록 조회 (HR_ADMIN+).

    본부(division) 필터는 DEPARTMENT_TO_DIVISION 매핑을 이용해 부서 IN 절로 변환한다.
    """
    _require_hr_admin(user)

    from core.auth.database import get_auth_db
    from core.auth.user_context import DEPARTMENT_TO_DIVISION

    conn = get_auth_db()

    base = """
        SELECT u.employee_id, u.username, u.department, u.position,
               u.email, u.phone, u.is_active, u.must_change_pw, u.failed_attempts,
               u.locked_until, u.last_login, u.hire_date, u.resign_date,
               r.role_name, r.role_level
          FROM users u
          JOIN roles r ON u.role_id = r.role_id
    """

    conditions: list[str] = []
    params: list = []

    if division:
        depts_in_div = [d for d, dv in DEPARTMENT_TO_DIVISION.items() if dv == division]
        if depts_in_div:
            placeholders = ",".join("?" * len(depts_in_div))
            conditions.append(f"u.department IN ({placeholders})")
            params.extend(depts_in_div)
        else:
            conditions.append("1=0")

    if department:
        conditions.append("u.department = ?")
        params.append(department)
    if position:
        conditions.append("u.position = ?")
        params.append(position)
    if role_name:
        conditions.append("r.role_name = ?")
        params.append(role_name)
    if status == "active":
        conditions.append("u.is_active = 1")
    elif status == "inactive":
        conditions.append("u.is_active = 0")
    elif status == "locked":
        conditions.append("u.locked_until IS NOT NULL AND u.locked_until > datetime('now')")
    elif status == "retired":
        conditions.append("u.is_active = 0 AND IFNULL(u.resign_date, '') != ''")
    if q:
        conditions.append("(u.employee_id LIKE ? OR u.username LIKE ? OR u.email LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like, like])

    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    filtered = conn.execute(f"SELECT COUNT(*) FROM users u JOIN roles r ON u.role_id=r.role_id{where}", params).fetchone()[0]

    rows = conn.execute(
        f"{base}{where} ORDER BY u.employee_id LIMIT ? OFFSET ?",
        [*params, limit, offset],
    ).fetchall()
    conn.close()

    items = [_row_to_user_item(r, DEPARTMENT_TO_DIVISION.get(r["department"] or "", "")) for r in rows]
    log_api_access(endpoint="/api/admin/users", method="GET", user=user, detail=f"filtered={filtered}")
    return AdminUserListResponse(total=total, filtered=filtered, users=items)


@router.get("/users/{employee_id}", response_model=AdminUserDetailResponse)
async def get_user_detail(employee_id: str, user=Depends(get_current_user)):
    _require_hr_admin(user)

    from core.auth.database import get_auth_db
    from core.auth.user_context import DEPARTMENT_TO_DIVISION

    conn = get_auth_db()
    row = conn.execute(
        """SELECT u.*, r.role_name, r.role_level
             FROM users u JOIN roles r ON u.role_id=r.role_id
            WHERE u.employee_id = ?""",
        (employee_id,),
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, f"사용자 {employee_id} 을(를) 찾을 수 없습니다.")

    item = _row_to_user_item(row, DEPARTMENT_TO_DIVISION.get(row["department"] or "", ""))

    history_rows = conn.execute(
        """SELECT timestamp, employee_id, action, success, ip_address
             FROM login_history WHERE employee_id = ?
            ORDER BY timestamp DESC LIMIT 20""",
        (employee_id,),
    ).fetchall()
    conn.close()

    recent = [
        LoginHistoryEntry(
            timestamp=r["timestamp"] or "",
            employee_id=r["employee_id"],
            username=item.username,
            action=r["action"] or "login",
            success=bool(r["success"]),
            ip_address=r["ip_address"] or "",
        )
        for r in history_rows
    ]
    return AdminUserDetailResponse(user=item, recent_logins=recent)


@router.put("/users/{employee_id}")
async def update_user(employee_id: str, req: UpdateUserRequest, user=Depends(get_current_user)):
    _require_hr_admin(user)

    if employee_id == getattr(user, "employee_id", ""):
        raise HTTPException(400, "자기 자신의 권한/상태는 변경할 수 없습니다.")

    from core.auth.database import get_auth_db
    conn = get_auth_db()
    target = conn.execute(
        """SELECT u.*, r.role_name, r.role_level
             FROM users u JOIN roles r ON u.role_id=r.role_id
            WHERE u.employee_id = ?""",
        (employee_id,),
    ).fetchone()
    if not target:
        conn.close()
        raise HTTPException(404, "사용자를 찾을 수 없습니다.")

    actor_level = resolve_user_role_level(user)
    target_level = target["role_level"]
    if target_level >= actor_level and actor_level < 5:
        conn.close()
        raise HTTPException(403, "본인보다 같거나 높은 권한 레벨의 계정은 수정할 수 없습니다.")

    sets: list[str] = []
    params: list = []

    if req.username is not None:
        sets.append("username = ?")
        params.append(req.username)
    if req.department is not None:
        sets.append("department = ?")
        params.append(req.department)
    if req.position is not None:
        sets.append("position = ?")
        params.append(req.position)
    if req.email is not None:
        sets.append("email = ?")
        params.append(req.email)
    if req.phone is not None:
        sets.append("phone = ?")
        params.append(req.phone)
    if req.is_active is not None:
        sets.append("is_active = ?")
        params.append(1 if req.is_active else 0)

    if req.role_name is not None:
        new_role = conn.execute(
            "SELECT role_id, role_level FROM roles WHERE role_name = ?",
            (req.role_name,),
        ).fetchone()
        if not new_role:
            conn.close()
            raise HTTPException(400, f"존재하지 않는 역할입니다: {req.role_name}")
        if new_role["role_level"] > actor_level and actor_level < 5:
            conn.close()
            raise HTTPException(403, "본인보다 높은 권한 레벨은 부여할 수 없습니다.")
        sets.append("role_id = ?")
        params.append(new_role["role_id"])

    if not sets:
        conn.close()
        return {"updated": 0}

    sets.append("updated_at = datetime('now')")
    params.append(employee_id)
    conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE employee_id = ?", params)
    conn.commit()
    conn.close()

    log_api_access(endpoint=f"/api/admin/users/{employee_id}", method="PUT", user=user, detail=",".join(sets))
    return {"updated": 1, "employee_id": employee_id}


@router.post("/users/{employee_id}/reset-password", response_model=ResetPasswordResponse)
async def reset_password(employee_id: str, user=Depends(get_current_user)):
    _require_hr_admin(user)

    from core.auth.database import get_auth_db
    from core.auth.password import generate_initial_password, hash_password
    from core.auth.policy import plaintext_initial_password_allowed

    conn = get_auth_db()
    target = conn.execute(
        "SELECT user_id, password_hash FROM users WHERE employee_id = ?",
        (employee_id,),
    ).fetchone()
    if not target:
        conn.close()
        raise HTTPException(404, "사용자를 찾을 수 없습니다.")

    new_pw = generate_initial_password(employee_id)
    new_hash = hash_password(new_pw)
    conn.execute(
        """UPDATE users SET password_hash = ?, must_change_pw = 1,
                            failed_attempts = 0, locked_until = NULL,
                            updated_at = datetime('now')
            WHERE employee_id = ?""",
        (new_hash, employee_id),
    )
    conn.execute(
        "INSERT INTO password_history (user_id, password_hash) VALUES (?, ?)",
        (target["user_id"], target["password_hash"]),
    )
    conn.commit()
    conn.close()
    if plaintext_initial_password_allowed():
        return ResetPasswordResponse(
            employee_id=employee_id,
            initial_password=new_pw,
            credential_delivery="local_plaintext",
            issuance_note="임시 비밀번호는 한 번만 표시됩니다. 안전한 채널로 전달하세요.",
        )
    return ResetPasswordResponse(
        employee_id=employee_id,
        initial_password="",
        credential_delivery="idp_invite_required",
        issuance_note="운영 환경에서는 임시 비밀번호를 응답하지 않습니다. 사내 IdP 초대/초기화 절차로 전달하세요.",
    )


@router.post("/users/{employee_id}/lock")
async def lock_user(employee_id: str, req: LockUserRequest, user=Depends(get_current_user)):
    _require_hr_admin(user)
    if employee_id == getattr(user, "employee_id", ""):
        raise HTTPException(400, "자기 자신을 잠글 수 없습니다.")

    from core.auth.database import get_auth_db

    lock_until = (datetime.now(timezone.utc) + timedelta(minutes=req.minutes)).isoformat()
    conn = get_auth_db()
    cur = conn.execute(
        "UPDATE users SET locked_until = ?, failed_attempts = 5 WHERE employee_id = ?",
        (lock_until, employee_id),
    )
    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(404, "사용자를 찾을 수 없습니다.")
    conn.commit()
    conn.close()
    return {"locked": True, "locked_until": lock_until}


@router.post("/users/{employee_id}/unlock")
async def unlock_user(employee_id: str, user=Depends(get_current_user)):
    _require_hr_admin(user)
    from core.auth.database import get_auth_db

    conn = get_auth_db()
    conn.execute(
        "UPDATE users SET locked_until = NULL, failed_attempts = 0 WHERE employee_id = ?",
        (employee_id,),
    )
    conn.commit()
    conn.close()
    return {"unlocked": True}


# ════════════════════════════════════════════════════════════════
# 삭제 (Soft retire / Hard delete)
# ════════════════════════════════════════════════════════════════

def _count_active_sys_admins(conn, exclude_user_id: int | None = None) -> int:
    """현재 활성 SYS_ADMIN 수. exclude_user_id 가 있으면 그 사용자 제외하고 셈."""
    if exclude_user_id is None:
        return conn.execute(
            """SELECT COUNT(*) FROM users u JOIN roles r ON u.role_id=r.role_id
                WHERE r.role_name='SYS_ADMIN' AND u.is_active=1"""
        ).fetchone()[0]
    return conn.execute(
        """SELECT COUNT(*) FROM users u JOIN roles r ON u.role_id=r.role_id
            WHERE r.role_name='SYS_ADMIN' AND u.is_active=1 AND u.user_id != ?""",
        (exclude_user_id,),
    ).fetchone()[0]


@router.delete("/users/{employee_id}/retire", response_model=RetireResponse)
async def retire_user(employee_id: str, user=Depends(get_current_user)):
    """Soft delete — 퇴직 처리. 가역적이며 모든 history 보존.

    동작:
    - is_active = 0
    - role = INACTIVE (이전 role 은 audit log 에 기록)
    - resign_date = 오늘
    - locked_until = 50년 후 (사실상 영구)
    - failed_attempts = 0 (재로그인 시도 카운터 리셋)
    """
    _require_hr_admin(user)
    if employee_id == getattr(user, "employee_id", ""):
        raise HTTPException(400, "자기 자신은 퇴직 처리할 수 없습니다.")

    from core.auth.database import get_auth_db
    conn = get_auth_db()
    target = conn.execute(
        """SELECT u.user_id, u.username, u.is_active, r.role_name, r.role_level
             FROM users u JOIN roles r ON u.role_id=r.role_id
            WHERE u.employee_id = ?""",
        (employee_id,),
    ).fetchone()
    if not target:
        conn.close()
        raise HTTPException(404, "사용자를 찾을 수 없습니다.")

    actor_level = resolve_user_role_level(user)
    if target["role_level"] >= actor_level and actor_level < 5:
        conn.close()
        raise HTTPException(403, "본인보다 같거나 높은 권한 레벨의 계정은 삭제할 수 없습니다.")

    if target["role_name"] == "SYS_ADMIN":
        remaining = _count_active_sys_admins(conn, exclude_user_id=target["user_id"])
        if remaining < 1:
            conn.close()
            raise HTTPException(409, "마지막 시스템 관리자입니다. 다른 SYS_ADMIN 을 먼저 만든 뒤 처리하세요.")

    inactive_role = conn.execute(
        "SELECT role_id FROM roles WHERE role_name = 'INACTIVE'"
    ).fetchone()
    if not inactive_role:
        conn.close()
        raise HTTPException(500, "INACTIVE 역할이 DB 에 등록되지 않았습니다. init_auth_db() 재실행 필요.")
    inactive_role_id = inactive_role["role_id"]

    today_iso = date.today().isoformat()
    permanent_lock = (datetime.now(timezone.utc) + timedelta(days=365 * 50)).isoformat()

    conn.execute(
        """UPDATE users
              SET is_active = 0,
                  role_id = ?,
                  resign_date = ?,
                  locked_until = ?,
                  failed_attempts = 0,
                  updated_at = datetime('now')
            WHERE employee_id = ?""",
        (inactive_role_id, today_iso, permanent_lock, employee_id),
    )
    conn.commit()
    conn.close()

    log_api_access(
        endpoint=f"/api/admin/users/{employee_id}/retire",
        method="DELETE",
        user=user,
        detail=f"soft_delete prev_role={target['role_name']} username={target['username']}",
    )
    return RetireResponse(retired=True, employee_id=employee_id, resign_date=today_iso)


@router.delete("/users/{employee_id}", response_model=HardDeleteResponse)
async def delete_user(
    employee_id: str,
    req: HardDeleteRequest,
    user=Depends(get_current_user),
):
    """Hard delete — SYS_ADMIN 전용 영구 삭제. 비가역.

    cascade 순서: password_history → login_history → users (트랜잭션).
    type-to-confirm: req.confirm_employee_id 가 path 파라미터와 일치해야 진행.
    """
    _require_sys_admin(user)
    if employee_id == getattr(user, "employee_id", ""):
        raise HTTPException(400, "자기 자신은 삭제할 수 없습니다.")
    if req.confirm_employee_id != employee_id:
        raise HTTPException(400, "확인용 사번이 일치하지 않습니다.")
    if not (req.reason or "").strip():
        raise HTTPException(400, "hard_delete_reason_required")

    from core.auth.policy import hard_delete_allowed

    if not hard_delete_allowed():
        log_api_access(
            endpoint=f"/api/admin/users/{employee_id}",
            method="DELETE",
            status_code=403,
            user=user,
            detail="hard_delete_disabled",
        )
        raise HTTPException(status_code=403, detail="hard_delete_disabled")

    from core.auth.database import get_auth_db

    conn = get_auth_db()
    target = conn.execute(
        """SELECT u.user_id, u.username, r.role_name, r.role_level
             FROM users u JOIN roles r ON u.role_id=r.role_id
            WHERE u.employee_id = ?""",
        (employee_id,),
    ).fetchone()
    if not target:
        conn.close()
        raise HTTPException(404, "사용자를 찾을 수 없습니다.")

    if target["role_name"] == "SYS_ADMIN":
        remaining = _count_active_sys_admins(conn, exclude_user_id=target["user_id"])
        if remaining < 1:
            conn.close()
            raise HTTPException(409, "마지막 시스템 관리자는 영구 삭제할 수 없습니다.")

    user_id = target["user_id"]
    history_count = conn.execute(
        "SELECT COUNT(*) FROM login_history WHERE user_id=?",
        (user_id,),
    ).fetchone()[0]
    pw_history_count = conn.execute(
        "SELECT COUNT(*) FROM password_history WHERE user_id=?",
        (user_id,),
    ).fetchone()[0]

    try:
        conn.execute("BEGIN")
        conn.execute("DELETE FROM password_history WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM login_history WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM users WHERE user_id=?", (user_id,))
        conn.commit()
    except Exception as e:  # noqa: BLE001
        conn.rollback()
        conn.close()
        logger.error("hard_delete transaction failed: %s", e)
        raise HTTPException(500, "삭제 트랜잭션 실패. 변경 사항이 롤백되었습니다.")
    conn.close()

    log_api_access(
        endpoint=f"/api/admin/users/{employee_id}",
        method="DELETE",
        user=user,
        detail=(
            f"hard_delete name={target['username']} role={target['role_name']} "
            f"login_history={history_count} pw_history={pw_history_count} "
            f"reason={(req.reason or '')[:80]}"
        ),
    )
    return HardDeleteResponse(
        deleted=True,
        employee_id=employee_id,
        cascaded={"login_history": history_count, "password_history": pw_history_count},
    )


# ════════════════════════════════════════════════════════════════
# 사번 미리보기 + 계정 생성
# ════════════════════════════════════════════════════════════════

def _next_sequence_for_prefix(prefix: str) -> int:
    """auth.db users 테이블에서 해당 prefix 의 가장 큰 시퀀스 + 1.

    fallback: prefix 가 어느 employee_id 와도 매치되지 않으면 1 부터.
    형식 가정: ``{PREFIX}-{NNNN}``.
    """
    from core.auth.database import get_auth_db

    conn = get_auth_db()
    rows = conn.execute(
        "SELECT employee_id FROM users WHERE employee_id LIKE ?",
        (f"{prefix}-%",),
    ).fetchall()
    conn.close()

    max_n = 0
    for r in rows:
        try:
            tail = r["employee_id"].split("-", 1)[1]
            n = int(tail)
            max_n = max(max_n, n)
        except (IndexError, ValueError):
            continue
    return max_n + 1


@router.post("/employee-id/preview", response_model=EmployeeIDPreviewResponse)
async def preview_employee_id(req: EmployeeIDPreviewRequest, user=Depends(get_current_user)):
    _require_hr_admin(user)

    from core.auth.department_config import (
        DEPARTMENT_CATEGORIES,
        generate_employee_id,
        get_dept_prefix,
    )

    valid = any(req.department in depts for depts in DEPARTMENT_CATEGORIES.values())
    if not valid:
        raise HTTPException(400, f"유효하지 않은 부서: {req.department}")

    prefix = get_dept_prefix(req.department)
    seq = _next_sequence_for_prefix(prefix)
    next_id = generate_employee_id(req.department, seq)
    suggested_email = f"{next_id.lower().replace('-', '')}@ajinindustry.com"
    return EmployeeIDPreviewResponse(
        department=req.department,
        prefix=prefix,
        next_id=next_id,
        sequence=seq,
        suggested_email=suggested_email,
        suggested_initial_password="생성 시 1회 발급",
    )


@router.post("/users", response_model=CreateEmployeeResponse, status_code=201)
async def create_employee(
    req: CreateEmployeeRequest,
    request: Request,
    user=Depends(get_current_user),
):
    _require_hr_admin(user)

    from core.auth.database import get_auth_db
    from core.auth.department_config import (
        DEPARTMENT_CATEGORIES,
        generate_employee_id,
        get_dept_prefix,
    )
    from core.auth.password import generate_initial_password, hash_password
    from core.auth.policy import plaintext_initial_password_allowed
    from core.data_lineage import lineage_values

    valid_dept = any(req.department in depts for depts in DEPARTMENT_CATEGORIES.values())
    if not valid_dept:
        raise HTTPException(400, f"유효하지 않은 부서: {req.department}")

    actor_level = resolve_user_role_level(user)

    conn = get_auth_db()
    role_row = conn.execute(
        "SELECT role_id, role_level FROM roles WHERE role_name = ?",
        (req.role_name,),
    ).fetchone()
    if not role_row:
        conn.close()
        raise HTTPException(400, f"존재하지 않는 역할: {req.role_name}")
    if role_row["role_level"] > actor_level and actor_level < 5:
        conn.close()
        raise HTTPException(403, "본인보다 높은 권한 레벨은 부여할 수 없습니다.")

    prefix = get_dept_prefix(req.department)

    for _ in range(5):
        seq = _next_sequence_for_prefix(prefix)
        emp_id = generate_employee_id(req.department, seq)
        exists = conn.execute("SELECT 1 FROM users WHERE employee_id = ?", (emp_id,)).fetchone()
        if not exists:
            break
    else:
        conn.close()
        raise HTTPException(500, "사번 생성 충돌. 잠시 후 다시 시도하세요.")

    initial_pw = generate_initial_password(emp_id)
    pw_hash = hash_password(initial_pw)

    email = req.email or f"{emp_id.lower().replace('-', '')}@ajinindustry.com"
    source_label = f"admin_ui:{getattr(user, 'employee_id', '') or 'unknown'}"
    auth_lineage = lineage_values("real", "admin_ui", source_label)

    conn.execute(
        """INSERT INTO users
             (employee_id, username, password_hash, role_id, is_active, must_change_pw,
              email, phone, department, position, hire_date,
              data_class, source_system, source_label, source_updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            emp_id, req.username, pw_hash, role_row["role_id"],
            1 if req.is_active else 0,
            1 if req.must_change_pw else 0,
            email, req.phone, req.department, req.position, req.hire_date,
            auth_lineage["data_class"],
            auth_lineage["source_system"],
            auth_lineage["source_label"],
            auth_lineage["source_updated_at"],
        ),
    )
    conn.commit()
    conn.close()

    # ─────────────────────────────────────────────────────────────
    # Plan v3.7 — Module E ↔ A 동기화 + Cloud Run 영속화 (3-way sync)
    # 1. Firestore auth_users upsert  → 인스턴스 재시작 후에도 유지
    # 2. employees.db UPSERT          → Module A (인원 검색) 즉시 노출
    # 3. Firestore employees upsert   → 재시작 후 employees.db 복원
    # 모든 단계 silent skip 가능 — auth.db INSERT 는 이미 commit 됨.
    # ─────────────────────────────────────────────────────────────
    try:
        from core.auth.database import persist_user_to_firestore

        _now_iso = datetime.utcnow().isoformat()
        persist_user_to_firestore({
            "employee_id": emp_id,
            "username": req.username,
            "password_hash": pw_hash,
            "role_id": role_row["role_id"],
            "role_name": req.role_name,
            "is_active": req.is_active,
            "must_change_pw": req.must_change_pw,
            "email": email,
            "phone": req.phone or "",
            "department": req.department,
            "position": req.position,
            "hire_date": req.hire_date or "",
            "created_at": _now_iso,
            "updated_at": _now_iso,
            **auth_lineage,
        })
    except Exception as e:  # pragma: no cover — silent skip
        logging.warning(f"[admin.create_employee] Firestore auth_users sync 실패: {e}")

    try:
        from features.search.employee.database import (
            POSITION_HIERARCHY,
            persist_employee_to_firestore,
        )

        _emp_dict = {
            "employee_id": emp_id,
            "name": req.username,
            "position": req.position,
            "position_level": POSITION_HIERARCHY.get(req.position, 1),
            "division": req.division,
            "department": req.department,
            "department_id": "",
            "email": email,
            "phone": req.phone or "",
            "extension": "",
            "plant": "경산 본사",
            "plant_id": "PLANT-KS-HQ",
            "hire_date": req.hire_date or "",
            "is_active": 1 if req.is_active else 0,
            "is_team_leader": 0,
            "photo_url": "",
            "is_synthetic": 0,
            "canonical_employee_id": emp_id,
            **auth_lineage,
        }

        # employees.db UPSERT — Module A 검색 즉시 노출
        emp_db = getattr(request.app.state, "employee_db", None)
        if emp_db is not None:
            emp_db.add_employee(_emp_dict)
        else:
            logging.warning("[admin.create_employee] app.state.employee_db 미초기화 — 검색 노출 보류")

        # Firestore employees upsert — Cloud Run 재시작 후 복원
        persist_employee_to_firestore(_emp_dict)
    except Exception as e:  # pragma: no cover — silent skip
        logging.warning(f"[admin.create_employee] employees 동기화 실패: {e}")

    can_return_plaintext = plaintext_initial_password_allowed()
    credential_delivery = "local_plaintext" if can_return_plaintext else "idp_invite_required"
    initial_password_response = initial_pw if can_return_plaintext else ""
    if can_return_plaintext:
        initial_login_note = (
            f"- 초기 비밀번호: **{initial_pw}** (최초 로그인 시 즉시 변경 필요)\n"
            f"- 비밀번호 정책: 12자 이상, UTF-8 72바이트 이하, 흔한/문맥 유사 비밀번호 금지\n"
        )
        issuance_note = "발급된 초기 비밀번호는 한 번만 표시됩니다. 안전한 채널로 사용자에게 전달하세요."
    else:
        initial_login_note = (
            "- 운영 환경에서는 임시 비밀번호를 응답하지 않습니다.\n"
            "- 사내 IdP 초대/초기화 절차에서 사용자에게 최초 로그인 수단을 전달하세요.\n"
        )
        issuance_note = "운영 환경에서는 임시 비밀번호를 응답하지 않습니다. 사내 IdP 초대/초기화 절차를 사용하세요."

    instructions = (
        f"# AJIN AI Assistant 계정 발급 안내\n\n"
        f"- 사번: **{emp_id}**\n"
        f"- 이름: {req.username}\n"
        f"- 본부 / 부서: {req.division} / {req.department}\n"
        f"- 직급: {req.position}\n"
        f"- 역할: {req.role_name} (L{role_row['role_level']})\n"
        f"- 이메일: {email}\n\n"
        f"## 초기 로그인\n\n"
        f"{initial_login_note}"
        f"- 5회 연속 실패 시 30분 잠금\n"
    )

    log_api_access(
        endpoint="/api/admin/users",
        method="POST",
        user=user,
        detail=f"created={emp_id}, role={req.role_name}",
    )

    return CreateEmployeeResponse(
        employee_id=emp_id,
        username=req.username,
        department=req.department,
        role_name=req.role_name,
        role_level=role_row["role_level"],
        initial_password=initial_password_response,
        must_change_pw=req.must_change_pw,
        issuance_note=issuance_note,
        credential_delivery=credential_delivery,
        instructions_markdown=instructions,
    )


# ════════════════════════════════════════════════════════════════
# 보안 감사
# ════════════════════════════════════════════════════════════════

@router.get("/security/alerts", response_model=SecurityAlertsResponse)
async def security_alerts(hours: int = Query(24, ge=1, le=720), user=Depends(get_current_user)):
    _require_hr_admin(user)

    from features.admin.security_monitor import detect_anomalies

    alerts = detect_anomalies(hours=hours)
    summary = {"brute_force": 0, "unusual_hour": 0, "inactive_access": 0}
    items: list[SecurityAlertItem] = []
    for a in alerts:
        summary[a.alert_type] = summary.get(a.alert_type, 0) + 1
        items.append(
            SecurityAlertItem(
                alert_type=a.alert_type,
                severity=a.severity,
                title=a.title,
                description=a.description,
                employee_id=a.employee_id,
                timestamp=a.timestamp,
                details=a.details,
            )
        )
    return SecurityAlertsResponse(period_hours=hours, alerts=items, summary=summary)


@router.get("/security/login-stats", response_model=LoginStatsResponse)
async def login_stats(days: int = Query(30, ge=1, le=365), user=Depends(get_current_user)):
    _require_hr_admin(user)

    from features.admin.security_monitor import (
        get_failed_login_trend,
        get_login_daily_counts,
        get_login_hour_distribution,
        get_login_stats,
    )

    stats = get_login_stats(days=days)
    return LoginStatsResponse(
        days=days,
        total_logins=stats["total_logins"],
        successful=stats["successful"],
        failed=stats["failed"],
        success_rate=stats["success_rate"],
        unique_users=stats["unique_users"],
        locked_accounts=stats["locked_accounts"],
        hour_distribution=get_login_hour_distribution(days=days),
        failed_trend=get_failed_login_trend(days=days),
        daily_counts=get_login_daily_counts(days=days),  # v4.9 — 달력 히트맵
    )


@router.get("/security/login-history", response_model=LoginHistoryResponse)
async def login_history(limit: int = Query(50, ge=1, le=500), user=Depends(get_current_user)):
    _require_hr_admin(user)

    from features.admin.security_monitor import get_recent_logins

    rows = get_recent_logins(limit=limit)
    history = []
    for r in rows:
        ts = r.get("timestamp", "") or ""
        flag = None
        try:
            hour = int(ts[11:13]) if len(ts) >= 13 else -1
            if hour >= 22 or 0 <= hour < 6:
                flag = "OFF-HOURS"
        except ValueError:
            pass
        if not r.get("success"):
            flag = "BRUTE" if flag is None else flag
        history.append(
            LoginHistoryEntry(
                timestamp=ts,
                employee_id=r.get("employee_id", "") or "",
                username=r.get("username") or "",
                action=r.get("action", "login"),
                success=bool(r.get("success")),
                ip_address=r.get("ip_address", "") or "",
                flag=flag,
            )
        )
    return LoginHistoryResponse(total=len(history), history=history)


# ════════════════════════════════════════════════════════════════
# AI 활용 분석
# ════════════════════════════════════════════════════════════════

@router.get("/analytics/usage", response_model=AnalyticsUsageResponse)
async def analytics_usage(days: int = Query(30, ge=1, le=365), user=Depends(get_current_user)):
    _require_hr_admin(user)

    from features.admin.usage_analytics import (
        get_usage_by_department,
        get_usage_by_feature,
        get_usage_by_hour,
    )

    return AnalyticsUsageResponse(
        days=days,
        by_feature=[
            {"feature": r["feature"], "name": r["name"], "count": r["count"], "color": r.get("color", "")}
            for r in get_usage_by_feature(days=days)
        ],
        by_department=[
            {"department": r["department"], "count": r["count"]}
            for r in get_usage_by_department(days=days)
        ],
        by_hour=[
            {"hour": r["hour"], "count": r["count"]}
            for r in get_usage_by_hour(days=days)
        ],
    )


@router.get("/analytics/heatmap", response_model=HeatmapResponse)
async def analytics_heatmap(days: int = Query(30, ge=1, le=365), user=Depends(get_current_user)):
    _require_hr_admin(user)
    from features.admin.usage_analytics import get_dept_feature_heatmap

    data = get_dept_feature_heatmap(days=days)
    return HeatmapResponse(
        days=days,
        departments=data["departments"],
        features=data["features"],
        matrix=data["matrix"],
    )


@router.get("/analytics/dau", response_model=DauResponse)
async def analytics_dau(days: int = Query(30, ge=1, le=365), user=Depends(get_current_user)):
    _require_hr_admin(user)
    from features.admin.usage_analytics import get_daily_active_users

    return DauResponse(days=days, series=get_daily_active_users(days=days))


@router.get("/analytics/roi", response_model=RoiResponse)
async def analytics_roi(days: int = Query(30, ge=1, le=365), user=Depends(get_current_user)):
    _require_hr_admin(user)
    from features.admin.usage_analytics import calculate_roi_estimate

    data = calculate_roi_estimate(days=days)
    return RoiResponse(
        period_days=data["period_days"],
        total_uses=data["total_uses"],
        total_saved_minutes=data["total_saved_minutes"],
        total_saved_hours=data["total_saved_hours"],
        saved_cost_krw=data["saved_cost_krw"],
        saved_cost_display=data["saved_cost_display"],
        per_feature={
            k: RoiPerFeature(name=v["name"], count=v["count"], saved_min=v["saved_min"])
            for k, v in data["per_feature"].items()
        },
    )


# ════════════════════════════════════════════════════════════════
# 인사 통계
# ════════════════════════════════════════════════════════════════

def _hr_min_level(user) -> None:
    """팀장(L3) 이상이면 통계 조회 허용."""
    _require_role_level(user, 3)


@router.get("/hr/summary", response_model=HRSummaryResponse)
async def hr_summary(user=Depends(get_current_user)):
    _hr_min_level(user)
    from features.search.employee.analytics import get_summary_stats

    s = get_summary_stats()
    return HRSummaryResponse(**s)


@router.get("/hr/headcount", response_model=HeadcountResponse)
async def hr_headcount(by: str = Query("division"), user=Depends(get_current_user)):
    _hr_min_level(user)
    from features.search.employee.analytics import (
        get_headcount_by_department,
        get_headcount_by_division,
        get_headcount_by_plant,
        get_headcount_by_position,
    )

    if by == "division":
        rows = [HeadcountRow(label=r["division"], count=r["count"], dept_count=r.get("dept_count")) for r in get_headcount_by_division()]
    elif by == "department":
        rows = [HeadcountRow(label=r["department"], count=r["count"], division=r.get("division")) for r in get_headcount_by_department()]
    elif by == "position":
        rows = [HeadcountRow(label=r["position"], count=r["count"]) for r in get_headcount_by_position()]
    elif by == "plant":
        rows = [HeadcountRow(label=r["plant"], count=r["count"]) for r in get_headcount_by_plant()]
    else:
        raise HTTPException(400, "by must be one of: division/department/position/plant")
    return HeadcountResponse(by=by, rows=rows)


@router.get("/hr/gender", response_model=GenderResponse)
async def hr_gender(user=Depends(get_current_user)):
    _hr_min_level(user)
    from features.search.employee.analytics import get_gender_distribution

    return GenderResponse(distribution=get_gender_distribution())


@router.get("/hr/tenure", response_model=TenureResponse)
async def hr_tenure(user=Depends(get_current_user)):
    _hr_min_level(user)
    from features.search.employee.analytics import get_tenure_distribution

    rows = get_tenure_distribution()
    return TenureResponse(rows=[TenureRow(**r) for r in rows])


@router.get("/hr/matrix", response_model=DivisionPositionMatrixResponse)
async def hr_matrix(user=Depends(get_current_user)):
    _hr_min_level(user)
    from features.search.employee.analytics import get_division_position_matrix

    data = get_division_position_matrix()
    return DivisionPositionMatrixResponse(**data)


@router.get("/hr/overseas", response_model=OverseasResponse)
async def hr_overseas(user=Depends(get_current_user)):
    _hr_min_level(user)
    from features.search.employee.analytics import get_overseas_staff

    rows = get_overseas_staff()
    return OverseasResponse(rows=[OverseasStaffRow(**r) for r in rows])


# ════════════════════════════════════════════════════════════════
# 시스템 도구
# ════════════════════════════════════════════════════════════════

@router.get("/system/audit-log", response_model=AuditLogResponse)
async def audit_log(
    employee_id: str = Query(""),
    endpoint: str = Query(""),
    limit: int = Query(50, ge=1, le=500),
    user=Depends(get_current_user),
):
    _require_sys_admin(user)
    rows = get_audit_logs(employee_id=employee_id, endpoint=endpoint, limit=limit)
    return AuditLogResponse(
        total=len(rows),
        rows=[
            AuditLogRow(
                timestamp=r.get("timestamp", "") or "",
                employee_id=r.get("employee_id", "") or "",
                name=r.get("name", "") or "",
                department=r.get("department", "") or "",
                role=r.get("role", "") or "",
                endpoint=r.get("endpoint", "") or "",
                method=r.get("method", "GET") or "GET",
                status_code=int(r.get("status_code") or 200),
                detail=r.get("detail", "") or "",
                ip_address=r.get("ip_address", "") or "",
            )
            for r in rows
        ],
    )


@router.post("/system/backup")
async def system_backup(user=Depends(get_current_user)):
    _require_sys_admin(user)

    auth_db = Path("data/auth.db")
    if not auth_db.exists():
        raise HTTPException(500, "auth.db 가 존재하지 않습니다.")

    backup_dir = Path("data/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = backup_dir / f"auth_{stamp}.db"

    src = sqlite3.connect(str(auth_db))
    dst = sqlite3.connect(str(target))
    with dst:
        src.backup(dst)
    src.close()
    dst.close()

    log_api_access(endpoint="/api/admin/system/backup", method="POST", user=user, detail=str(target))

    data = target.read_bytes()
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{target.name}"'},
    )


@router.get("/system/health", response_model=SystemHealthResponse)
async def system_health(user=Depends(get_current_user)):
    _require_sys_admin(user)

    auth_db = Path("data/auth.db")
    employees_db = Path("data/employees.db")
    audit_db = Path("data/audit.db")

    seed_users = 0
    try:
        from core.auth.database import get_auth_db

        conn = get_auth_db()
        seed_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        conn.close()
    except Exception:  # noqa: BLE001
        seed_users = 0

    return SystemHealthResponse(
        auth_db_ok=auth_db.exists(),
        employees_db_ok=employees_db.exists(),
        audit_db_ok=audit_db.exists(),
        seed_users=seed_users,
        active_sessions=0,
    )


# ═══════════════════════════════════════════════════════════════════════
# v4.8 F 트랙 — Management Console (4 카테고리)
# ═══════════════════════════════════════════════════════════════════════


class BulkRoleChangeRequest(BaseModel):
    user_ids: list[str] = Field(default_factory=list)
    target_role: int = Field(..., ge=1, le=5)
    reason: str = ""


@router.post("/users/bulk")
async def bulk_create_users(
    request: Request,  # noqa: ARG001 — uvicorn parsing 호환
    file: UploadFile = File(...),
    dry_run: bool = Query(True),
    user=Depends(get_current_user),
):
    """CSV 일괄 사용자 생성/업데이트 (HR_ADMIN+).

    multipart `file` + `?dry_run=true|false`. dry_run=True 가 기본값(안전).
    """
    _require_hr_admin(user)
    content = await file.read()
    try:
        text = content.decode("utf-8-sig", errors="replace")
    except Exception:
        text = content.decode("utf-8", errors="replace")

    from features.admin.bulk_create import ingest_users_csv

    result = ingest_users_csv(
        text,
        dry_run=bool(dry_run),
        actor_employee_id=getattr(user, "employee_id", ""),
    )

    log_api_access(
        endpoint="/api/admin/users/bulk",
        method="POST",
        user=user,
        detail=(
            f"file={file.filename} dry_run={dry_run} "
            f"total={result.rows_total} inserted={result.rows_inserted} "
            f"updated={result.rows_updated} skipped={result.rows_skipped} "
            f"errors={result.rows_error}"
        ),
    )
    return result


@router.post("/users/bulk-role")
async def bulk_role_change(req: BulkRoleChangeRequest, user=Depends(get_current_user)):
    """선택된 user_ids 의 role_level 을 일괄 변경 (HR_ADMIN+).

    request.user_ids 는 employee_id 의 리스트. target_role 는 1~5.
    """
    _require_hr_admin(user)
    if not req.user_ids:
        raise HTTPException(400, "user_ids 가 비어 있습니다.")
    if len(req.user_ids) > 200:
        raise HTTPException(400, "한 번에 200명 이하만 변경할 수 있습니다.")

    actor_level = resolve_user_role_level(user)
    if req.target_role > actor_level and actor_level < 5:
        raise HTTPException(403, "본인보다 높은 권한 레벨은 부여할 수 없습니다.")

    from features.admin.bulk_create import apply_bulk_role_change

    try:
        out = apply_bulk_role_change(
            req.user_ids,
            req.target_role,
            reason=req.reason,
            actor_employee_id=getattr(user, "employee_id", ""),
        )
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))

    log_api_access(
        endpoint="/api/admin/users/bulk-role",
        method="POST",
        user=user,
        detail=(
            f"target_role=L{req.target_role} changed={out['changed_count']} "
            f"not_found={len(out['not_found'])} reason={(req.reason or '')[:80]}"
        ),
    )
    return out


@router.get("/audit/timeline")
async def audit_timeline(
    actor: str = Query("", description="employee_id 일부일치"),
    action: str = Query("", description="endpoint/method 키워드"),
    target: str = Query("", description="detail 텍스트 부분일치"),
    result: str = Query("all", description="all|success|fail"),
    period_days: int = Query(30, ge=1, le=365),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user=Depends(get_current_user),
):
    """v4.8 F-Audit — 통합 감사 타임라인 (HR_ADMIN+).

    SQLite api_audit_log + (활성 시) Firestore audit shadow union.
    """
    _require_hr_admin(user)

    from pathlib import Path as _P
    import sqlite3 as _sql

    audit_db = _P("data/audit.db")
    rows: list[dict] = []
    if audit_db.exists():
        try:
            conn = _sql.connect(str(audit_db))
            conn.row_factory = _sql.Row
            cutoff = (datetime.utcnow() - timedelta(days=period_days)).isoformat()
            conditions = ["timestamp >= ?"]
            params: list = [cutoff]
            if actor:
                conditions.append("(employee_id LIKE ? OR name LIKE ?)")
                params.extend([f"%{actor}%", f"%{actor}%"])
            if action:
                conditions.append("(endpoint LIKE ? OR method LIKE ?)")
                params.extend([f"%{action}%", f"%{action}%"])
            if target:
                conditions.append("detail LIKE ?")
                params.append(f"%{target}%")
            if result == "success":
                conditions.append("status_code BETWEEN 200 AND 299")
            elif result == "fail":
                conditions.append("status_code >= 400")
            where = " AND ".join(conditions)
            offset = (page - 1) * page_size
            cursor = conn.execute(
                f"""SELECT id, timestamp, employee_id, name, department, role,
                          endpoint, method, status_code, detail, ip_address
                     FROM api_audit_log
                    WHERE {where}
                    ORDER BY timestamp DESC
                    LIMIT ? OFFSET ?""",
                [*params, page_size, offset],
            )
            rows = [dict(r) for r in cursor.fetchall()]
            total = conn.execute(
                f"SELECT COUNT(*) FROM api_audit_log WHERE {where}", params,
            ).fetchone()[0]
            conn.close()
        except Exception as e:  # noqa: BLE001
            logger.warning("[audit_timeline] sqlite query failed: %s", e)
            total = 0
    else:
        total = 0

    # Firestore shadow union (env 토글 시).
    import os as _os
    if _os.getenv("FIRESTORE_AUDIT_ENABLED", "false").lower() == "true":
        try:
            from core.auth.firestore_audit import read_recent_logins, is_available
            if is_available():
                shadow = read_recent_logins(limit=page_size)
                for s in shadow:
                    rows.append({
                        "id": f"fs-{s.get('id', '')}",
                        "timestamp": s.get("timestamp", ""),
                        "employee_id": s.get("employee_id", ""),
                        "name": "",
                        "department": "",
                        "role": "",
                        "endpoint": "/api/auth/login",
                        "method": "POST",
                        "status_code": 200 if s.get("success") else 401,
                        "detail": f"firestore audit (login success={s.get('success')})",
                        "ip_address": s.get("ip_address", ""),
                    })
                rows.sort(key=lambda r: r.get("timestamp") or "", reverse=True)
                rows = rows[:page_size]
        except Exception as e:  # noqa: BLE001
            logger.warning("[audit_timeline] firestore shadow union failed: %s", e)

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "rows": rows,
        "filters": {
            "actor": actor, "action": action, "target": target,
            "result": result, "period_days": period_days,
        },
    }


@router.get("/system/health-extended")
async def system_health_extended(user=Depends(get_current_user)):
    """v4.8 F-System — 확장 헬스 (SYS_ADMIN+).

    Beat / Redis / PostgreSQL / Supabase / Vector Store / SQLite / ChromaDB / Disk / External 섹션.
    각 섹션은 실패해도 status="error" 로 격리 반환 — 전체 응답은 항상 200.
    """
    _require_role_level(user, 3)

    import shutil as _shutil
    import os as _os
    from pathlib import Path as _P

    out: dict = {"timestamp": datetime.utcnow().isoformat(), "sections": {}}

    # 1) celery_beat
    try:
        beat_tick = _P("data/celery_beat.pid")
        last = beat_tick.stat().st_mtime if beat_tick.exists() else 0
        lag = max(0, int(__import__("time").time() - last)) if last else None
        out["sections"]["celery_beat"] = {
            "status": "ok" if (lag is not None and lag < 600) else ("unknown" if lag is None else "warn"),
            "last_heartbeat": datetime.fromtimestamp(last).isoformat() if last else None,
            "schedule_lag_seconds": lag,
        }
    except Exception as e:  # noqa: BLE001
        out["sections"]["celery_beat"] = {"status": "error", "error": str(e)}

    # 2) redis
    try:
        url = _os.getenv("REDIS_URL", "")
        if not url:
            out["sections"]["redis"] = {"status": "disabled", "note": "REDIS_URL 미설정"}
        else:
            import redis  # type: ignore
            import time as _t
            r = redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
            t0 = _t.time()
            r.ping()
            ping_ms = int((_t.time() - t0) * 1000)
            info = r.info(section="memory")
            out["sections"]["redis"] = {
                "status": "ok",
                "ping_ms": ping_ms,
                "used_memory_mb": round(int(info.get("used_memory", 0)) / 1024 / 1024, 2),
                "connected_clients": int(r.info(section="clients").get("connected_clients", 0)),
            }
    except Exception as e:  # noqa: BLE001
        out["sections"]["redis"] = {"status": "error", "error": str(e)}

    # 3) postgresql / supabase
    supabase_health: dict = {}
    try:
        from core.db import get_database_settings
        from scripts.verify_supabase_remote import collect_sanitized_supabase_health

        settings = get_database_settings()
        supabase_health = collect_sanitized_supabase_health()
        postgres_enabled = settings.backend == "postgres"
        out["sections"]["postgresql"] = {
            "status": "ok"
            if postgres_enabled and supabase_health.get("database_connected") is True
            else ("disabled" if not postgres_enabled else "warn"),
            "backend": settings.backend,
            "connected": bool(supabase_health.get("database_connected")),
            "alembic_current": bool(supabase_health.get("alembic_current")),
            "data_api_locked_down": bool(supabase_health.get("data_api_locked_down")),
            "default_admin_risk": bool(supabase_health.get("default_admin_risk")),
        }
        out["sections"]["supabase"] = {
            "status": supabase_health.get("status", "unknown"),
            "project_ref_configured": bool(supabase_health.get("project_ref_configured")),
            "url_matches_project_ref": bool(supabase_health.get("url_matches_project_ref")),
            "storage_configured": bool(supabase_health.get("storage_configured")),
            "storage_buckets_present": bool(supabase_health.get("storage_buckets_present")),
            "realtime_enabled": _os.getenv("ENABLE_SUPABASE_REALTIME", "false").lower() == "true",
        }
    except Exception as e:  # noqa: BLE001
        out["sections"]["postgresql"] = {"status": "error", "error": str(e)}
        out["sections"]["supabase"] = {"status": "error", "error": str(e)}
        supabase_health = {}

    # 4) sqlite
    try:
        files: dict[str, dict] = {}
        for name in ("auth.db", "employees.db", "audit.db", "feedback.db", "compliance.db", "learning.db"):
            p = _P("data") / name
            if p.exists():
                files[name] = {"size_mb": round(p.stat().st_size / 1024 / 1024, 2)}
        out["sections"]["sqlite"] = {"status": "ok", "files": files}
    except Exception as e:  # noqa: BLE001
        out["sections"]["sqlite"] = {"status": "error", "error": str(e)}

    # 5) chromadb (선택)
    chroma_status = "empty"
    chroma_collections = 0
    try:
        vroot = _P("vectorstore")
        if vroot.exists():
            chroma_collections = sum(1 for p in vroot.iterdir() if p.is_dir())
        chroma_status = "ok" if chroma_collections > 0 else "empty"
        out["sections"]["chromadb"] = {
            "status": chroma_status,
            "collections": chroma_collections,
        }
    except Exception as e:  # noqa: BLE001
        chroma_status = "error"
        out["sections"]["chromadb"] = {"status": "error", "error": str(e)}

    # 6) vector store routing
    try:
        vector_write_mode = _os.getenv("VECTOR_WRITE_MODE", "chroma").strip().lower() or "chroma"
        vector_read_mode = _os.getenv("VECTOR_READ_MODE", "chroma").strip().lower() or "chroma"
        postgres_vector_enabled = vector_write_mode in {"postgres", "dual"} or vector_read_mode == "postgres"
        chroma_enabled = vector_write_mode in {"chroma", "dual"} or vector_read_mode == "chroma"
        postgres_ready = bool(supabase_health.get("database_connected"))
        chroma_ready = chroma_status == "ok"
        if postgres_vector_enabled and not postgres_ready:
            vector_status = "warn"
        elif chroma_enabled and not chroma_ready:
            vector_status = "warn"
        else:
            vector_status = "ok"
        if vector_read_mode == "postgres":
            primary = "supabase_pgvector"
        elif vector_write_mode == "dual":
            primary = "dual_write_chroma_read"
        else:
            primary = "chromadb"
        out["sections"]["vector_store"] = {
            "status": vector_status,
            "write_mode": vector_write_mode,
            "read_mode": vector_read_mode,
            "primary": primary,
            "postgres_ready": postgres_ready,
            "chroma_ready": chroma_ready,
            "chroma_collections": chroma_collections,
        }
    except Exception as e:  # noqa: BLE001
        out["sections"]["vector_store"] = {"status": "error", "error": str(e)}

    # 7) disk
    try:
        data_path = _P("data")
        total, used, free = _shutil.disk_usage(str(data_path) if data_path.exists() else ".")
        out["sections"]["disk"] = {
            "status": "ok" if free > 1024 * 1024 * 1024 else "warn",
            "free_gb": round(free / 1024 ** 3, 2),
            "used_gb": round(used / 1024 ** 3, 2),
            "total_gb": round(total / 1024 ** 3, 2),
        }
    except Exception as e:  # noqa: BLE001
        out["sections"]["disk"] = {"status": "error", "error": str(e)}

    # 8) external
    try:
        from core.feature_flags import firebase_cost_flags_dict

        ext: dict = {}
        ext["slack_signing"] = bool(_os.getenv("SLACK_SIGNING_SECRET"))
        ext["firebase_admin"] = False
        try:
            import firebase_admin  # type: ignore
            ext["firebase_admin"] = bool(firebase_admin._apps)
        except Exception:
            pass
        ext["gemini_api_key_set"] = bool(_os.getenv("GEMINI_API_KEY") or _os.getenv("GOOGLE_API_KEY"))
        ext["firestore_audit_enabled"] = _os.getenv("FIRESTORE_AUDIT_ENABLED", "false").lower() == "true"
        firebase_cost = firebase_cost_flags_dict()
        ext["firebase_write_enabled"] = firebase_cost["write_enabled"]
        ext["firebase_read_fallback_enabled"] = firebase_cost["read_fallback_enabled"]
        ext["firebase_dryrun_capture_enabled"] = firebase_cost["dryrun_capture_enabled"]
        ext["supabase"] = supabase_health
        ext["supabase_status"] = supabase_health.get("status", "unknown")
        out["sections"]["external"] = {"status": "ok", **ext}
    except Exception as e:  # noqa: BLE001
        out["sections"]["external"] = {"status": "error", "error": str(e)}

    return out


@router.get("/stats/feature-heatmap")
async def stats_feature_heatmap(
    period: str = Query("day", description="day|week|month"),
    period_days: int = Query(7, ge=1, le=365),
    user=Depends(get_current_user),
):
    """v4.8 F-Stats — feature × bucket 히트맵 (L1+).

    period=day → period_days 만큼 일 단위 셀.
    period=week → 7주, period=month → 12달.
    """
    _require_role_level(user, 1)
    from features.admin.usage_analytics import get_feature_heatmap

    data = get_feature_heatmap(period=period, period_days=period_days)
    return data


# ═══════════════════════════════════════════════════════════════════════
# H8 — BigQuery audit pipeline (장기 분석)
# Cloud Logging sink 가 ajin-cb.ajin_audit 에 적재한 login 이벤트를 쿼리.
# 1~5분 sink 지연 — SecurityTab 실시간(30s)은 Firestore(H7) 사용,
# 본 엔드포인트는 "장기 추세·부서별 활동" 등 콜드 패스 분석 용도.
# ═══════════════════════════════════════════════════════════════════════


@router.get("/audit/bq/summary")
def audit_bq_summary(days: int = 30, user=Depends(get_current_user)):
    """BigQuery 기반 로그인 요약 (지난 N일)."""
    _require_hr_admin(user)
    from backend.services.bigquery_audit import fetch_summary
    return fetch_summary(days=days)


@router.get("/audit/bq/hour-distribution")
def audit_bq_hour_distribution(days: int = 30, user=Depends(get_current_user)):
    """BigQuery 기반 시간대 분포 (24-bin)."""
    _require_hr_admin(user)
    from backend.services.bigquery_audit import fetch_hour_distribution
    return {"items": fetch_hour_distribution(days=days)}


@router.get("/audit/bq/department-dau")
def audit_bq_department_dau(days: int = 30, user=Depends(get_current_user)):
    """BigQuery 기반 부서별 일일 활성 사용자."""
    _require_hr_admin(user)
    from backend.services.bigquery_audit import fetch_department_dau
    return {"items": fetch_department_dau(days=days)}


@router.get("/security/login-history-archived")
def login_history_archived(
    date: str = Query(..., description="YYYY-MM-DD"),
    limit: int = Query(500, ge=1, le=5000),
    user=Depends(get_current_user),
):
    """v4.9.2 — 90일 초과 archived 로그인 이력 (BigQuery audit).

    SecurityTab 달력에서 90일 초과 일자 클릭 시 호출. GCP 인증 미설정 시 빈 응답.
    """
    _require_hr_admin(user)
    import re as _re
    if not _re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        raise HTTPException(status_code=422, detail="date format must be YYYY-MM-DD")

    from backend.services.bigquery_audit import fetch_archived_logins, is_available
    if not is_available():
        return {"total": 0, "history": [], "source": "bigquery", "available": False}

    items = fetch_archived_logins(date=date, limit=limit)
    return {"total": len(items), "history": items, "source": "bigquery", "available": True}


# ═══════════════════════════════════════════════════════════════════════
# PR-E5 — Audit Dashboard (5-dimension) + 7-pattern anomaly feed
# ═══════════════════════════════════════════════════════════════════════


@router.get("/audit/anomaly/feed")
def audit_anomaly_feed(
    window_hours: int = Query(24, ge=1, le=720),
    user=Depends(get_current_user),
):
    """7-패턴 (기존 3 brute_force/unusual_hour/inactive_access +
    신규 4 privilege_escalation/mass_export/off_hours_export/deprecated_account_active)
    통합 알람 피드. severity DESC 정렬. HR_ADMIN(L4)+ 필요.
    """
    _require_hr_admin(user)
    from features.admin.security_monitor import build_anomaly_feed
    items = build_anomaly_feed(window_hours=window_hours)
    return {
        "window_hours": window_hours,
        "total": len(items),
        "items": items,
    }


@router.get("/audit/dashboard")
def audit_dashboard(
    period: str = Query("week", description="day|week|month"),
    user=Depends(get_current_user),
):
    """5-차원 audit dashboard 통합 응답:

    - time_pattern: 시간 × 요일 × 부서 사용량 (heatmap)
    - anomalies: 7-패턴 통합 알람 feed
    - permission_violations: K4=0 검증 (401/403 row)
    - feature_usage: A~F 기능별 사용량 + 만족도
    - change_audit: PUT/DELETE/grant/revoke 시간순 timeline

    SYS_ADMIN(L5) 필요 — SecurityAlertsTab role≥4 와 별도로 strict.
    """
    if period not in ("day", "week", "month"):
        raise HTTPException(status_code=422, detail="period must be day|week|month")
    _require_hr_admin(user)
    from features.admin.security_monitor import build_dashboard
    return build_dashboard(period=period)


# ═══════════════════════════════════════════════════════════════════════
# PR-E6 — SIEM Export (Splunk JSON / ArcSight CEF / IBM QRadar LEEF 2.0)
# ═══════════════════════════════════════════════════════════════════════

def _query_audit_rows(start_ts: int, end_ts: int) -> list[dict]:
    """audit.db api_audit_log SELECT WHERE timestamp BETWEEN start and end.

    start_ts / end_ts 가 0 이면 범위 제한 없이 전체 반환 (최대 50,000건).
    """
    import sqlite3 as _sql

    audit_db = Path("data/audit.db")
    if not audit_db.exists():
        return []

    conn = _sql.connect(str(audit_db))
    conn.row_factory = _sql.Row
    try:
        if start_ts and end_ts:
            from datetime import datetime as _dt, timezone as _tz
            start_iso = _dt.fromtimestamp(start_ts, tz=_tz.utc).isoformat()
            end_iso = _dt.fromtimestamp(end_ts, tz=_tz.utc).isoformat()
            cursor = conn.execute(
                """SELECT employee_id AS actor, endpoint AS action,
                          detail AS target, status_code AS result,
                          ip_address, timestamp AS ts
                     FROM api_audit_log
                    WHERE timestamp BETWEEN ? AND ?
                    ORDER BY timestamp DESC
                    LIMIT 50000""",
                (start_iso, end_iso),
            )
        else:
            cursor = conn.execute(
                """SELECT employee_id AS actor, endpoint AS action,
                          detail AS target, status_code AS result,
                          ip_address, timestamp AS ts
                     FROM api_audit_log
                    ORDER BY timestamp DESC
                    LIMIT 50000""",
            )
        rows = [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()
    return rows


# ═══════════════════════════════════════════════════════════════════════
# PR-E7 — 권한 변경 2단계 결재 워크플로우
# 흐름: requester (L4+) → IT보안 (L5) 1차 → 임원 (L5 + EXECUTIVE position) 최종
# ═══════════════════════════════════════════════════════════════════════


class PermissionChangeRequestBody(BaseModel):
    permission_key: str = Field(..., min_length=1)
    new_value: dict = Field(..., description="신규 권한 정의 (description/min_role/departments/...)")
    reason: str = Field(..., min_length=1, max_length=2000)


class PermissionRejectBody(BaseModel):
    reason: str = Field(..., min_length=1, max_length=2000)


# 임원 직급 — 권한 변경 최종 승인자
_EXECUTIVE_POSITIONS = {
    "이사", "상무", "전무", "부사장", "사장",
}


def _require_executive(user) -> None:
    """임원 최종 승인 가드 — L5 + 임원 직급 OR SYS_ADMIN."""
    role = getattr(user, "role", "EMPLOYEE")
    position = getattr(user, "position", "") or ""
    user_level = resolve_user_role_level(user)
    if role == "SYS_ADMIN":
        return
    if user_level >= 5 and position in _EXECUTIVE_POSITIONS:
        return
    raise HTTPException(
        status_code=403,
        detail="임원 직급 (이사/상무/전무/부사장/사장) + L5 권한이 필요합니다.",
    )


@router.post("/permissions/request")
def request_permission_change(
    body: PermissionChangeRequestBody, user=Depends(get_current_user)
):
    """권한 변경 요청 생성 (L4 HR_ADMIN+)."""
    _require_hr_admin(user)
    from features.admin.permission_workflow import (
        WorkflowError,
        create_change_request,
    )
    try:
        request_id = create_change_request(
            permission_key=body.permission_key,
            new_value=body.new_value,
            reason=body.reason,
            actor=getattr(user, "employee_id", ""),
        )
    except WorkflowError as e:
        raise HTTPException(400, str(e))

    log_api_access(
        endpoint="/api/admin/permissions/request",
        method="POST",
        user=user,
        detail=f"request_id={request_id} key={body.permission_key}",
    )
    return {"request_id": request_id, "status": "pending"}


@router.post("/permissions/approve/security/{request_id}")
def approve_permission_security(request_id: int, user=Depends(get_current_user)):
    """IT 보안 1차 승인 (L5 SYS_ADMIN+)."""
    _require_sys_admin(user)
    from features.admin.permission_workflow import (
        WorkflowError,
        approve_by_security,
    )
    try:
        updated = approve_by_security(request_id, getattr(user, "employee_id", ""))
    except WorkflowError as e:
        raise HTTPException(409, str(e))

    log_api_access(
        endpoint=f"/api/admin/permissions/approve/security/{request_id}",
        method="POST",
        user=user,
        detail=f"status={updated.get('status')}",
    )
    return updated


@router.post("/permissions/approve/executive/{request_id}")
def approve_permission_executive(request_id: int, user=Depends(get_current_user)):
    """임원 최종 승인 + 자동 applied (L5 + EXECUTIVE)."""
    _require_executive(user)
    from features.admin.permission_workflow import (
        WorkflowError,
        approve_by_executive,
    )
    try:
        updated = approve_by_executive(request_id, getattr(user, "employee_id", ""))
    except WorkflowError as e:
        raise HTTPException(409, str(e))

    log_api_access(
        endpoint=f"/api/admin/permissions/approve/executive/{request_id}",
        method="POST",
        user=user,
        detail=f"status={updated.get('status')}",
    )
    return updated


@router.post("/permissions/reject/{request_id}")
def reject_permission_change(
    request_id: int,
    body: PermissionRejectBody,
    user=Depends(get_current_user),
):
    """결재 반려 (L5 SYS_ADMIN+ — 보안/임원 단계 모두 거부 가능)."""
    _require_sys_admin(user)
    from features.admin.permission_workflow import WorkflowError, reject
    try:
        updated = reject(
            request_id, getattr(user, "employee_id", ""), body.reason,
        )
    except WorkflowError as e:
        raise HTTPException(409, str(e))

    log_api_access(
        endpoint=f"/api/admin/permissions/reject/{request_id}",
        method="POST",
        user=user,
        detail=f"reason={(body.reason or '')[:80]}",
    )
    return updated


@router.get("/permissions/queue")
def get_permission_queue(
    status: str = Query("pending", description="pending|security_approved"),
    user=Depends(get_current_user),
):
    """대기열 조회 (L5 SYS_ADMIN+)."""
    _require_sys_admin(user)
    from features.admin.permission_workflow import get_queue
    return {"status": status, "items": get_queue(status_filter=status)}


# ── PR-E8 — Permission 조회 / dry-run preview ──────────────────────────────


def _serialize_permission(perm: dict) -> dict:
    """list/get 응답 직렬화 (departments set → list)."""
    out = dict(perm)
    depts = out.get("departments")
    if isinstance(depts, (set, frozenset)):
        out["departments"] = sorted(depts)
    return out


@router.get("/permissions/list")
def list_permissions_endpoint(user=Depends(get_current_user)):
    """전체 권한 매트릭스 데이터 (L4 HR_ADMIN+).

    PermissionMatrixUI 의 27 부서 × 5 역할 표 렌더링 소스.
    """
    _require_hr_admin(user)
    from core.auth.permissions_db import init_permissions_db, list_permissions

    init_permissions_db()
    items = [_serialize_permission(p) for p in list_permissions()]
    return {"total": len(items), "items": items}


@router.get("/permissions/{key}")
def get_permission_endpoint(key: str, user=Depends(get_current_user)):
    """단일 권한 조회 (L4 HR_ADMIN+). 없으면 404."""
    _require_hr_admin(user)
    from core.auth.permissions_db import get_permission, init_permissions_db

    init_permissions_db()
    perm = get_permission(key)
    if perm is None:
        raise HTTPException(404, f"permission '{key}' not found")
    return _serialize_permission(perm)


@router.post("/permissions/preview")
def preview_permission_change(
    body: PermissionChangeRequestBody, user=Depends(get_current_user),
):
    """dry-run preview — 결재 요청 전에 before/after diff 만 반환 (L4 HR_ADMIN+).

    상태 변경 / 결재 큐 INSERT 없음. UI 미리보기 전용.
    """
    _require_hr_admin(user)
    from core.auth.permissions_db import get_permission, init_permissions_db

    init_permissions_db()
    before = get_permission(body.permission_key)
    return {
        "permission_key": body.permission_key,
        "before": _serialize_permission(before) if before else None,
        "after": body.new_value,
        "is_new": before is None,
        "reason": body.reason,
    }


@router.get("/permissions/history")
def get_permission_history(
    limit: int = Query(50, ge=1, le=500), user=Depends(get_current_user)
):
    """변경 이력 (applied + rejected). L4 HR_ADMIN+."""
    _require_hr_admin(user)
    from features.admin.permission_workflow import get_history
    return {"limit": limit, "items": get_history(limit=limit)}


@router.get("/audit/export/siem", response_class=PlainTextResponse)
def export_siem_format(
    start_ts: int = Query(0, description="start unix timestamp (sec); 0 = no lower bound"),
    end_ts: int = Query(0, description="end unix timestamp (sec); 0 = no upper bound"),
    format: Literal["json", "cef", "leef"] = Query("json", description="json|cef|leef"),
    user=Depends(get_current_user),
):
    """SIEM 호환 포맷 export. SYS_ADMIN(L5) 필수.

    - json: Splunk HEC 포맷 (application/json)
    - cef: ArcSight CEF 라인 (text/plain)
    - leef: IBM QRadar LEEF 2.0 라인 (text/plain)
    """
    _require_sys_admin(user)

    from backend.services.audit_export import to_cef, to_leef, to_siem_json

    rows = _query_audit_rows(start_ts, end_ts)

    if format == "json":
        return JSONResponse(content=to_siem_json(rows))
    elif format == "cef":
        return PlainTextResponse("\n".join(to_cef(rows)))
    else:  # leef
        return PlainTextResponse("\n".join(to_leef(rows)))
