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
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from backend.auth_middleware import get_audit_logs, log_api_access
from backend.dependencies import get_current_user
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
    """user.role 의 레벨이 min_level 이상이어야 한다. 아니면 403."""
    from core.auth.rbac import get_role_level

    user_level = get_role_level(getattr(user, "role", "EMPLOYEE"))
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
    from core.auth.rbac import get_role_level

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

    actor_level = get_role_level(getattr(user, "role", "EMPLOYEE"))
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

    conn = get_auth_db()
    target = conn.execute("SELECT user_id FROM users WHERE employee_id = ?", (employee_id,)).fetchone()
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
        (target["user_id"], new_hash),
    )
    conn.commit()
    conn.close()
    return ResetPasswordResponse(employee_id=employee_id, initial_password=new_pw)


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
    from core.auth.rbac import get_role_level

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

    actor_level = get_role_level(getattr(user, "role", "EMPLOYEE"))
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
    initial_pw = f"ajin{next_id[-4:]}"

    return EmployeeIDPreviewResponse(
        department=req.department,
        prefix=prefix,
        next_id=next_id,
        sequence=seq,
        suggested_email=suggested_email,
        suggested_initial_password=initial_pw,
    )


@router.post("/users", response_model=CreateEmployeeResponse, status_code=201)
async def create_employee(req: CreateEmployeeRequest, user=Depends(get_current_user)):
    _require_hr_admin(user)

    from core.auth.database import get_auth_db
    from core.auth.department_config import (
        DEPARTMENT_CATEGORIES,
        generate_employee_id,
        get_dept_prefix,
    )
    from core.auth.password import generate_initial_password, hash_password
    from core.auth.rbac import get_role_level

    valid_dept = any(req.department in depts for depts in DEPARTMENT_CATEGORIES.values())
    if not valid_dept:
        raise HTTPException(400, f"유효하지 않은 부서: {req.department}")

    actor_level = get_role_level(getattr(user, "role", "EMPLOYEE"))

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

    conn.execute(
        """INSERT INTO users
             (employee_id, username, password_hash, role_id, is_active, must_change_pw,
              email, phone, department, position, hire_date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            emp_id, req.username, pw_hash, role_row["role_id"],
            1 if req.is_active else 0,
            1 if req.must_change_pw else 0,
            email, req.phone, req.department, req.position, req.hire_date,
        ),
    )
    conn.commit()
    conn.close()

    instructions = (
        f"# AJIN AI Assistant 계정 발급 안내\n\n"
        f"- 사번: **{emp_id}**\n"
        f"- 이름: {req.username}\n"
        f"- 본부 / 부서: {req.division} / {req.department}\n"
        f"- 직급: {req.position}\n"
        f"- 역할: {req.role_name} (L{role_row['role_level']})\n"
        f"- 이메일: {email}\n\n"
        f"## 초기 로그인\n\n"
        f"- 초기 비밀번호: **{initial_pw}** (최초 로그인 시 즉시 변경 필요)\n"
        f"- 비밀번호 정책: 8자 이상 + 대소문자 + 숫자 + 특수문자, 동일 문자 3회 연속 금지\n"
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
        initial_password=initial_pw,
        must_change_pw=req.must_change_pw,
        issuance_note="발급된 초기 비밀번호는 한 번만 표시됩니다. 안전한 채널로 사용자에게 전달하세요.",
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
