"""인증 API 라우터 — 로그인, 비밀번호 변경, 토큰 갱신, Firebase 교환"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    employee_id: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    employee_id: str
    username: str
    role_name: str
    role_level: int
    must_change_pw: bool = False
    department: str = ""
    position: str = ""


class ChangePasswordRequest(BaseModel):
    employee_id: str
    current_password: str
    new_password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class FirebaseExchangeRequest(BaseModel):
    """Frontend axios interceptor 가 access_token 만료 시 호출.

    Firebase Web SDK ``user.getIdToken(true)`` 결과를 그대로 전달한다.
    """
    id_token: str


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


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """사원번호 + 비밀번호로 로그인"""
    from core.auth.database import get_auth_db
    from core.auth.password import verify_password
    from core.auth.jwt_handler import create_access_token, create_refresh_token

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

        # 로그인 실패 이력
        conn.execute(
            "INSERT INTO login_history (user_id, employee_id, action, success) VALUES (?, ?, 'login', 0)",
            (user["user_id"], req.employee_id),
        )
        conn.commit()
        conn.close()
        raise HTTPException(status_code=401, detail=f"비밀번호가 올바르지 않습니다. ({new_attempts}/5)")

    # 로그인 성공 — 실패 횟수 리셋
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE users SET failed_attempts = 0, locked_until = NULL, last_login = ? WHERE user_id = ?",
        (now, user["user_id"]),
    )
    conn.execute(
        "INSERT INTO login_history (user_id, employee_id, action, success) VALUES (?, ?, 'login', 1)",
        (user["user_id"], req.employee_id),
    )
    conn.commit()
    conn.close()

    # 토큰 생성
    access_token = create_access_token(
        employee_id=user["employee_id"],
        username=user["username"],
        role_name=user["role_name"],
        role_level=user["role_level"],
    )
    refresh_token = create_refresh_token(user["employee_id"])

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        employee_id=user["employee_id"],
        username=user["username"],
        role_name=user["role_name"],
        role_level=user["role_level"],
        must_change_pw=bool(user["must_change_pw"]),
    )


@router.post("/change-password")
async def change_password(req: ChangePasswordRequest):
    """비밀번호 변경"""
    from core.auth.database import get_auth_db
    from core.auth.password import verify_password, hash_password

    conn = get_auth_db()
    user = conn.execute("SELECT * FROM users WHERE employee_id = ?", (req.employee_id,)).fetchone()

    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    if not verify_password(req.current_password, user["password_hash"]):
        conn.close()
        raise HTTPException(status_code=401, detail="현재 비밀번호가 올바르지 않습니다.")

    if len(req.new_password) < 6:
        conn.close()
        raise HTTPException(status_code=400, detail="새 비밀번호는 6자 이상이어야 합니다.")

    new_hash = hash_password(req.new_password)

    # 비밀번호 이력 저장
    conn.execute("INSERT INTO password_history (user_id, password_hash) VALUES (?, ?)",
                (user["user_id"], user["password_hash"]))

    # 비밀번호 업데이트 + must_change_pw 해제
    conn.execute(
        "UPDATE users SET password_hash = ?, must_change_pw = 0, updated_at = datetime('now') WHERE user_id = ?",
        (new_hash, user["user_id"]),
    )
    conn.commit()
    conn.close()

    return {"message": "비밀번호가 변경되었습니다.", "must_change_pw": False}


@router.post("/refresh")
async def refresh_token(req: RefreshRequest):
    """리프레시 토큰으로 새 액세스 토큰 발급"""
    from core.auth.jwt_handler import verify_token, create_access_token
    from core.auth.database import get_auth_db

    payload = verify_token(req.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="유효하지 않은 리프레시 토큰입니다.")

    employee_id = payload["sub"]
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

    new_token = create_access_token(
        employee_id=user["employee_id"],
        username=user["username"],
        role_name=user["role_name"],
        role_level=user["role_level"],
    )

    return {"access_token": new_token, "token_type": "bearer"}


@router.post("/firebase-exchange", response_model=LoginResponse)
async def firebase_exchange(req: FirebaseExchangeRequest) -> LoginResponse:
    """Firebase ID Token → 백엔드 JWT 교환 (Day 5++.5).

    Frontend axios interceptor 가 access_token 만료 시 자동 호출하여
    silent re-authentication 을 수행한다.

    매핑: Firebase email ``{employee_id.lower()}@ajin.local`` → ``employee_id`` 역추적.
    """
    from backend.auth.firebase_verify import verify_firebase_id_token
    from core.auth.database import get_auth_db
    from core.auth.jwt_handler import create_access_token, create_refresh_token

    # 1) Firebase ID Token 검증
    try:
        decoded = verify_firebase_id_token(req.id_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Firebase 토큰 검증 실패: {e}") from e
    except Exception as e:  # pragma: no cover
        logger.exception("Firebase 토큰 검증 중 예외")
        raise HTTPException(status_code=401, detail=f"Firebase 인증 오류: {e}") from e

    # 2) email → employee_id 역추적
    email = (decoded.get("email") or "").strip().lower()
    if not email or not email.endswith("@ajin.local"):
        raise HTTPException(
            status_code=403,
            detail="지원하지 않는 이메일 도메인입니다. (@ajin.local 만 허용)",
        )
    employee_id = email[: -len("@ajin.local")].upper()
    if not employee_id:
        raise HTTPException(status_code=400, detail="유효하지 않은 사번 매핑")

    # 3) 사용자 정보 조회 (auth.db)
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

    if not user:
        raise HTTPException(status_code=404, detail=f"사용자를 찾을 수 없습니다: {employee_id}")
    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="비활성화된 계정입니다.")

    # 4) JWT 발급 (기존 login 동일 패턴)
    access_token = create_access_token(
        employee_id=user["employee_id"],
        username=user["username"],
        role_name=user["role_name"],
        role_level=user["role_level"],
    )
    refresh_tok = create_refresh_token(user["employee_id"])

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_tok,
        employee_id=user["employee_id"],
        username=user["username"],
        role_name=user["role_name"],
        role_level=user["role_level"],
        must_change_pw=bool(user["must_change_pw"]),
        department=(user["department"] or "") if "department" in user.keys() else "",
        position=(user["position"] or "") if "position" in user.keys() else "",
    )


# ═══════════════════════════════════════════════════════════════
# 본인 프로필 — GET /me, PUT /me, GET /me/login-history
# ═══════════════════════════════════════════════════════════════

import re
from fastapi import Depends
from backend.dependencies import get_current_user

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
