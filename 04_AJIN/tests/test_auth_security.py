"""Security regression tests for AJIN authentication hardening."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers import auth as auth_router
from core.auth import database as auth_database
from core.auth.password import (
    generate_initial_password,
    hash_password,
    validate_password_change,
    validate_password_strength,
    verify_password,
)


HARDENED_ROUTER_PATHS = (
    Path("backend/routers/draft.py"),
    Path("backend/routers/onboarding.py"),
    Path("backend/routers/export.py"),
    Path("backend/routers/feedback.py"),
)


def _use_tmp_auth_db(monkeypatch, tmp_path) -> Path:
    """Point auth.db helpers at a temporary SQLite file.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Pytest temporary path fixture.

    Returns:
        Path: Temporary auth DB path.
    """

    db_path = tmp_path / "auth.db"
    monkeypatch.setattr(auth_database, "AUTH_DB_PATH", db_path)
    monkeypatch.delenv("AUTH_BACKEND", raising=False)
    monkeypatch.delenv("AUTH_BOOTSTRAP_ADMIN_ENABLED", raising=False)
    monkeypatch.delenv("AUTH_BOOTSTRAP_ADMIN_PASSWORD", raising=False)
    auth_database.init_auth_db()
    return db_path


def _insert_user(employee_id: str = "E001", password: str = "CurrentPass!234") -> int:
    """Insert a test auth user.

    Args:
        employee_id: Employee id for the user.
        password: Plain password to hash.

    Returns:
        int: Inserted user id.
    """

    conn = auth_database.get_auth_db()
    role = conn.execute("SELECT role_id FROM roles WHERE role_name = 'EMPLOYEE'").fetchone()
    cursor = conn.execute(
        """INSERT INTO users
             (employee_id, username, password_hash, role_id, is_active, must_change_pw)
           VALUES (?, ?, ?, ?, 1, 1)""",
        (employee_id, "테스트사용자", hash_password(password), role["role_id"]),
    )
    conn.commit()
    conn.close()
    return int(cursor.lastrowid)


def _client_for(user: SimpleNamespace | None = None) -> TestClient:
    """Create an auth-router TestClient.

    Args:
        user: Optional dependency override user context.

    Returns:
        TestClient: Router-only FastAPI test client.
    """

    app = FastAPI()
    app.include_router(auth_router.router, prefix="/api")
    if user is not None:
        app.dependency_overrides[auth_router.get_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=False)


def test_optional_auth_is_not_used_on_hardened_feature_routers() -> None:
    """Draft/onboarding/export/feedback must fail closed with required auth."""

    for router_path in HARDENED_ROUTER_PATHS:
        text = router_path.read_text(encoding="utf-8")
        assert "Depends(get_optional_user)" not in text
        assert "get_optional_user" not in text


def test_supabase_lockdown_migration_contains_grants_rls_and_deny_policy() -> None:
    """The P1 Alembic migration must lock grants and add explicit deny policies."""

    migration = Path(
        "alembic/versions/20260518_0002_lock_down_supabase_data_api.py"
    ).read_text(encoding="utf-8")

    assert "revoke all privileges on all tables in schema public" in migration
    assert "alter default privileges in schema public revoke" in migration
    assert "enable row level security" in migration
    assert "deny_all_data_api_" in migration
    assert "to anon, authenticated" in migration
    assert "using (false)" in migration
    assert "with check (false)" in migration


def test_temporary_password_is_random_and_policy_compliant() -> None:
    """Generated temporary passwords must not follow deterministic employee-id patterns."""

    first = generate_initial_password("HR-0001")
    second = generate_initial_password("HR-0001")

    assert first != "ajin0001"
    assert second != "ajin0001"
    assert first != second
    assert validate_password_strength(first, employee_id="HR-0001")[0] is True
    assert validate_password_strength(second, employee_id="HR-0001")[0] is True


def test_password_policy_rejects_weak_contextual_and_oversized_values() -> None:
    """Backend password validator enforces minimum, blocklist, and bcrypt byte limit."""

    assert validate_password_strength("short!1")[0] is False
    assert validate_password_strength("admin1234xxxx")[0] is False
    assert validate_password_strength("ajin1234!!!!", employee_id="AJ-0001")[0] is False
    assert validate_password_strength("가" * 25)[0] is False


def test_change_password_requires_bearer_token(monkeypatch, tmp_path) -> None:
    """change-password must reject unauthenticated requests."""

    _use_tmp_auth_db(monkeypatch, tmp_path)
    _insert_user()

    response = _client_for().post(
        "/api/auth/change-password",
        json={"current_password": "CurrentPass!234", "new_password": "NewStrong!2345"},
    )

    assert response.status_code == 401


def test_change_password_forbids_employee_id_body(monkeypatch, tmp_path) -> None:
    """Request body can no longer select another employee_id."""

    _use_tmp_auth_db(monkeypatch, tmp_path)
    _insert_user()
    response = _client_for(SimpleNamespace(employee_id="E001")).post(
        "/api/auth/change-password",
        json={
            "employee_id": "E002",
            "current_password": "CurrentPass!234",
            "new_password": "NewStrong!2345",
        },
    )

    assert response.status_code == 422


def test_change_password_rejects_current_and_recent_password_reuse(monkeypatch, tmp_path) -> None:
    """Current password and recent password history cannot be reused."""

    _use_tmp_auth_db(monkeypatch, tmp_path)
    user_id = _insert_user()
    reused_password = "OldUsedPass!234"
    conn = auth_database.get_auth_db()
    conn.execute(
        "INSERT INTO password_history (user_id, password_hash) VALUES (?, ?)",
        (user_id, hash_password(reused_password)),
    )
    conn.commit()
    conn.close()

    client = _client_for(SimpleNamespace(employee_id="E001"))
    current_response = client.post(
        "/api/auth/change-password",
        json={"current_password": "CurrentPass!234", "new_password": "CurrentPass!234"},
    )
    history_response = client.post(
        "/api/auth/change-password",
        json={"current_password": "CurrentPass!234", "new_password": reused_password},
    )

    assert current_response.status_code == 400
    assert history_response.status_code == 400


def test_change_password_succeeds_and_stores_previous_hash(monkeypatch, tmp_path) -> None:
    """Successful changes clear must_change_pw and record the previous hash only."""

    _use_tmp_auth_db(monkeypatch, tmp_path)
    user_id = _insert_user()
    conn = auth_database.get_auth_db()
    before_hash = conn.execute(
        "SELECT password_hash FROM users WHERE user_id = ?",
        (user_id,),
    ).fetchone()["password_hash"]
    conn.close()

    response = _client_for(SimpleNamespace(employee_id="E001")).post(
        "/api/auth/change-password",
        json={"current_password": "CurrentPass!234", "new_password": "NewStrong!2345"},
    )

    conn = auth_database.get_auth_db()
    user_row = conn.execute(
        "SELECT password_hash, must_change_pw FROM users WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    history_row = conn.execute(
        "SELECT password_hash FROM password_history WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    conn.close()

    assert response.status_code == 200
    assert user_row["must_change_pw"] == 0
    assert user_row["password_hash"] != before_hash
    assert history_row["password_hash"] == before_hash


def test_change_password_syncs_postgres_auth_source(monkeypatch, tmp_path) -> None:
    """Postgres cutover must persist password changes beyond the SQLite mirror."""

    _use_tmp_auth_db(monkeypatch, tmp_path)
    _insert_user()
    captured: dict[str, object] = {}

    class _Result:
        rowcount = 1

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, statement, params):
            captured["statement"] = str(statement)
            captured["params"] = dict(params)
            return _Result()

    class _Engine:
        def begin(self):
            return _Connection()

    import core.db as db

    monkeypatch.setattr(db, "is_postgres_enabled", lambda: True)
    monkeypatch.setattr(db, "create_sqlalchemy_engine", lambda: _Engine())

    response = _client_for(SimpleNamespace(employee_id="E001")).post(
        "/api/auth/change-password",
        json={"current_password": "CurrentPass!234", "new_password": "NewStrong!2345"},
    )

    conn = auth_database.get_auth_db()
    user_row = conn.execute(
        "SELECT password_hash, must_change_pw, failed_attempts, locked_until FROM users WHERE employee_id = ?",
        ("E001",),
    ).fetchone()
    conn.close()

    params = captured["params"]
    assert response.status_code == 200
    assert "update public.users" in str(captured["statement"])
    assert params["employee_id"] == "E001"
    assert params["old_hash"] != params["new_hash"]
    assert verify_password("NewStrong!2345", str(params["new_hash"]))
    assert verify_password("NewStrong!2345", user_row["password_hash"])
    assert user_row["must_change_pw"] == 0
    assert user_row["failed_attempts"] == 0
    assert user_row["locked_until"] is None


def test_change_password_rolls_back_when_postgres_sync_fails(monkeypatch, tmp_path) -> None:
    """A failed Postgres password sync must not leave only one instance updated."""

    _use_tmp_auth_db(monkeypatch, tmp_path)
    user_id = _insert_user()
    conn = auth_database.get_auth_db()
    before_hash = conn.execute(
        "SELECT password_hash FROM users WHERE user_id = ?",
        (user_id,),
    ).fetchone()["password_hash"]
    conn.close()

    class _Result:
        rowcount = 0

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, statement, params):
            return _Result()

    class _Engine:
        def begin(self):
            return _Connection()

    import core.db as db

    monkeypatch.setattr(db, "is_postgres_enabled", lambda: True)
    monkeypatch.setattr(db, "create_sqlalchemy_engine", lambda: _Engine())

    response = _client_for(SimpleNamespace(employee_id="E001")).post(
        "/api/auth/change-password",
        json={"current_password": "CurrentPass!234", "new_password": "NewStrong!2345"},
    )

    conn = auth_database.get_auth_db()
    user_row = conn.execute(
        "SELECT password_hash, must_change_pw FROM users WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    history_count = conn.execute(
        "SELECT COUNT(*) FROM password_history WHERE user_id = ?",
        (user_id,),
    ).fetchone()[0]
    conn.close()

    assert response.status_code == 503
    assert user_row["password_hash"] == before_hash
    assert user_row["must_change_pw"] == 1
    assert history_count == 0


def test_password_change_validator_uses_recent_history() -> None:
    """Shared validator rejects hashes from the latest password history."""

    recent_hash = hash_password("RecentPass!234")
    ok, message = validate_password_change(
        "RecentPass!234",
        previous_password_hashes=(recent_hash,),
        employee_id="E001",
        username="테스트사용자",
    )

    assert ok is False
    assert "최근" in message


def test_seed_admin_user_is_disabled_unless_explicitly_enabled(monkeypatch, tmp_path) -> None:
    """Default admin/admin1234 bootstrap is not created by default."""

    _use_tmp_auth_db(monkeypatch, tmp_path)
    auth_database.seed_admin_user()

    conn = auth_database.get_auth_db()
    row = conn.execute("SELECT 1 FROM users WHERE employee_id = 'admin'").fetchone()
    conn.close()

    assert row is None


def test_existing_legacy_admin_is_disabled_by_default(monkeypatch, tmp_path) -> None:
    """Existing legacy admin rows are forced inactive unless explicitly allowed."""

    _use_tmp_auth_db(monkeypatch, tmp_path)
    conn = auth_database.get_auth_db()
    role = conn.execute("SELECT role_id FROM roles WHERE role_name = 'SYS_ADMIN'").fetchone()
    conn.execute(
        """INSERT INTO users
             (employee_id, username, password_hash, role_id, is_active, must_change_pw)
           VALUES ('admin', '시스템관리자', ?, ?, 1, 0)""",
        (hash_password("AdminPass!234"), role["role_id"]),
    )
    conn.commit()
    conn.close()

    auth_database.seed_admin_user()

    conn = auth_database.get_auth_db()
    row = conn.execute(
        """SELECT u.is_active, u.password_hash, r.role_name
             FROM users u JOIN roles r ON u.role_id = r.role_id
            WHERE u.employee_id = 'admin'"""
    ).fetchone()
    conn.close()

    assert row["is_active"] == 0
    assert row["password_hash"] == "!DISABLED!"
    assert row["role_name"] == "INACTIVE"


def test_seed_admin_user_rejects_weak_bootstrap_secret(monkeypatch, tmp_path) -> None:
    """Explicit bootstrap still must pass the backend password policy."""

    _use_tmp_auth_db(monkeypatch, tmp_path)
    monkeypatch.setenv("AUTH_BOOTSTRAP_ADMIN_ENABLED", "true")
    monkeypatch.setenv("AUTH_BOOTSTRAP_ADMIN_PASSWORD", "admin1234")

    with pytest.raises(RuntimeError):
        auth_database.seed_admin_user()
