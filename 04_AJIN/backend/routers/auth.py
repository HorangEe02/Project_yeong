"""인증 API 라우터 — 로그인, 비밀번호 변경, 토큰 갱신.

PR-E3: Firebase ID Token 교환 엔드포인트 폐기. 외부 IdP (OIDC/SAML/LDAP) 흐름은
`backend/routers/idp.py` 에서 처리한다.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from backend.dependencies import get_current_user
from core.data_lineage import lineage_values
from core.audit_log_emitter import emit_login_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# 공개 쇼케이스 게스트(읽기 전용) 세션 — /showcase 를 로그인 없이 열람하기 위함.
# role_level=4 → 법규(D)·설비(E)·관리(F) 화면까지 열람 가능. 단, 변경 작업은
# dependencies.require_role_level / require_permission 의 게스트 unsafe-method 가드가
# 차단하므로 공개 게스트는 L3/L4 mutation 을 수행할 수 없다(읽기 전용 유지).
# DB user row 없는 합성 신원(토큰 기반).
GUEST_EMPLOYEE_ID = "GUEST"
GUEST_ROLE_LEVEL = 4


def _is_guest(user) -> bool:
    """현재 사용자가 쇼케이스 게스트(읽기 전용)인지."""
    return (
        getattr(user, "employee_id", "") == GUEST_EMPLOYEE_ID
        or str(getattr(user, "role", "")) == "GUEST"
    )


def _guest_disabled() -> bool:
    """`SHOWCASE_GUEST_ENABLED=false`(등)면 게스트 미리보기를 끈다."""
    return os.environ.get("SHOWCASE_GUEST_ENABLED", "true").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }


def _guest_user_dict() -> dict:
    """쇼케이스 게스트(읽기 전용) 합성 신원 — DB row 없이 토큰 컨텍스트로만 존재.

    `/auth/guest`(발급) 와 `/auth/refresh`(재발급) 가 공유해 두 경로의 신원이
    어긋나지 않도록 단일 출처로 둔다.
    """
    return {
        "employee_id": GUEST_EMPLOYEE_ID,
        "username": "게스트 (읽기 전용)",
        "role_name": "GUEST",
        "role_level": GUEST_ROLE_LEVEL,
        "must_change_pw": 0,
        "department": "체험",
        "position": "Showcase Guest",
    }


class LoginRequest(BaseModel):
    employee_id: str
    password: str


class LoginResponse(BaseModel):
    token_type: str = "cookie"
    employee_id: str
    username: str
    role_name: str
    role_level: int
    must_change_pw: bool = False
    department: str = ""
    position: str = ""
    # v4.7 Feature E Phase 2 — 2FA 중간 응답 (totp_enabled=1 사용자)
    require_2fa: bool = False
    mid_token: str | None = None


class ChangePasswordRequest(BaseModel):
    """Authenticated password change request."""

    model_config = ConfigDict(extra="forbid")

    current_password: str
    new_password: str


class ProfileResponse(BaseModel):
    """본인 프로필 — GET /me"""
    employee_id: str
    username: str
    role_name: str
    role_level: int
    department: str = ""
    position: str = ""
    email: str = ""
    phone: str = ""
    hire_date: str = ""
    last_login: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    is_active: bool = True
    must_change_pw: bool = False
    # v3.9 — 디지털 사원증 사진 (data:image/jpeg;base64,... 형식)
    photo_url: str = ""


class PhotoUpdateRequest(BaseModel):
    """본인 증명사진 변경 — PATCH /me/photo. 256x256 JPEG base64 data URL."""

    photo_data_url: str = Field(..., min_length=10, max_length=300_000)


class ProfileUpdateRequest(BaseModel):
    """본인 정보 수정 — PUT /me. 화이트리스트 필드만 적용.

    일반 사용자: email, phone, position
    HR_ADMIN(Lv4)+: + employee_id, username, department, role_name
    """
    email: str | None = None
    phone: str | None = None
    position: str | None = None
    # HR_ADMIN/SYS_ADMIN 전용 (role_level >= 4)
    employee_id: str | None = None
    username: str | None = None
    department: str | None = None
    role_name: str | None = None


class ProfileUpdateResponse(BaseModel):
    """프로필 응답 + 재인증 필요 여부 플래그."""
    profile: ProfileResponse
    reissued: bool = False  # 사번/역할 변경 시 true → 프론트가 강제 로그아웃


class LoginHistoryEntry(BaseModel):
    id: int
    action: str
    success: bool
    ip_address: str = ""
    user_agent: str = ""
    timestamp: str


class LoginHistoryResponse(BaseModel):
    employee_id: str
    total: int
    history: list[LoginHistoryEntry]


def _login_history_lineage(user) -> dict[str, str]:
    """Derive login_history lineage from the authenticated auth.users row.

    Args:
        user: sqlite3.Row returned by the login query.

    Returns:
        Canonical lineage dict for login_history inserts.
    """
    keys = set(user.keys()) if hasattr(user, "keys") else set()
    data_class = user["data_class"] if "data_class" in keys else "unknown"
    source_system = user["source_system"] if "source_system" in keys else "auth_login"
    source_label = user["source_label"] if "source_label" in keys else "auth_login"
    if data_class in ("", None, "unknown"):
        data_class = "system" if user["employee_id"] == "admin" else "unknown"
    return lineage_values(data_class, source_system or "auth_login", source_label or "auth_login")


def _login_response_from_user(user, *, require_2fa: bool = False, mid_token: str | None = None) -> LoginResponse:
    """Build the browser-safe login response without JWT values.

    Args:
        user: SQLite row joined with role metadata.
        require_2fa: Whether the response is a 2FA challenge rather than a session.
        mid_token: Short-lived mid-token used only by the 2FA verify endpoint.

    Returns:
        LoginResponse: User/session metadata safe for the response body.
    """

    keys = set(user.keys()) if hasattr(user, "keys") else set()
    return LoginResponse(
        employee_id=user["employee_id"],
        username=user["username"],
        role_name=user["role_name"],
        role_level=user["role_level"],
        must_change_pw=bool(user["must_change_pw"]),
        department=(user["department"] or "") if "department" in keys else "",
        position=(user["position"] or "") if "position" in keys else "",
        require_2fa=require_2fa,
        mid_token=mid_token,
    )


def _issue_browser_session(response: Response, user) -> None:
    """Issue browser cookies and persist the refresh allowlist entry.

    Args:
        response: FastAPI response used to set cookies.
        user: SQLite row joined with role metadata.

    Raises:
        RuntimeError: If the refresh-token allowlist cannot be written.
    """

    from core.auth.cookies import set_auth_cookies
    from core.auth.jwt_handler import create_access_token
    from core.auth.refresh_sessions import issue_refresh_session

    access_token = create_access_token(
        employee_id=user["employee_id"],
        username=user["username"],
        role_name=user["role_name"],
        role_level=user["role_level"],
    )
    refresh_token = issue_refresh_session(user["employee_id"])
    set_auth_cookies(response, access_token, refresh_token)


@router.post("/guest", response_model=LoginResponse)
async def guest_login(response: Response):
    """공개 쇼케이스용 게스트(읽기 전용) 세션 발급 — 자격증명 불필요.

    심사위원·팀원이 로그인 없이 /showcase 의 라이브 화면을 볼 수 있게 한다.
    role_level=2 라 법규 등 열람은 가능하지만 크롤러 실행(L3)·상태변경/관리(L4)
    등 mutation 은 기존 RBAC 로 차단된다. `SHOWCASE_GUEST_ENABLED=false` 로 비활성화.
    """
    if _guest_disabled():
        raise HTTPException(status_code=404, detail="게스트 미리보기가 비활성화되어 있습니다.")

    from core.auth.cookies import set_auth_cookies
    from core.auth.jwt_handler import create_access_token
    from core.auth.refresh_sessions import issue_refresh_session

    guest = _guest_user_dict()
    # 심사 세션 동안 재발급 없이 유지되도록 access 8시간.
    access_token = create_access_token(
        employee_id=guest["employee_id"],
        username=guest["username"],
        role_name=guest["role_name"],
        role_level=guest["role_level"],
        expires_hours=8,
    )
    refresh_token = issue_refresh_session(guest["employee_id"])
    set_auth_cookies(response, access_token, refresh_token)
    return _login_response_from_user(guest)


def _record_login_policy_block(conn, user, request: Request, reason: str) -> None:
    """Record a failed local-login policy decision without storing secrets.

    Args:
        conn: Open auth DB connection.
        user: Auth user row joined with role metadata.
        request: FastAPI request for IP/user-agent metadata.
        reason: Stable policy reason such as ``local_login_disabled``.
    """

    login_lineage = _login_history_lineage(user)
    conn.execute(
        """INSERT INTO login_history
             (user_id, employee_id, action, success,
              data_class, source_system, source_label, source_updated_at)
           VALUES (?, ?, 'login_policy_block', 0, ?, ?, ?, ?)""",
        (
            user["user_id"],
            user["employee_id"],
            login_lineage["data_class"],
            login_lineage["source_system"],
            login_lineage["source_label"],
            login_lineage["source_updated_at"],
        ),
    )
    conn.commit()
    emit_login_event(
        user_id=user["user_id"],
        employee_id=user["employee_id"],
        success=False,
        ip_address=request.client.host if request and request.client else "",
        user_agent=request.headers.get("user-agent", "") if request else "",
        department=user["department"] if "department" in user.keys() else "",
        role_level=user["role_level"],
        extra={"policy": reason},
    )


def _persist_password_change_to_postgres(
    *,
    employee_id: str,
    old_password_hash: str,
    new_password_hash: str,
) -> None:
    """Persist a browser password change to the Postgres auth source.

    Args:
        employee_id: Target AJIN employee id.
        old_password_hash: Hash read from the SQLite auth mirror before change.
        new_password_hash: Newly generated password hash.

    Raises:
        RuntimeError: If Postgres is enabled and the source row cannot be updated.
    """

    from core.db import create_sqlalchemy_engine, is_postgres_enabled

    if not is_postgres_enabled():
        return

    try:
        import sqlalchemy as sa

        engine = create_sqlalchemy_engine()
        with engine.begin() as pg:
            result = pg.execute(
                sa.text(
                    """
                    update public.users
                       set password_hash = :new_hash,
                           must_change_pw = false,
                           failed_attempts = 0,
                           locked_until = null,
                           updated_at = CURRENT_TIMESTAMP
                     where employee_id = :employee_id
                       and password_hash = :old_hash
                    """
                ),
                {
                    "employee_id": employee_id,
                    "old_hash": old_password_hash,
                    "new_hash": new_password_hash,
                },
            )
    except Exception as exc:
        raise RuntimeError("Postgres password sync failed") from exc

    if getattr(result, "rowcount", 0) != 1:
        raise RuntimeError("Postgres password sync affected no rows")


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, request: Request, response: Response):
    """사원번호 + 비밀번호로 로그인. H7+H8: Firestore audit_logs + Cloud Logging emit."""
    from core.auth.database import get_auth_db
    from core.auth.password import verify_password

    conn = get_auth_db()

    # 사용자 조회
    user = conn.execute(
        """SELECT u.*, r.role_name, r.role_level
           FROM users u JOIN roles r ON u.role_id = r.role_id
           WHERE u.employee_id = ?""",
        (req.employee_id,),
    ).fetchone()

    if not user:
        conn.close()
        raise HTTPException(status_code=401, detail="사원번호 또는 비밀번호가 올바르지 않습니다.")

    # 계정 잠금 확인
    if user["locked_until"]:
        lock_until = datetime.fromisoformat(user["locked_until"])
        if lock_until > datetime.now(timezone.utc):
            conn.close()
            raise HTTPException(status_code=423, detail="계정이 잠금 상태입니다. 30분 후 다시 시도하세요.")
        else:
            # 잠금 해제
            conn.execute("UPDATE users SET locked_until = NULL, failed_attempts = 0 WHERE user_id = ?",
                        (user["user_id"],))

    # 비활성 계정 확인
    if not user["is_active"]:
        conn.close()
        raise HTTPException(status_code=403, detail="비활성화된 계정입니다. 관리자에게 문의하세요.")

    try:
        from core.auth.policy import local_password_login_block_reason

        block_reason = local_password_login_block_reason(user)
    except ValueError:
        conn.close()
        raise HTTPException(status_code=500, detail="auth_policy_invalid")
    if block_reason:
        _record_login_policy_block(conn, user, request, block_reason)
        conn.close()
        raise HTTPException(status_code=403, detail=block_reason)

    # 비밀번호 검증
    if not verify_password(req.password, user["password_hash"]):
        # 실패 횟수 증가
        new_attempts = user["failed_attempts"] + 1
        if new_attempts >= 5:
            # 5회 실패 → 30분 잠금
            from datetime import timedelta
            lock_until = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
            conn.execute("UPDATE users SET failed_attempts = ?, locked_until = ? WHERE user_id = ?",
                        (new_attempts, lock_until, user["user_id"]))
        else:
            conn.execute("UPDATE users SET failed_attempts = ? WHERE user_id = ?",
                        (new_attempts, user["user_id"]))

        # 로그인 실패 이력 — SQLite (기존 hot path)
        login_lineage = _login_history_lineage(user)
        conn.execute(
            """INSERT INTO login_history
                 (user_id, employee_id, action, success,
                  data_class, source_system, source_label, source_updated_at)
               VALUES (?, ?, 'login', 0, ?, ?, ?, ?)""",
            (
                user["user_id"],
                req.employee_id,
                login_lineage["data_class"],
                login_lineage["source_system"],
                login_lineage["source_label"],
                login_lineage["source_updated_at"],
            ),
        )
        conn.commit()
        conn.close()
        # H7+H8 — Firestore audit_logs + Cloud Logging JSON 이벤트
        _ip = request.client.host if request and request.client else ""
        _ua = request.headers.get("user-agent", "") if request else ""
        emit_login_event(
            user_id=user["user_id"],
            employee_id=req.employee_id,
            success=False,
            ip_address=_ip,
            user_agent=_ua,
            department=user["department"] if "department" in user.keys() else "",
            role_level=user["role_level"],
            extra={"fail_count": new_attempts},
        )
        raise HTTPException(status_code=401, detail=f"비밀번호가 올바르지 않습니다. ({new_attempts}/5)")

    # 로그인 성공 — 실패 횟수 리셋
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE users SET failed_attempts = 0, locked_until = NULL, last_login = ? WHERE user_id = ?",
        (now, user["user_id"]),
    )
    login_lineage = _login_history_lineage(user)
    conn.execute(
        """INSERT INTO login_history
             (user_id, employee_id, action, success,
              data_class, source_system, source_label, source_updated_at)
           VALUES (?, ?, 'login', 1, ?, ?, ?, ?)""",
        (
            user["user_id"],
            req.employee_id,
            login_lineage["data_class"],
            login_lineage["source_system"],
            login_lineage["source_label"],
            login_lineage["source_updated_at"],
        ),
    )
    conn.commit()
    conn.close()

    # H7+H8 — Firestore audit_logs + Cloud Logging JSON 이벤트
    _ip = request.client.host if request and request.client else ""
    _ua = request.headers.get("user-agent", "") if request else ""
    emit_login_event(
        user_id=user["user_id"],
        employee_id=req.employee_id,
        success=True,
        ip_address=_ip,
        user_agent=_ua,
        department=user["department"] if "department" in user.keys() else "",
        role_level=user["role_level"],
    )

    # v4.7 Feature E Phase 2 — 2FA 활성 사용자는 mid_token 만 발급 → 2FA verify 단계 필요
    totp_enabled = bool(user["totp_enabled"]) if "totp_enabled" in user.keys() else False
    if totp_enabled:
        from core.auth.jwt_handler import mint_mid_token

        mid = mint_mid_token(user["employee_id"], ttl_seconds=120)
        return _login_response_from_user(user, require_2fa=True, mid_token=mid)

    _issue_browser_session(response, user)
    return _login_response_from_user(user)


@router.post("/change-password")
async def change_password(req: ChangePasswordRequest, user=Depends(get_current_user)):
    """Change the current authenticated user's password.

    Args:
        req: Current and new password payload.
        user: Authenticated AJIN user context.

    Returns:
        dict[str, bool | str]: Change confirmation and must-change state.

    Raises:
        HTTPException: If authentication, current password, strength, or history validation fails.
    """
    from core.auth.database import get_auth_db
    from core.auth.password import hash_password, validate_password_change, verify_password

    employee_id = getattr(user, "employee_id", "")
    if not employee_id:
        raise HTTPException(status_code=401, detail="인증이 필요합니다.")
    if _is_guest(user):
        raise HTTPException(status_code=403, detail="게스트는 읽기 전용입니다.")

    conn = get_auth_db()
    db_user = conn.execute("SELECT * FROM users WHERE employee_id = ?", (employee_id,)).fetchone()

    if not db_user:
        conn.close()
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    if not verify_password(req.current_password, db_user["password_hash"]):
        conn.close()
        raise HTTPException(status_code=401, detail="현재 비밀번호가 올바르지 않습니다.")

    history_rows = conn.execute(
        "SELECT password_hash FROM password_history WHERE user_id = ? ORDER BY changed_at DESC, id DESC LIMIT 5",
        (db_user["user_id"],),
    ).fetchall()
    recent_hashes = tuple(str(row["password_hash"]) for row in history_rows)
    ok, message = validate_password_change(
        req.new_password,
        current_password_hash=db_user["password_hash"],
        previous_password_hashes=recent_hashes,
        employee_id=employee_id,
        username=db_user["username"],
    )
    if not ok:
        conn.close()
        raise HTTPException(status_code=400, detail=message)

    new_hash = hash_password(req.new_password)

    try:
        # Store the previous hash, not the newly issued hash.
        conn.execute(
            "INSERT INTO password_history (user_id, password_hash) VALUES (?, ?)",
            (db_user["user_id"], db_user["password_hash"]),
        )

        # 비밀번호 업데이트 + must_change_pw 해제
        conn.execute(
            "UPDATE users SET password_hash = ?, must_change_pw = 0, failed_attempts = 0, locked_until = NULL, updated_at = datetime('now') WHERE user_id = ?",
            (new_hash, db_user["user_id"]),
        )
        _persist_password_change_to_postgres(
            employee_id=employee_id,
            old_password_hash=db_user["password_hash"],
            new_password_hash=new_hash,
        )
        conn.commit()
    except RuntimeError:
        conn.rollback()
        logger.exception("Password change persistence failed for employee_id=%s", employee_id)
        raise HTTPException(status_code=503, detail="비밀번호 저장소 동기화에 실패했습니다. 잠시 후 다시 시도하세요.")
    finally:
        conn.close()

    return {"message": "비밀번호가 변경되었습니다.", "must_change_pw": False}


@router.post("/refresh", response_model=LoginResponse)
async def refresh_token(request: Request, response: Response):
    """Refresh the browser session from the HttpOnly refresh cookie."""
    from core.auth.cookies import refresh_token_from_request, set_auth_cookies
    from core.auth.database import get_auth_db
    from core.auth.jwt_handler import create_access_token, verify_token
    from core.auth.refresh_sessions import refresh_session_is_active, rotate_refresh_session

    current_refresh = refresh_token_from_request(request)
    if not current_refresh:
        raise HTTPException(status_code=401, detail="리프레시 쿠키가 없습니다.")

    payload = verify_token(current_refresh)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="유효하지 않은 리프레시 토큰입니다.")
    if not refresh_session_is_active(current_refresh):
        raise HTTPException(status_code=401, detail="리프레시 토큰이 폐기되었거나 재사용되었습니다.")

    employee_id = payload["sub"]

    # 게스트(쇼케이스)는 DB user row 가 없으므로 토큰 컨텍스트로 재발급한다
    # (/auth/guest·/auth/me 와 동일 패턴). 이 분기가 없으면 아래 DB 조회가 None →
    # 401 → 프론트가 게스트 세션을 잃고 모든 쇼케이스 패널이 /login 으로 튕긴다.
    if employee_id == GUEST_EMPLOYEE_ID:
        if _guest_disabled():
            raise HTTPException(status_code=404, detail="게스트 미리보기가 비활성화되어 있습니다.")
        guest = _guest_user_dict()
        new_access = create_access_token(
            employee_id=guest["employee_id"],
            username=guest["username"],
            role_name=guest["role_name"],
            role_level=guest["role_level"],
            expires_hours=8,
        )
        new_refresh = rotate_refresh_session(current_refresh, guest["employee_id"])
        set_auth_cookies(response, new_access, new_refresh)
        return _login_response_from_user(guest)

    conn = get_auth_db()
    user = conn.execute(
        """SELECT u.*, r.role_name, r.role_level
           FROM users u JOIN roles r ON u.role_id = r.role_id
           WHERE u.employee_id = ?""",
        (employee_id,),
    ).fetchone()
    conn.close()

    if not user or not user["is_active"]:
        raise HTTPException(status_code=401, detail="계정이 비활성 상태입니다.")

    new_access = create_access_token(
        employee_id=user["employee_id"],
        username=user["username"],
        role_name=user["role_name"],
        role_level=user["role_level"],
    )
    new_refresh = rotate_refresh_session(current_refresh, user["employee_id"])
    set_auth_cookies(response, new_access, new_refresh)

    return _login_response_from_user(user)


@router.post("/logout", include_in_schema=False)
async def logout(request: Request, response: Response) -> dict[str, bool]:
    """Clear browser auth cookies and revoke the current refresh token.

    Args:
        request: Incoming request containing the refresh cookie when logged in.
        response: Response mutated with cookie deletion headers.

    Returns:
        dict[str, bool]: Stateless logout acknowledgement.
    """

    from core.auth.cookies import clear_auth_cookies, refresh_token_from_request
    from core.auth.refresh_sessions import revoke_refresh_session

    revoke_refresh_session(refresh_token_from_request(request))
    clear_auth_cookies(response)
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════
# 본인 프로필 — GET /me, PUT /me, GET /me/login-history
# ═══════════════════════════════════════════════════════════════

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
# 휴대폰 (010-XXXX-XXXX) + 일반 전화 (02-XXX-XXXX, 053-XXX-XXXX 등) 모두 허용
_PHONE_RE = re.compile(r"^0\d{1,2}-?\d{3,4}-?\d{4}$")


@router.get("/me", response_model=ProfileResponse)
async def get_me(user=Depends(get_current_user)) -> ProfileResponse:
    """본인 프로필 — auth.db users + roles JOIN. 토큰의 employee_id 기준."""
    from core.auth.database import get_auth_db

    employee_id = getattr(user, "employee_id", None)
    if not employee_id:
        raise HTTPException(status_code=401, detail="토큰에서 사번을 추출할 수 없습니다.")

    # 게스트(읽기 전용) — DB row 가 없으므로 토큰 컨텍스트로 합성 프로필 반환.
    if _is_guest(user):
        return ProfileResponse(
            employee_id=GUEST_EMPLOYEE_ID,
            username="게스트 (읽기 전용)",
            role_name="GUEST",
            role_level=GUEST_ROLE_LEVEL,
            department="체험",
            position="Showcase Guest",
            email="",
            phone="",
            hire_date="",
            last_login=None,
            created_at=None,
            updated_at=None,
            is_active=True,
            must_change_pw=False,
            photo_url="",
        )

    conn = get_auth_db()
    try:
        row = conn.execute(
            """SELECT u.*, r.role_name, r.role_level
               FROM users u JOIN roles r ON u.role_id = r.role_id
               WHERE u.employee_id = ?""",
            (employee_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="사용자 정보를 찾을 수 없습니다.")

    # photo_url 컬럼은 alembic 20260526_0003 또는 ensure_schema 로 추가됨 — 안전한 접근
    try:
        photo_url_value = row["photo_url"] or ""
    except (KeyError, IndexError):
        photo_url_value = ""

    return ProfileResponse(
        employee_id=row["employee_id"],
        username=row["username"],
        role_name=row["role_name"],
        role_level=row["role_level"],
        department=row["department"] or "",
        position=row["position"] or "",
        email=row["email"] or "",
        phone=row["phone"] or "",
        hire_date=row["hire_date"] or "",
        last_login=row["last_login"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        is_active=bool(row["is_active"]),
        must_change_pw=bool(row["must_change_pw"]),
        photo_url=photo_url_value,
    )


# ─────────────────────────────────────────────────────────────
# PATCH /me/photo — 디지털 사원증 사진 변경 (base64 data URL 인라인 저장)
# 추후 Supabase Storage signed-upload 로 마이그레이션 시 storage 호출만 swap.
# ─────────────────────────────────────────────────────────────


@router.patch("/me/photo", response_model=ProfileResponse)
async def update_my_photo(
    req: PhotoUpdateRequest,
    user=Depends(get_current_user),
) -> ProfileResponse:
    """본인 디지털 사원증 사진 변경."""
    from core.auth.database import get_auth_db

    employee_id = getattr(user, "employee_id", None)
    if not employee_id:
        raise HTTPException(status_code=401, detail="토큰에서 사번을 추출할 수 없습니다.")

    if not req.photo_data_url.startswith("data:image/"):
        raise HTTPException(
            status_code=400,
            detail="photo_data_url 은 'data:image/*;base64,...' 형식이어야 합니다.",
        )

    conn = get_auth_db()
    try:
        now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with conn:
            conn.execute(
                "UPDATE users SET photo_url = ?, updated_at = ? WHERE employee_id = ?",
                (req.photo_data_url, now_iso, employee_id),
            )
        row = conn.execute(
            """SELECT u.*, r.role_name, r.role_level
               FROM users u JOIN roles r ON u.role_id = r.role_id
               WHERE u.employee_id = ?""",
            (employee_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="사용자 정보를 찾을 수 없습니다.")

    try:
        photo_url_value = row["photo_url"] or ""
    except (KeyError, IndexError):
        photo_url_value = req.photo_data_url

    return ProfileResponse(
        employee_id=row["employee_id"],
        username=row["username"],
        role_name=row["role_name"],
        role_level=row["role_level"],
        department=row["department"] or "",
        position=row["position"] or "",
        email=row["email"] or "",
        phone=row["phone"] or "",
        hire_date=row["hire_date"] or "",
        last_login=row["last_login"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        is_active=bool(row["is_active"]),
        must_change_pw=bool(row["must_change_pw"]),
        photo_url=photo_url_value,
    )


_EMP_ID_RE = re.compile(r"^[A-Za-z0-9_-]{3,20}$")
_VALID_ROLE_NAMES = {"INACTIVE", "EMPLOYEE", "MANAGER", "TEAM_LEAD", "HR_ADMIN", "SYS_ADMIN"}
# UserContext 에 role_level 필드가 없으므로 role(name) → level 매핑
_ROLE_LEVEL_MAP = {
    "INACTIVE": 0, "EMPLOYEE": 1, "MANAGER": 2,
    "TEAM_LEAD": 3, "HR_ADMIN": 4, "SYS_ADMIN": 5,
}


@router.put("/me", response_model=ProfileUpdateResponse)
async def update_me(
    req: ProfileUpdateRequest,
    user=Depends(get_current_user),
) -> ProfileUpdateResponse:
    """본인 정보 수정.

    화이트리스트:
      모든 사용자: email, phone, position
      HR_ADMIN(Lv4)+:  + employee_id, username, department, role_name

    사번/역할 변경 시 ``reissued=True`` 플래그 → 프론트가 강제 로그아웃.
    """
    import os
    from core.auth.database import get_auth_db

    current_emp_id = getattr(user, "employee_id", None)
    if not current_emp_id:
        raise HTTPException(status_code=401, detail="토큰에서 사번을 추출할 수 없습니다.")
    if _is_guest(user):
        raise HTTPException(status_code=403, detail="게스트는 읽기 전용입니다.")
    role_level = _ROLE_LEVEL_MAP.get(getattr(user, "role", "") or "", 1)

    privileged = role_level >= 4

    # ── 1) 일반 화이트리스트 ──
    updates: dict[str, str] = {}
    if req.email is not None:
        e = req.email.strip()
        if e and not _EMAIL_RE.match(e):
            raise HTTPException(status_code=400, detail="이메일 형식이 올바르지 않습니다.")
        updates["email"] = e
    if req.phone is not None:
        p = req.phone.strip()
        if p and not _PHONE_RE.match(p):
            raise HTTPException(status_code=400, detail="전화번호 형식: 010-XXXX-XXXX 또는 053-XXX-XXXX")
        updates["phone"] = p
    if req.position is not None:
        pos = req.position.strip()
        if len(pos) > 50:
            raise HTTPException(status_code=400, detail="직급은 50자 이하여야 합니다.")
        updates["position"] = pos

    # ── 2) 특권 화이트리스트 (HR_ADMIN/SYS_ADMIN) ──
    new_emp_id: str | None = None
    new_role_name: str | None = None

    if req.username is not None:
        if not privileged:
            raise HTTPException(status_code=403, detail="이름 변경은 인사·시스템 관리자만 가능합니다.")
        n = req.username.strip()
        if not n or len(n) > 100:
            raise HTTPException(status_code=400, detail="이름은 1~100자여야 합니다.")
        updates["username"] = n

    if req.department is not None:
        if not privileged:
            raise HTTPException(status_code=403, detail="부서 변경은 인사·시스템 관리자만 가능합니다.")
        d = req.department.strip()
        if len(d) > 100:
            raise HTTPException(status_code=400, detail="부서명은 100자 이하여야 합니다.")
        updates["department"] = d

    if req.employee_id is not None:
        if not privileged:
            raise HTTPException(status_code=403, detail="사번 변경은 인사·시스템 관리자만 가능합니다.")
        new_emp_id = req.employee_id.strip()
        if not _EMP_ID_RE.match(new_emp_id):
            raise HTTPException(status_code=400, detail="사번은 영문/숫자/-/_ 3~20자만 허용됩니다.")
        # 동일 사번이면 변경으로 간주하지 않음
        if new_emp_id == current_emp_id:
            new_emp_id = None

    if req.role_name is not None:
        if not privileged:
            raise HTTPException(status_code=403, detail="역할 변경은 인사·시스템 관리자만 가능합니다.")
        r = req.role_name.strip().upper()
        if r not in _VALID_ROLE_NAMES:
            raise HTTPException(status_code=400, detail=f"역할은 {sorted(_VALID_ROLE_NAMES)} 중 하나.")
        new_role_name = r

    # 변경 없음 → 현재 프로필 그대로 반환
    if not updates and new_emp_id is None and new_role_name is None:
        prof = await get_me(user)  # type: ignore[arg-type]
        return ProfileUpdateResponse(profile=prof, reissued=False)

    reissued = False  # 사번/역할 변경 시 True

    conn = get_auth_db()
    try:
        # ── 3) 역할 변경 처리 ──
        if new_role_name:
            target_role = conn.execute(
                "SELECT role_id, role_name FROM roles WHERE role_name = ?",
                (new_role_name,),
            ).fetchone()
            if not target_role:
                raise HTTPException(status_code=400, detail=f"존재하지 않는 역할: {new_role_name}")

            current_role = conn.execute(
                """SELECT r.role_name FROM users u JOIN roles r ON u.role_id = r.role_id
                   WHERE u.employee_id = ?""",
                (current_emp_id,),
            ).fetchone()

            # 본인이 마지막 SYS_ADMIN 인데 강등하려는 경우 차단
            if current_role and current_role["role_name"] == "SYS_ADMIN" and new_role_name != "SYS_ADMIN":
                cnt = conn.execute(
                    """SELECT COUNT(*) FROM users u JOIN roles r ON u.role_id = r.role_id
                       WHERE r.role_name = 'SYS_ADMIN' AND u.is_active = 1"""
                ).fetchone()[0]
                if cnt <= 1:
                    raise HTTPException(
                        status_code=400,
                        detail="마지막 시스템 관리자는 본인 역할을 강등할 수 없습니다. 다른 SYS_ADMIN을 먼저 임명하세요.",
                    )

            updates["role_id"] = str(target_role["role_id"])  # 다음 SET 절에 포함
            reissued = True

        # ── 4) 사번 변경 처리 (UNIQUE 검사) ──
        rename_emp = False
        if new_emp_id:
            taken = conn.execute(
                "SELECT 1 FROM users WHERE employee_id = ? AND employee_id != ?",
                (new_emp_id, current_emp_id),
            ).fetchone()
            if taken:
                raise HTTPException(status_code=409, detail=f"이미 사용 중인 사번: {new_emp_id}")
            rename_emp = True
            reissued = True

        # ── 5) UPDATE 쿼리 빌드 ──
        set_parts: list[str] = []
        params: list[object] = []
        for k, v in updates.items():
            set_parts.append(f"{k} = ?")
            params.append(int(v) if k == "role_id" else v)

        if rename_emp:
            set_parts.append("employee_id = ?")
            params.append(new_emp_id)

        set_parts.append("updated_at = ?")
        params.append(datetime.now(timezone.utc).isoformat())
        params.append(current_emp_id)  # WHERE

        conn.execute(
            f"UPDATE users SET {', '.join(set_parts)} WHERE employee_id = ?",
            params,
        )

        # 사번 변경 시 login_history 도 새 사번으로 (FK 는 user_id 기준이라 OK, employee_id 컬럼만 덮어씀)
        if rename_emp:
            conn.execute(
                "UPDATE login_history SET employee_id = ? WHERE employee_id = ?",
                (new_emp_id, current_emp_id),
            )
        conn.commit()
    finally:
        conn.close()

    # ── 6) Firestore 동기화 ──
    if os.environ.get("AUTH_BACKEND", "").lower() == "firestore":
        try:
            from google.cloud import firestore  # type: ignore
            db = firestore.Client()
            now_iso = datetime.now(timezone.utc).isoformat()

            # 사번 변경 시 doc id 가 바뀌므로 옛 doc 삭제 + 새 doc 생성
            if new_emp_id:
                old_doc = db.collection("auth_users").document(current_emp_id).get()
                old_data = old_doc.to_dict() if old_doc.exists else {}
                merged = {
                    **old_data,
                    **{k: (int(v) if k == "role_id" else v) for k, v in updates.items()},
                    "employee_id": new_emp_id,
                    "updated_at": now_iso,
                }
                if new_role_name:
                    merged["role_name"] = new_role_name
                db.collection("auth_users").document(new_emp_id).set(merged)
                db.collection("auth_users").document(current_emp_id).delete()
            else:
                payload: dict[str, object] = {
                    **{k: (int(v) if k == "role_id" else v) for k, v in updates.items()},
                    "updated_at": now_iso,
                }
                if new_role_name:
                    payload["role_name"] = new_role_name
                db.collection("auth_users").document(current_emp_id).set(payload, merge=True)
        except Exception as e:  # pragma: no cover
            logger.warning("Firestore 동기화 실패 (SQLite 만 update됨): %s", e)

    # ── 7) 응답 반환 ──
    # 사번/역할 변경 시 토큰 sub 또는 role 이 stale → 다시 조회 시 token sub (current_emp_id) 가
    # auth.db 에 더 이상 존재하지 않을 수 있어 GET /me 가 404. 직접 조회로 응답 구성.
    target_emp = new_emp_id or current_emp_id
    conn = get_auth_db()
    try:
        row = conn.execute(
            """SELECT u.*, r.role_name, r.role_level
               FROM users u JOIN roles r ON u.role_id = r.role_id
               WHERE u.employee_id = ?""",
            (target_emp,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=500, detail="갱신 후 프로필 조회 실패")

    profile = ProfileResponse(
        employee_id=row["employee_id"],
        username=row["username"],
        role_name=row["role_name"],
        role_level=row["role_level"],
        department=row["department"] or "",
        position=row["position"] or "",
        email=row["email"] or "",
        phone=row["phone"] or "",
        hire_date=row["hire_date"] or "",
        last_login=row["last_login"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        is_active=bool(row["is_active"]),
        must_change_pw=bool(row["must_change_pw"]),
    )
    return ProfileUpdateResponse(profile=profile, reissued=reissued)


@router.get("/me/login-history", response_model=LoginHistoryResponse)
async def get_my_login_history(
    limit: int = 20,
    user=Depends(get_current_user),
) -> LoginHistoryResponse:
    """본인 로그인 이력 — login_history 테이블에서 최신순 limit건."""
    from core.auth.database import get_auth_db

    employee_id = getattr(user, "employee_id", None)
    if not employee_id:
        raise HTTPException(status_code=401, detail="토큰에서 사번을 추출할 수 없습니다.")

    limit = max(1, min(int(limit), 100))

    conn = get_auth_db()
    try:
        rows = conn.execute(
            """SELECT id, action, success, ip_address, user_agent, timestamp
               FROM login_history
               WHERE employee_id = ?
               ORDER BY id DESC
               LIMIT ?""",
            (employee_id, limit),
        ).fetchall()
    finally:
        conn.close()

    history = [
        LoginHistoryEntry(
            id=int(r["id"]),
            action=r["action"] or "login",
            success=bool(r["success"]),
            ip_address=r["ip_address"] or "",
            user_agent=r["user_agent"] or "",
            timestamp=r["timestamp"] or "",
        )
        for r in rows
    ]

    return LoginHistoryResponse(
        employee_id=employee_id,
        total=len(history),
        history=history,
    )


# ═══════════════════════════════════════════════════════════════
# v4.7 Feature E Phase 2 — 2FA (TOTP) endpoints
# ═══════════════════════════════════════════════════════════════


class TwoFactorEnrollResponse(BaseModel):
    secret_b32: str
    otpauth_url: str
    backup_codes: list[str]
    issuer: str


class TwoFactorConfirmRequest(BaseModel):
    code: str


class TwoFactorVerifyRequest(BaseModel):
    mid_token: str
    code: str


class TwoFactorBackupRegenRequest(BaseModel):
    password: str


@router.get("/2fa/status")
async def two_factor_status(user=Depends(get_current_user)):
    """내 2FA 활성 여부 확인."""
    from features.admin import totp

    employee_id = getattr(user, "employee_id", None)
    if not employee_id:
        raise HTTPException(status_code=401, detail="인증 필요")
    return {"enabled": totp.is_enabled(employee_id)}


@router.post("/2fa/enroll", response_model=TwoFactorEnrollResponse)
async def two_factor_enroll(user=Depends(get_current_user)) -> TwoFactorEnrollResponse:
    """2FA enroll — 시크릿/백업코드 생성 후 QR URL 반환. confirm 필요."""
    from features.admin import totp

    employee_id = getattr(user, "employee_id", None)
    if not employee_id:
        raise HTTPException(status_code=401, detail="인증 필요")
    try:
        result = totp.enroll_user(employee_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return TwoFactorEnrollResponse(**result)  # type: ignore[arg-type]


@router.post("/2fa/confirm")
async def two_factor_confirm(req: TwoFactorConfirmRequest, user=Depends(get_current_user)):
    """enroll 직후 사용자의 6자리 코드로 enrollment 확정."""
    from features.admin import totp

    employee_id = getattr(user, "employee_id", None)
    if not employee_id:
        raise HTTPException(status_code=401, detail="인증 필요")
    try:
        ok = totp.confirm_enrollment(employee_id, req.code.strip())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not ok:
        raise HTTPException(status_code=400, detail="코드가 일치하지 않습니다.")
    return {"enabled": True}


@router.post("/2fa/verify", response_model=LoginResponse)
async def two_factor_verify(req: TwoFactorVerifyRequest, request: Request, response: Response) -> LoginResponse:
    """로그인 1차 통과 후 mid_token + 6자리 코드(또는 백업코드)로 최종 세션 발급."""
    from core.auth.database import get_auth_db
    from core.auth.jwt_handler import verify_token
    from features.admin import totp

    payload = verify_token(req.mid_token)
    if not payload or payload.get("type") != "mid" or not payload.get("mid"):
        raise HTTPException(status_code=401, detail="mid_token 무효 또는 만료")

    employee_id = payload.get("sub")
    if not employee_id:
        raise HTTPException(status_code=401, detail="mid_token sub 누락")

    if not totp.verify_code(employee_id, req.code.strip()):
        raise HTTPException(status_code=401, detail="2FA 코드가 올바르지 않습니다.")

    conn = get_auth_db()
    try:
        user = conn.execute(
            """SELECT u.*, r.role_name, r.role_level
               FROM users u JOIN roles r ON u.role_id = r.role_id
               WHERE u.employee_id = ?""",
            (employee_id,),
        ).fetchone()
    finally:
        conn.close()
    if not user or not user["is_active"]:
        raise HTTPException(status_code=403, detail="비활성 계정")

    # 감사 — 2FA 성공
    _ip = request.client.host if request and request.client else ""
    _ua = request.headers.get("user-agent", "") if request else ""
    try:
        emit_login_event(
            user_id=user["user_id"],
            employee_id=user["employee_id"],
            success=True,
            ip_address=_ip,
            user_agent=_ua,
            department=user["department"] if "department" in user.keys() else "",
            role_level=user["role_level"],
            extra={"twofa": "ok"},
        )
    except Exception:
        pass

    _issue_browser_session(response, user)
    return _login_response_from_user(user)


@router.post("/2fa/backup-regen")
async def two_factor_backup_regen(
    req: TwoFactorBackupRegenRequest,
    user=Depends(get_current_user),
):
    """백업 코드 재발급 — 비밀번호 재확인 필수."""
    from core.auth.database import get_auth_db
    from core.auth.password import verify_password
    from features.admin import totp

    employee_id = getattr(user, "employee_id", None)
    if not employee_id:
        raise HTTPException(status_code=401, detail="인증 필요")

    conn = get_auth_db()
    try:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE employee_id = ?", (employee_id,)
        ).fetchone()
    finally:
        conn.close()
    if not row or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다.")

    codes = totp.regenerate_backup_codes(employee_id)
    return {"backup_codes": codes}


@router.post("/2fa/disable")
async def two_factor_disable(
    req: TwoFactorBackupRegenRequest,
    user=Depends(get_current_user),
):
    """2FA 비활성화 — 비밀번호 재확인 필수."""
    from core.auth.database import get_auth_db
    from core.auth.password import verify_password
    from features.admin import totp

    employee_id = getattr(user, "employee_id", None)
    if not employee_id:
        raise HTTPException(status_code=401, detail="인증 필요")
    conn = get_auth_db()
    try:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE employee_id = ?", (employee_id,)
        ).fetchone()
    finally:
        conn.close()
    if not row or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다.")
    totp.disable_2fa(employee_id)
    return {"enabled": False}


@router.post("/admin/sync-from-postgres", include_in_schema=False)
def trigger_postgres_sync(
    x_sync_token: str | None = Header(default=None, alias="X-Sync-Token"),
):
    """Admin emergency endpoint — Postgres → SQLite mirror sync 강제 재실행.

    Use case:
        Supabase Postgres 의 users 테이블에 직접 INSERT/UPDATE (예: SUPER-9999
        admin recovery) 한 후, Cloud Run instance 의 SQLite mirror 가 startup
        시점의 stale 상태에 머물 때 사용. instance warm pool 재사용으로 자동
        sync 가 안 일어나는 architecture limitation 보완.

    Auth:
        env ``AJIN_SYNC_TOKEN`` 과 ``X-Sync-Token`` header 가 hmac.compare_digest
        로 일치해야 함. 미설정 시 503.

    Returns:
        {"ok": True, "synced_rows": int} — Postgres 에서 mirror 한 row 수.
    """

    import hmac
    import os

    expected = os.environ.get("AJIN_SYNC_TOKEN", "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="sync endpoint disabled (AJIN_SYNC_TOKEN env 미설정)",
        )
    if not x_sync_token or not hmac.compare_digest(x_sync_token, expected):
        raise HTTPException(status_code=403, detail="invalid sync token")

    from core.auth.database import _sync_from_postgres_if_enabled

    count = _sync_from_postgres_if_enabled()
    return {"ok": True, "synced_rows": count}
