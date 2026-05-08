"""인증 데이터베이스 (auth.db) — 사용자/역할/로그인 이력 관리

employees.db(기존, 읽기전용)와 분리된 별도 DB.
employee_id를 외래키로 연결.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

# auth.db 경로 (config.py에서도 설정 가능)
AUTH_DB_PATH = Path(__file__).parent.parent.parent / "data" / "auth.db"


def get_auth_db() -> sqlite3.Connection:
    """auth.db 연결을 반환한다."""
    conn = sqlite3.connect(str(AUTH_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_auth_db():
    """auth.db 스키마를 초기화한다 (존재하지 않으면 생성)."""
    conn = get_auth_db()

    conn.executescript("""
    -- 역할 테이블
    CREATE TABLE IF NOT EXISTS roles (
        role_id     INTEGER PRIMARY KEY AUTOINCREMENT,
        role_name   TEXT NOT NULL UNIQUE,
        role_level  INTEGER NOT NULL DEFAULT 1,
        description TEXT DEFAULT '',
        created_at  TEXT DEFAULT (datetime('now'))
    );

    -- 사용자 테이블
    CREATE TABLE IF NOT EXISTS users (
        user_id         INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id     TEXT NOT NULL UNIQUE,
        username        TEXT NOT NULL,
        password_hash   TEXT NOT NULL,
        role_id         INTEGER NOT NULL DEFAULT 2,
        is_active       INTEGER NOT NULL DEFAULT 1,
        must_change_pw  INTEGER NOT NULL DEFAULT 1,
        failed_attempts INTEGER NOT NULL DEFAULT 0,
        locked_until    TEXT,
        last_login      TEXT,
        created_at      TEXT DEFAULT (datetime('now')),
        updated_at      TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (role_id) REFERENCES roles(role_id)
    );

    -- 로그인 이력
    CREATE TABLE IF NOT EXISTS login_history (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER NOT NULL,
        employee_id TEXT NOT NULL,
        action      TEXT NOT NULL DEFAULT 'login',
        success     INTEGER NOT NULL DEFAULT 0,
        ip_address  TEXT DEFAULT '',
        user_agent  TEXT DEFAULT '',
        timestamp   TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    );

    -- 비밀번호 변경 이력
    CREATE TABLE IF NOT EXISTS password_history (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id         INTEGER NOT NULL,
        password_hash   TEXT NOT NULL,
        changed_at      TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    );
    """)

    # v2.3: 신규 컬럼 마이그레이션 (기존 DB 호환)
    _migrate_columns = [
        ("email", "TEXT DEFAULT ''"),
        ("phone", "TEXT DEFAULT ''"),
        ("department", "TEXT DEFAULT ''"),
        ("position", "TEXT DEFAULT ''"),
        # v2.7: 입사/퇴사일
        ("hire_date", "TEXT DEFAULT ''"),
        ("resign_date", "TEXT DEFAULT ''"),
    ]
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    for col_name, col_def in _migrate_columns:
        if col_name not in existing_cols:
            conn.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")

    # 기본 역할 삽입 (중복 무시)
    default_roles = [
        ("INACTIVE", 0, "비활성 계정"),
        ("EMPLOYEE", 1, "일반 사원 (기본)"),
        ("MANAGER", 2, "관리자급 (과장 이상)"),
        ("TEAM_LEAD", 3, "팀장"),
        ("HR_ADMIN", 4, "인사 관리자"),
        ("SYS_ADMIN", 5, "시스템 관리자"),
    ]
    for role_name, role_level, description in default_roles:
        conn.execute(
            "INSERT OR IGNORE INTO roles (role_name, role_level, description) VALUES (?, ?, ?)",
            (role_name, role_level, description),
        )

    conn.commit()
    conn.close()

    # AUTH_BACKEND=firestore 일 때 Firestore 의 사용자/역할을 SQLite mirror 에 동기화
    _sync_from_firestore_if_enabled()


def _sync_from_firestore_if_enabled() -> int:
    """AUTH_BACKEND=firestore 인 경우 auth_users / auth_roles 컬렉션을 SQLite mirror 에 upsert.

    Firestore 가 source-of-truth, SQLite 는 read-cache.
    인스턴스 부팅 시 1회 실행. 사용자 추가는 Firestore 콘솔/스크립트로, 인스턴스 재시작 시 반영.

    Returns: 동기화된 사용자 수
    """
    import os
    if os.environ.get("AUTH_BACKEND", "").lower() != "firestore":
        return 0

    try:
        from google.cloud import firestore  # type: ignore
        db = firestore.Client()
    except Exception as e:
        print(f"[auth] Firestore 클라이언트 초기화 실패: {e}")
        return 0

    conn = get_auth_db()

    # 1. roles 동기화
    roles_synced = 0
    try:
        for snap in db.collection("auth_roles").stream():
            d = snap.to_dict() or {}
            conn.execute(
                """INSERT INTO roles (role_id, role_name, role_level, description)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(role_name) DO UPDATE SET
                     role_level  = excluded.role_level,
                     description = excluded.description""",
                (d.get("role_id"), d.get("role_name"), d.get("role_level", 1), d.get("description", "")),
            )
            roles_synced += 1
    except Exception as e:
        print(f"[auth] roles sync 실패: {e}")

    # 2. users 동기화 (employee_id 가 doc id)
    users_synced = 0
    try:
        # role_name → role_id 매핑
        role_map = {r["role_name"]: r["role_id"]
                    for r in conn.execute("SELECT role_name, role_id FROM roles")}

        for snap in db.collection("auth_users").stream():
            d = snap.to_dict() or {}
            emp_id = d.get("employee_id") or snap.id
            role_id = d.get("role_id") or role_map.get(d.get("role_name"), 1)

            # UPSERT (employee_id 기준) — INSERT OR REPLACE 는 user_id 가 변하므로
            # login_history/password_history 의 FK 가 깨진다.
            conn.execute(
                """INSERT INTO users
                   (employee_id, username, password_hash, role_id, is_active, must_change_pw,
                    failed_attempts, locked_until, last_login,
                    created_at, updated_at, email, phone, department, position, hire_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(employee_id) DO UPDATE SET
                     username        = excluded.username,
                     password_hash   = excluded.password_hash,
                     role_id         = excluded.role_id,
                     is_active       = excluded.is_active,
                     must_change_pw  = excluded.must_change_pw,
                     email           = excluded.email,
                     phone           = excluded.phone,
                     department      = excluded.department,
                     position        = excluded.position,
                     hire_date       = excluded.hire_date,
                     updated_at      = excluded.updated_at""",
                (
                    emp_id, d.get("username", ""), d.get("password_hash", ""),
                    role_id,
                    1 if d.get("is_active", True) else 0,
                    1 if d.get("must_change_pw", False) else 0,
                    int(d.get("failed_attempts") or 0),
                    d.get("locked_until"),
                    d.get("last_login"),
                    d.get("created_at", ""),
                    d.get("updated_at", ""),
                    d.get("email", ""),
                    d.get("phone", ""),
                    d.get("department", ""),
                    d.get("position", ""),
                    d.get("hire_date", ""),
                ),
            )
            users_synced += 1
    except Exception as e:
        print(f"[auth] users sync 실패: {e}")

    conn.commit()
    conn.close()
    print(f"[auth] Firestore → SQLite 동기화 완료: roles={roles_synced}, users={users_synced}")
    return users_synced


def seed_admin_user():
    """최초 실행 시 시스템 관리자 계정을 생성한다."""
    from core.auth.password import hash_password

    conn = get_auth_db()

    # admin 계정이 이미 존재하면 스킵
    existing = conn.execute("SELECT user_id FROM users WHERE employee_id = 'admin'").fetchone()
    if existing:
        conn.close()
        return

    # SYS_ADMIN 역할 ID 조회
    role = conn.execute("SELECT role_id FROM roles WHERE role_name = 'SYS_ADMIN'").fetchone()
    if not role:
        conn.close()
        return

    # SEC-P0: 초기 비밀번호는 최초 로그인 시 반드시 변경 필요 (must_change_pw=1)
    pw_hash = hash_password("admin1234")
    conn.execute(
        """INSERT INTO users (employee_id, username, password_hash, role_id, is_active, must_change_pw)
           VALUES (?, ?, ?, ?, 1, 1)""",
        ("admin", "시스템관리자", pw_hash, role["role_id"]),
    )
    conn.commit()
    conn.close()


# ── v3.4: 33명 테스트 계정 (auth.db 실제 데이터와 동기화) ──
TEST_USERS = [
    # (사원번호, 이름, 역할명, 부서, 직급)
    # ── 관리자급 (HR_ADMIN / TEAM_LEAD) ──
    ("HR-0001",  "김인사",   "HR_ADMIN",  "총무인사팀",     "팀장"),
    ("QA-0100",  "이품질",   "TEAM_LEAD", "품질보증팀",     "팀장"),
    ("PR-0200",  "박생산",   "TEAM_LEAD", "생산관리팀",     "팀장"),
    ("IT-0001",  "김민수",   "TEAM_LEAD", "IT전략팀",       "부장"),
    ("QM-0001",  "이지원",   "TEAM_LEAD", "품질경영팀",     "차장"),
    # ── 매니저급 (MANAGER) ──
    ("QA-0101",  "최품과",   "MANAGER",   "품질보증팀",     "과장"),
    ("PT-0301",  "정기술",   "MANAGER",   "생산기술팀",     "과장"),
    ("SL-0401",  "한영업",   "MANAGER",   "영업팀",         "과장"),
    ("ES-0001",  "박성현",   "MANAGER",   "ESG경영팀",      "과장"),
    ("PU-0001",  "최민지",   "MANAGER",   "구매팀",         "과장"),
    ("RE-0001",  "황지윤",   "MANAGER",   "전장선행개발팀", "과장"),
    # ── 일반 직원 (EMPLOYEE) — 대리급 ──
    ("QA-0102",  "윤품대",   "EMPLOYEE",  "품질보증팀",     "대리"),
    ("QA-0001",  "강예은",   "EMPLOYEE",  "품질보증팀",     "대리"),
    ("GS-0001",  "정동현",   "EMPLOYEE",  "해외지원팀",     "대리"),
    ("SF-0001",  "조승우",   "EMPLOYEE",  "안전보건팀",     "대리"),
    ("SF-0501",  "장안전",   "EMPLOYEE",  "안전보건팀",     "대리"),
    ("RB-0001",  "권유준",   "EMPLOYEE",  "바디선행개발팀", "대리"),
    ("RD-0801",  "강연구",   "EMPLOYEE",  "바디선행개발팀", "사원"),
    # ── 일반 직원 (EMPLOYEE) — 주임/사원급 ──
    ("MF-0901",  "오금형",   "EMPLOYEE",  "금형생산팀",     "주임"),
    ("PM-0001",  "윤지아",   "EMPLOYEE",  "생산관리팀",     "주임"),
    ("SL-0001",  "장태현",   "EMPLOYEE",  "영업팀",         "주임"),
    ("EX-0001",  "안서준",   "EMPLOYEE",  "경영지원",       "주임"),
    ("IT-0701",  "임아이",   "EMPLOYEE",  "IT전략팀",       "사원"),
    ("PU-0601",  "송구매",   "EMPLOYEE",  "구매팀",         "사원"),
    ("AT-0001",  "서은우",   "EMPLOYEE",  "자동화기술팀",   "사원"),
    ("ED-0001",  "류민재",   "EMPLOYEE",  "기술교육원",     "사원"),
    ("HR-0000",  "김노예",   "EMPLOYEE",  "총무인사팀",     "사원"),
    ("MD-0001",  "한시우",   "EMPLOYEE",  "금형생산팀",     "사원"),
    ("PD-0001",  "임다은",   "EMPLOYEE",  "부품개발팀",     "사원"),
    ("PT-0001",  "오지유",   "EMPLOYEE",  "생산기술팀",     "사원"),
    ("VR-0001",  "신하린",   "EMPLOYEE",  "비전연구팀",     "사원"),
    # ── 기타 (테스트/레거시) ──
    ("HR-0002",  "송수아",   "EMPLOYEE",  "인사관리",       "사원"),
    ("HR-9999",  "노예",     "EMPLOYEE",  "인사관리",       "사원"),
]


def seed_test_users() -> int:
    """부서별/직급별 테스트 계정을 일괄 생성한다. 이미 존재하면 스킵.

    Returns:
        새로 생성된 계정 수
    """
    from core.auth.password import hash_password, generate_initial_password

    init_auth_db()
    seed_admin_user()

    conn = get_auth_db()

    # 역할 ID 매핑
    roles = conn.execute("SELECT role_name, role_id FROM roles").fetchall()
    role_map = {r["role_name"]: r["role_id"] for r in roles}

    created = 0
    for emp_id, name, role_name, dept, position in TEST_USERS:
        existing = conn.execute("SELECT 1 FROM users WHERE employee_id = ?", (emp_id,)).fetchone()
        if existing:
            continue

        role_id = role_map.get(role_name, role_map.get("EMPLOYEE", 2))
        pw = generate_initial_password(emp_id)
        pw_hash = hash_password(pw)

        conn.execute(
            """INSERT INTO users (employee_id, username, password_hash, role_id,
               is_active, must_change_pw, department, position)
               VALUES (?, ?, ?, ?, 1, 0, ?, ?)""",
            (emp_id, name, pw_hash, role_id, dept, position),
        )
        created += 1

    conn.commit()
    conn.close()
    return created
