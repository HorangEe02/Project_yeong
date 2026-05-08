"""백엔드 인증 미들웨어 — JWT → UserContext 복원 + 감사 로깅

JWT 토큰에서 사용자 정보를 추출하여 UserContext를 생성하고,
API 호출 이력을 audit.db에 기록한다.

공개 엔드포인트: /api/health, /api/auth/login, /api/auth/refresh, /
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

AUDIT_DB_PATH = Path("data/audit.db")

# 인증 불필요 경로
PUBLIC_PATHS = frozenset({
    "/",
    "/docs",
    "/openapi.json",
    "/api/health",
    "/api/auth/login",
    "/api/auth/refresh",
    "/api/auth/firebase-exchange",
})


def _is_public_path(path: str) -> bool:
    """공개 엔드포인트인지 확인"""
    return path in PUBLIC_PATHS or path.startswith("/docs") or path.startswith("/openapi")


# ═══════════════════════════════════════════════════════════
# JWT → UserContext 복원
# ═══════════════════════════════════════════════════════════

def extract_user_from_token(token: str):
    """JWT 토큰에서 UserContext를 복원한다.

    Returns:
        UserContext 또는 None (토큰 무효 시)
    """
    from core.auth.jwt_handler import verify_token
    from core.auth.user_context import UserContext

    payload = verify_token(token)
    if not payload:
        return None

    if payload.get("type") != "access":
        return None

    employee_id = payload.get("sub", "")
    role_name = payload.get("role", "EMPLOYEE")
    role_level = payload.get("role_level", 1)

    # auth.db에서 추가 정보 조회
    department = ""
    position = ""
    name = ""
    division = ""
    user_id = 0

    try:
        from core.auth.database import get_auth_db
        conn = get_auth_db()
        row = conn.execute(
            """SELECT u.user_id, u.department, u.position, u.username
               FROM users u
               WHERE u.employee_id = ? AND u.is_active = 1""",
            (employee_id,),
        ).fetchone()
        conn.close()

        if row:
            user_id = row["user_id"]
            department = row["department"] or ""
            position = row["position"] or ""
            name = row["username"] or payload.get("username", "")

            # 부서→본부 매핑
            try:
                from core.auth.user_context import DEPARTMENT_TO_DIVISION
                division = DEPARTMENT_TO_DIVISION.get(department, "")
            except ImportError:
                pass
    except Exception as e:
        logger.warning(f"사용자 정보 DB 조회 실패: {e}")
        name = payload.get("username", "")

    return UserContext(
        user_id=user_id,
        employee_id=employee_id,
        name=name,
        department=department,
        division=division,
        position=position,
        role=role_name,
    )


def extract_token_from_header(authorization: str) -> Optional[str]:
    """Authorization 헤더에서 Bearer 토큰을 추출한다."""
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


# ═══════════════════════════════════════════════════════════
# 감사 로깅
# ═══════════════════════════════════════════════════════════

def init_audit_db(db_path: Path = AUDIT_DB_PATH) -> None:
    """감사 로그 DB 초기화"""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS api_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT DEFAULT '',
            name TEXT DEFAULT '',
            department TEXT DEFAULT '',
            role TEXT DEFAULT '',
            endpoint TEXT NOT NULL,
            method TEXT NOT NULL DEFAULT 'GET',
            status_code INTEGER DEFAULT 200,
            detail TEXT DEFAULT '',
            ip_address TEXT DEFAULT '',
            timestamp TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_audit_employee
        ON api_audit_log(employee_id, timestamp DESC);

        CREATE INDEX IF NOT EXISTS idx_audit_endpoint
        ON api_audit_log(endpoint, timestamp DESC);
    """)
    conn.commit()
    conn.close()


def log_api_access(
    endpoint: str,
    method: str = "GET",
    status_code: int = 200,
    detail: str = "",
    ip_address: str = "",
    user=None,
    db_path: Path = AUDIT_DB_PATH,
) -> None:
    """API 호출을 감사 로그에 기록한다."""
    try:
        init_audit_db(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            """INSERT INTO api_audit_log
               (employee_id, name, department, role, endpoint, method, status_code, detail, ip_address)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                getattr(user, 'employee_id', '') if user else '',
                getattr(user, 'name', '') if user else '',
                getattr(user, 'department', '') if user else '',
                getattr(user, 'role', '') if user else '',
                endpoint,
                method,
                status_code,
                detail,
                ip_address,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"감사 로그 기록 실패: {e}")


def get_audit_logs(
    employee_id: str = "",
    endpoint: str = "",
    limit: int = 50,
    db_path: Path = AUDIT_DB_PATH,
) -> list[dict]:
    """감사 로그를 조회한다."""
    init_audit_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    conditions = []
    params = []
    if employee_id:
        conditions.append("employee_id = ?")
        params.append(employee_id)
    if endpoint:
        conditions.append("endpoint LIKE ?")
        params.append(f"%{endpoint}%")

    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    rows = conn.execute(
        f"SELECT * FROM api_audit_log{where} ORDER BY timestamp DESC LIMIT ?",
        params + [limit],
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_audit_stats(db_path: Path = AUDIT_DB_PATH) -> dict:
    """감사 로그 통계"""
    init_audit_db(db_path)
    conn = sqlite3.connect(str(db_path))
    total = conn.execute("SELECT COUNT(*) FROM api_audit_log").fetchone()[0]
    by_endpoint = conn.execute(
        "SELECT endpoint, COUNT(*) as cnt FROM api_audit_log GROUP BY endpoint ORDER BY cnt DESC LIMIT 10"
    ).fetchall()
    conn.close()
    return {
        "total": total,
        "top_endpoints": {r[0]: r[1] for r in by_endpoint},
    }
