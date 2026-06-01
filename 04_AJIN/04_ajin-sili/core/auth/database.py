"""인증 데이터베이스 (auth.db) — 사용자/역할/로그인 이력 관리

employees.db(기존, 읽기전용)와 분리된 별도 DB.
employee_id를 외래키로 연결.
"""

import sqlite3
import os
from pathlib import Path
from typing import Any

from core.data_lineage import ensure_lineage_columns, lineage_values
from core.feature_flags import firebase_read_fallback_enabled, firebase_writes_enabled

# auth.db 경로 (config.py에서도 설정 가능)
AUTH_DB_PATH = Path(__file__).parent.parent.parent / "data" / "auth.db"


def _env_truthy(name: str, default: bool = False) -> bool:
    """Return whether an environment variable is enabled.

    Args:
        name: Environment variable name.
        default: Value to use when the variable is unset.

    Returns:
        bool: True for common truthy string values.
    """

    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


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
        data_class      TEXT NOT NULL DEFAULT 'unknown',
        source_system   TEXT NOT NULL DEFAULT 'unknown',
        source_label    TEXT DEFAULT '',
        source_updated_at TEXT DEFAULT '',
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
        data_class  TEXT NOT NULL DEFAULT 'unknown',
        source_system TEXT NOT NULL DEFAULT 'unknown',
        source_label TEXT DEFAULT '',
        source_updated_at TEXT DEFAULT '',
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
        # v4.7 Feature E Phase 2 — 2FA (TOTP) 컬럼
        ("totp_secret", "BLOB DEFAULT NULL"),
        ("backup_codes_hash", "TEXT DEFAULT ''"),
        ("totp_enabled", "INTEGER NOT NULL DEFAULT 0"),
        ("totp_failed_count", "INTEGER NOT NULL DEFAULT 0"),
        ("totp_locked_until", "TEXT DEFAULT NULL"),
        # v4.7 PR-E2 — IdP user-cache: 마지막 IdP fetch 시각 (ISO8601 UTC)
        ("cached_at", "TEXT DEFAULT NULL"),
        # P1 — common data lineage labels for seed/system/real users.
        ("data_class", "TEXT NOT NULL DEFAULT 'unknown'"),
        ("source_system", "TEXT NOT NULL DEFAULT 'unknown'"),
        ("source_label", "TEXT DEFAULT ''"),
        ("source_updated_at", "TEXT DEFAULT ''"),
        # v3.9 — 디지털 사원증 사진 (base64 data URL, 256x256 JPEG)
        ("photo_url", "TEXT NOT NULL DEFAULT ''"),
    ]
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    for col_name, col_def in _migrate_columns:
        if col_name not in existing_cols:
            conn.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
    ensure_lineage_columns(conn, "login_history")

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
    # APP_DB_BACKEND=postgres 일 때 Supabase/Postgres users/roles 를 SQLite auth mirror 로 동기화
    _sync_from_postgres_if_enabled()


def _sync_from_firestore_if_enabled() -> int:
    """AUTH_BACKEND=firestore 인 경우 auth_users / auth_roles 컬렉션을 SQLite mirror 에 upsert.

    Firestore 가 source-of-truth, SQLite 는 read-cache.
    인스턴스 부팅 시 1회 실행. 사용자 추가는 Firestore 콘솔/스크립트로, 인스턴스 재시작 시 반영.

    Returns: 동기화된 사용자 수
    """
    import os
    if os.environ.get("AUTH_BACKEND", "").lower() != "firestore":
        return 0
    if not firebase_read_fallback_enabled():
        print("[auth] Firestore read fallback 비활성 — auth mirror sync 스킵")
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
            lineage = lineage_values("real", "firestore_auth", "Firestore auth_users mirror")
            conn.execute(
                """INSERT INTO users
                   (employee_id, username, password_hash, role_id, is_active, must_change_pw,
                    failed_attempts, locked_until, last_login,
                    created_at, updated_at, email, phone, department, position, hire_date,
                    data_class, source_system, source_label, source_updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                     data_class      = excluded.data_class,
                     source_system   = excluded.source_system,
                     source_label    = excluded.source_label,
                     source_updated_at = excluded.source_updated_at,
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
                    lineage["data_class"],
                    lineage["source_system"],
                    lineage["source_label"],
                    lineage["source_updated_at"],
                ),
            )
            users_synced += 1
    except Exception as e:
        print(f"[auth] users sync 실패: {e}")

    conn.commit()
    conn.close()
    print(f"[auth] Firestore → SQLite 동기화 완료: roles={roles_synced}, users={users_synced}")
    return users_synced


def _row_bool(value: Any) -> int:
    """Normalize DB boolean-ish values into SQLite integer flags.

    Args:
        value: Value returned by Postgres or SQLite.

    Returns:
        int: ``1`` for truthy values, otherwise ``0``.
    """

    return 1 if bool(value) else 0


def _sync_from_postgres_if_enabled() -> int:
    """Mirror Supabase/Postgres auth rows into the runtime SQLite auth DB.

    The existing auth router still uses ``core.auth.database.get_auth_db()``.
    During the Supabase cutover, Cloud Run therefore needs a startup mirror so
    login checks use the same production-safe users and password hashes that
    were bootstrapped in Postgres.

    Returns:
        int: Number of user rows mirrored. Returns ``0`` when disabled or when
        sync fails closed.
    """

    if os.environ.get("APP_DB_BACKEND", "").strip().lower() != "postgres":
        return 0
    if not _env_truthy("AUTH_SYNC_POSTGRES_ENABLED", default=True):
        print("[auth] Postgres → SQLite auth mirror 비활성")
        return 0

    try:
        import sqlalchemy as sa

        from core.db import create_sqlalchemy_engine

        engine = create_sqlalchemy_engine()
        with engine.connect() as pg:
            role_rows = (
                pg.execute(
                    sa.text(
                        """
                        select role_id, role_name, role_level, coalesce(description, '') as description
                          from public.roles
                        """
                    )
                )
                .mappings()
                .all()
            )
            column_rows = (
                pg.execute(
                    sa.text(
                        """
                        select column_name
                          from information_schema.columns
                         where table_schema = 'public'
                           and table_name = 'users'
                        """
                    )
                )
                .mappings()
                .all()
            )
            user_columns = {str(row["column_name"]) for row in column_rows}

            def select_column(name: str, default_sql: str, *, coalesce: str | None = None) -> str:
                """Build a safe SELECT expression for known public.users columns."""

                if name not in user_columns:
                    return f"{default_sql} as {name}"
                if coalesce is not None:
                    return f"coalesce(u.{name}, {coalesce}) as {name}"
                return f"u.{name}"

            source_updated_at_expr = (
                "coalesce(u.source_updated_at::text, '') as source_updated_at"
                if "source_updated_at" in user_columns
                else "'' as source_updated_at"
            )
            user_select = ",\n                               ".join(
                [
                    "u.employee_id",
                    "u.username",
                    "u.password_hash",
                    "u.role_id",
                    "u.is_active",
                    "u.must_change_pw",
                    select_column("failed_attempts", "0", coalesce="0"),
                    select_column("locked_until", "null"),
                    select_column("last_login", "null"),
                    select_column("email", "''", coalesce="''"),
                    select_column("phone", "''", coalesce="''"),
                    select_column("department", "''", coalesce="''"),
                    select_column("position", "''", coalesce="''"),
                    select_column("hire_date", "''", coalesce="''"),
                    select_column("resign_date", "''", coalesce="''"),
                    select_column("created_at", "''"),
                    select_column("updated_at", "''"),
                    select_column("data_class", "'unknown'", coalesce="'unknown'"),
                    select_column("source_system", "'postgres_auth'", coalesce="'postgres_auth'"),
                    select_column("source_label", "'Supabase auth mirror'", coalesce="'Supabase auth mirror'"),
                    source_updated_at_expr,
                    select_column("totp_secret", "null"),
                    select_column("backup_codes_hash", "''", coalesce="''"),
                    select_column("totp_enabled", "false", coalesce="false"),
                    select_column("totp_failed_count", "0", coalesce="0"),
                    select_column("totp_locked_until", "null"),
                    select_column("cached_at", "null"),
                ]
            )
            user_rows = (
                pg.execute(sa.text(f"select {user_select} from public.users u"))
                .mappings()
                .all()
            )
    except Exception as e:
        print(f"[auth] Postgres → SQLite auth mirror 실패: {e}")
        return 0

    conn = get_auth_db()
    try:
        for row in role_rows:
            conn.execute(
                """INSERT INTO roles (role_id, role_name, role_level, description)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(role_name) DO UPDATE SET
                     role_level = excluded.role_level,
                     description = excluded.description""",
                (
                    int(row["role_id"]),
                    str(row["role_name"]),
                    int(row["role_level"]),
                    str(row["description"] or ""),
                ),
            )

        users_synced = 0
        for row in user_rows:
            employee_id = str(row["employee_id"] or "").strip()
            if not employee_id:
                continue
            conn.execute(
                """INSERT INTO users (
                     employee_id, username, password_hash, role_id, is_active, must_change_pw,
                     failed_attempts, locked_until, last_login, email, phone, department,
                     position, hire_date, resign_date, created_at, updated_at, data_class,
                     source_system, source_label, source_updated_at, totp_secret,
                     backup_codes_hash, totp_enabled, totp_failed_count, totp_locked_until,
                     cached_at
                   )
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(employee_id) DO UPDATE SET
                     username = excluded.username,
                     password_hash = excluded.password_hash,
                     role_id = excluded.role_id,
                     is_active = excluded.is_active,
                     must_change_pw = excluded.must_change_pw,
                     failed_attempts = excluded.failed_attempts,
                     locked_until = excluded.locked_until,
                     last_login = excluded.last_login,
                     email = excluded.email,
                     phone = excluded.phone,
                     department = excluded.department,
                     position = excluded.position,
                     hire_date = excluded.hire_date,
                     resign_date = excluded.resign_date,
                     updated_at = excluded.updated_at,
                     data_class = excluded.data_class,
                     source_system = excluded.source_system,
                     source_label = excluded.source_label,
                     source_updated_at = excluded.source_updated_at,
                     totp_secret = excluded.totp_secret,
                     backup_codes_hash = excluded.backup_codes_hash,
                     totp_enabled = excluded.totp_enabled,
                     totp_failed_count = excluded.totp_failed_count,
                     totp_locked_until = excluded.totp_locked_until,
                     cached_at = excluded.cached_at""",
                (
                    employee_id,
                    str(row["username"] or employee_id),
                    str(row["password_hash"] or "!DISABLED!"),
                    int(row["role_id"]),
                    _row_bool(row["is_active"]),
                    _row_bool(row["must_change_pw"]),
                    int(row["failed_attempts"] or 0),
                    str(row["locked_until"] or "") or None,
                    str(row["last_login"] or "") or None,
                    str(row["email"] or ""),
                    str(row["phone"] or ""),
                    str(row["department"] or ""),
                    str(row["position"] or ""),
                    str(row["hire_date"] or ""),
                    str(row["resign_date"] or ""),
                    str(row["created_at"] or ""),
                    str(row["updated_at"] or ""),
                    str(row["data_class"] or "unknown"),
                    str(row["source_system"] or "postgres_auth"),
                    str(row["source_label"] or "Supabase auth mirror"),
                    str(row["source_updated_at"] or ""),
                    row["totp_secret"],
                    str(row["backup_codes_hash"] or ""),
                    _row_bool(row["totp_enabled"]),
                    int(row["totp_failed_count"] or 0),
                    str(row["totp_locked_until"] or "") or None,
                    str(row["cached_at"] or "") or None,
                ),
            )
            users_synced += 1
        conn.commit()
    finally:
        conn.close()

    print(f"[auth] Postgres → SQLite auth mirror 완료: roles={len(role_rows)}, users={users_synced}")
    return users_synced


def persist_user_to_firestore(user: dict) -> bool:
    """SQLite 사용자 변경을 Firestore auth_users 컬렉션에 upsert (reverse-sync).

    Plan v3.7 — Module E (인사 관리) 의 새 계정이 Cloud Run instance 재시작 후에도
    유지되도록 Firestore 에 영속화. AUTH_BACKEND != 'firestore' (로컬 dev) 또는
    firestore 클라이언트 초기화 실패 시 silent skip — auth.db INSERT 자체는 이미
    완료된 상태이므로 endpoint 200 반환에 영향 주지 않음.

    user dict 필요 키: employee_id, username, password_hash, role_id, role_name,
                      is_active, must_change_pw, email, phone, department, position,
                      hire_date, created_at, updated_at
    Returns: 성공 여부.
    """
    import os
    if os.environ.get("AUTH_BACKEND", "").lower() != "firestore":
        return False  # 로컬 dev 는 SQLite-only — skip
    if not firebase_writes_enabled():
        print("[auth] Firebase write 비활성 — Firestore auth_users upsert 스킵")
        return False
    if not user.get("employee_id"):
        print(f"[auth] Firestore upsert 스킵 — employee_id 누락: {user}")
        return False
    try:
        from google.cloud import firestore  # type: ignore
        db = firestore.Client()
        # set(merge=True) 로 idempotent — 기존 doc 의 다른 필드 보존하면서 부분 update
        db.collection("auth_users").document(user["employee_id"]).set(user, merge=True)
        print(f"[auth] Firestore auth_users/{user['employee_id']} upsert 완료")
        return True
    except Exception as e:
        print(f"[auth] Firestore upsert 실패 ({user.get('employee_id')}): {e}")
        return False


def _mirror_admin_to_postgres(plaintext_password: str, password_hash: str) -> None:
    """admin user 를 Supabase Postgres (public.users) 에 UPSERT.

    APP_DB_BACKEND=postgres 활성 시 _persist_password_change_to_postgres 가
    이 row 를 찾지 못하면 "affected no rows" RuntimeError 로 비밀번호 변경 503.
    startup hook 에서 admin row 를 미리 보장한다.

    Args:
        plaintext_password: 정책 검증용 (unused now — caller 가 이미 검증).
        password_hash: bcrypt hash — Postgres 에 그대로 저장.
    """
    if os.environ.get("APP_DB_BACKEND", "").strip().lower() != "postgres":
        return
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        return
    try:
        import sqlalchemy as sa
        from core.db import create_sqlalchemy_engine

        # core.db 의 create_sqlalchemy_engine 은 _normalize_postgres_url 적용 —
        # postgresql:// → postgresql+psycopg:// 로 변환하여 psycopg3 driver 사용.
        # 직접 sa.create_engine(db_url) 하면 SQLAlchemy 가 default psycopg2 찾음.
        engine = create_sqlalchemy_engine()
        with engine.begin() as pg:
            pg.execute(
                sa.text(
                    """
                    INSERT INTO public.roles (role_id, role_name, role_level, description)
                    VALUES (5, 'SYS_ADMIN', 5, 'System Administrator (bootstrap)')
                    ON CONFLICT (role_id) DO NOTHING
                    """
                )
            )
            pg.execute(
                sa.text(
                    """
                    INSERT INTO public.users (
                        employee_id, username, password_hash, role_id,
                        is_active, must_change_pw, failed_attempts, locked_until
                    )
                    VALUES (
                        :emp, :usr, :pw, 5,
                        true, true, 0, NULL
                    )
                    ON CONFLICT (employee_id) DO UPDATE
                    SET password_hash = EXCLUDED.password_hash,
                        is_active = true,
                        must_change_pw = true,
                        failed_attempts = 0,
                        locked_until = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    """
                ),
                {"emp": "admin", "usr": "시스템관리자", "pw": password_hash},
            )
        print("[auth] admin row mirrored to Supabase Postgres (public.users)")
    except Exception as e:  # noqa: BLE001
        # Non-fatal — SQLite 는 이미 준비됐고 application 동작 가능.
        # Postgres mirror 실패는 비밀번호 변경 endpoint 만 영향.
        print(f"[auth] Postgres admin mirror skipped: {e}")


def seed_admin_user():
    """Create the bootstrap admin only when explicitly enabled.

    Raises:
        RuntimeError: If bootstrap is enabled without a valid password.
    """
    from core.auth.password import hash_password, validate_password_strength

    conn = get_auth_db()

    # legacy admin/admin1234 계정은 production-safe 기본값으로 비활성화한다.
    existing = conn.execute("SELECT user_id FROM users WHERE employee_id = 'admin'").fetchone()
    if existing:
        lineage = lineage_values("system", "bootstrap_admin", "Initial bootstrap admin")
        if not _env_truthy("AUTH_ALLOW_LEGACY_ADMIN", default=False):
            inactive_role = conn.execute(
                "SELECT role_id FROM roles WHERE role_name = 'INACTIVE'"
            ).fetchone()
            role_id = inactive_role["role_id"] if inactive_role else 1
            conn.execute(
                """UPDATE users
                      SET password_hash = '!DISABLED!',
                          role_id = ?,
                          is_active = 0,
                          must_change_pw = 1,
                          data_class = ?,
                          source_system = ?,
                          source_label = ?,
                          source_updated_at = ?
                    WHERE employee_id = 'admin'""",
                (
                    role_id,
                    lineage["data_class"],
                    lineage["source_system"],
                    "Legacy default admin disabled",
                    lineage["source_updated_at"],
                ),
            )
            conn.commit()
            conn.close()
            print("[auth] legacy admin 계정 비활성화 완료")
            return

        # v4.x hotfix: AUTH_BOOTSTRAP_ADMIN_PASSWORD 환경변수가 설정되어 있으면
        # 기존 admin row 의 password_hash + is_active 도 강제 reset.
        # 이전 비활성화 상태가 베이크된 SQLite 에 남아있어도 startup 시 복구된다.
        #
        # v3.10 안전망: 한 번 사용자가 비밀번호를 변경했으면 (must_change_pw=0)
        # 매 deploy 마다 reset 하지 않는다. 잊었을 때 복구 path 는
        # AUTH_BOOTSTRAP_FORCE_RESET=true 명시적으로 set 하면 강제 reset.
        _bootstrap_pw = os.environ.get("AUTH_BOOTSTRAP_ADMIN_PASSWORD", "")
        if _env_truthy("AUTH_BOOTSTRAP_ADMIN_ENABLED", default=False) and _bootstrap_pw:
            # 이미 사용자가 비번 변경했는지 확인 (must_change_pw=0 = customized)
            _existing = conn.execute(
                "SELECT must_change_pw FROM users WHERE employee_id = 'admin'"
            ).fetchone()
            _already_customized = bool(_existing) and not bool(_existing["must_change_pw"])
            _force_reset = _env_truthy("AUTH_BOOTSTRAP_FORCE_RESET", default=False)

            if _already_customized and not _force_reset:
                print(
                    "[auth] admin 비밀번호가 이미 변경된 상태 — bootstrap reset skip "
                    "(force 가 필요하면 AUTH_BOOTSTRAP_FORCE_RESET=true)"
                )
                conn.commit()
                conn.close()
                return

            from core.auth.password import hash_password, validate_password_strength

            _ok, _msg = validate_password_strength(
                _bootstrap_pw, employee_id="admin", username="시스템관리자"
            )
            if _ok:
                _sys_role = conn.execute(
                    "SELECT role_id FROM roles WHERE role_name = 'SYS_ADMIN'"
                ).fetchone()
                _role_id = _sys_role["role_id"] if _sys_role else 5
                _new_hash = hash_password(_bootstrap_pw)
                conn.execute(
                    """UPDATE users
                          SET password_hash = ?,
                              is_active = 1,
                              must_change_pw = 1,
                              failed_attempts = 0,
                              locked_until = NULL,
                              role_id = ?,
                              data_class = ?,
                              source_system = ?,
                              source_label = ?,
                              source_updated_at = ?
                        WHERE employee_id = 'admin'""",
                    (
                        _new_hash,
                        _role_id,
                        lineage["data_class"],
                        lineage["source_system"],
                        lineage["source_label"],
                        lineage["source_updated_at"],
                    ),
                )
                conn.commit()
                conn.close()
                print(
                    "[auth] legacy admin password+is_active reset 완료 "
                    "(AUTH_BOOTSTRAP_ADMIN_PASSWORD)"
                )
                # v4.x — APP_DB_BACKEND=postgres 활성 시 Supabase Postgres 에도 mirror.
                # 이게 없으면 _persist_password_change_to_postgres 가 affected_no_rows
                # 로 503 던지며 비밀번호 변경 막힘.
                _mirror_admin_to_postgres(_bootstrap_pw, _new_hash)
                return
            else:
                print(f"[auth] bootstrap password 정책 미준수: {_msg}")

        conn.execute(
            """UPDATE users
                  SET data_class = ?,
                      source_system = ?,
                      source_label = ?,
                      source_updated_at = ?
                WHERE employee_id = 'admin'""",
            (
                lineage["data_class"],
                lineage["source_system"],
                lineage["source_label"],
                lineage["source_updated_at"],
            ),
        )
        conn.commit()
        conn.close()
        return

    bootstrap_enabled = (
        os.environ.get("AUTH_BOOTSTRAP_ADMIN_ENABLED", "").strip().lower()
        in {"1", "true", "yes", "on"}
    )
    if not bootstrap_enabled:
        conn.close()
        return

    bootstrap_password = os.environ.get("AUTH_BOOTSTRAP_ADMIN_PASSWORD", "")
    ok, message = validate_password_strength(
        bootstrap_password,
        employee_id="admin",
        username="시스템관리자",
    )
    if not ok:
        conn.close()
        raise RuntimeError(f"AUTH_BOOTSTRAP_ADMIN_PASSWORD does not satisfy policy: {message}")

    # SYS_ADMIN 역할 ID 조회
    role = conn.execute("SELECT role_id FROM roles WHERE role_name = 'SYS_ADMIN'").fetchone()
    if not role:
        conn.close()
        return

    # Bootstrap password is secret-provided and must be changed on first login.
    pw_hash = hash_password(bootstrap_password)
    lineage = lineage_values("system", "bootstrap_admin", "Initial bootstrap admin")
    conn.execute(
        """INSERT INTO users
             (employee_id, username, password_hash, role_id, is_active, must_change_pw,
              data_class, source_system, source_label, source_updated_at)
           VALUES (?, ?, ?, ?, 1, 1, ?, ?, ?, ?)""",
        (
            "admin",
            "시스템관리자",
            pw_hash,
            role["role_id"],
            lineage["data_class"],
            lineage["source_system"],
            lineage["source_label"],
            lineage["source_updated_at"],
        ),
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

    Raises:
        RuntimeError: If synthetic auth seeding is not explicitly enabled or the
            runtime is production-like.
    """
    from core.auth.password import generate_initial_password, hash_password
    from core.auth.policy import seed_test_users_allowed

    if not seed_test_users_allowed():
        raise RuntimeError(
            "AUTH_SEED_TEST_USERS=true is required outside production; "
            "synthetic auth users are blocked in production."
        )

    init_auth_db()
    seed_admin_user()

    conn = get_auth_db()
    seed_lineage = lineage_values("synthetic", "seed_test_users", "Seed test users")

    # 역할 ID 매핑
    roles = conn.execute("SELECT role_name, role_id FROM roles").fetchall()
    role_map = {r["role_name"]: r["role_id"] for r in roles}

    created = 0
    for emp_id, name, role_name, dept, position in TEST_USERS:
        existing = conn.execute("SELECT 1 FROM users WHERE employee_id = ?", (emp_id,)).fetchone()
        if existing:
            conn.execute(
                """UPDATE users
                      SET data_class = ?,
                          source_system = ?,
                          source_label = ?,
                          source_updated_at = ?
                    WHERE employee_id = ?""",
                (
                    seed_lineage["data_class"],
                    seed_lineage["source_system"],
                    seed_lineage["source_label"],
                    seed_lineage["source_updated_at"],
                    emp_id,
                ),
            )
            continue

        role_id = role_map.get(role_name, role_map.get("EMPLOYEE", 2))
        pw = generate_initial_password(emp_id)
        pw_hash = hash_password(pw)

        conn.execute(
            """INSERT INTO users (employee_id, username, password_hash, role_id,
               is_active, must_change_pw, department, position,
               data_class, source_system, source_label, source_updated_at)
               VALUES (?, ?, ?, ?, 1, 0, ?, ?, ?, ?, ?, ?)""",
            (
                emp_id,
                name,
                pw_hash,
                role_id,
                dept,
                position,
                seed_lineage["data_class"],
                seed_lineage["source_system"],
                seed_lineage["source_label"],
                seed_lineage["source_updated_at"],
            ),
        )
        created += 1

    conn.commit()
    conn.close()
    return created
