"""Feature E IdP-first authentication policy tests."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers import auth as auth_router
from core.auth import database as auth_database
from core.auth.password import hash_password
from core.auth.session_store import reset_session_store_for_tests


def _use_tmp_auth_db(monkeypatch, tmp_path: Path) -> None:
    """Initialize an isolated auth DB for auth-policy tests.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary test directory.
    """

    monkeypatch.setattr(auth_database, "AUTH_DB_PATH", tmp_path / "auth.db")
    monkeypatch.delenv("APP_DB_BACKEND", raising=False)
    monkeypatch.delenv("AUTH_BACKEND", raising=False)
    monkeypatch.delenv("AUTH_PRIMARY_PROVIDER", raising=False)
    monkeypatch.setenv("SESSION_STORE", "memory")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    reset_session_store_for_tests()
    auth_database.init_auth_db()


def _insert_user(
    *,
    employee_id: str,
    password: str = "CurrentPass!234",
    role_name: str = "EMPLOYEE",
    source_system: str = "admin_ui",
    totp_enabled: int = 0,
) -> None:
    """Insert one auth user with lineage and role metadata."""

    conn = auth_database.get_auth_db()
    role = conn.execute("SELECT role_id FROM roles WHERE role_name = ?", (role_name,)).fetchone()
    conn.execute(
        """INSERT INTO users
             (employee_id, username, password_hash, role_id, is_active, must_change_pw,
              source_system, source_label, data_class, totp_enabled)
           VALUES (?, ?, ?, ?, 1, 0, ?, ?, ?, ?)""",
        (
            employee_id,
            f"{employee_id} 사용자",
            hash_password(password),
            role["role_id"],
            source_system,
            source_system,
            "system" if source_system == "bootstrap_admin" else "real",
            totp_enabled,
        ),
    )
    conn.commit()
    conn.close()


def _client() -> TestClient:
    """Create a minimal auth router client."""

    app = FastAPI()
    app.include_router(auth_router.router, prefix="/api")
    return TestClient(app, raise_server_exceptions=False)


def test_production_idp_mode_blocks_normal_local_password_login(monkeypatch, tmp_path) -> None:
    """Production defaults to IdP-first and rejects normal password login."""

    _use_tmp_auth_db(monkeypatch, tmp_path)
    monkeypatch.setenv("APP_ENV", "production")
    _insert_user(employee_id="E001")

    response = _client().post(
        "/api/auth/login",
        json={"employee_id": "E001", "password": "CurrentPass!234"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "local_login_disabled"

    conn = auth_database.get_auth_db()
    row = conn.execute(
        "SELECT action, success FROM login_history WHERE employee_id='E001'"
    ).fetchone()
    conn.close()
    assert row["action"] == "login_policy_block"
    assert row["success"] == 0


def test_break_glass_local_login_requires_2fa_in_idp_mode(monkeypatch, tmp_path) -> None:
    """Bootstrap SYS_ADMIN local login is blocked until TOTP is enabled."""

    _use_tmp_auth_db(monkeypatch, tmp_path)
    monkeypatch.setenv("APP_ENV", "production")
    _insert_user(employee_id="admin", role_name="SYS_ADMIN", source_system="bootstrap_admin")

    response = _client().post(
        "/api/auth/login",
        json={"employee_id": "admin", "password": "CurrentPass!234"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "break_glass_2fa_required"


def test_break_glass_with_2fa_gets_mid_token_not_session(monkeypatch, tmp_path) -> None:
    """Bootstrap SYS_ADMIN with TOTP enabled reaches the existing 2FA challenge."""

    _use_tmp_auth_db(monkeypatch, tmp_path)
    monkeypatch.setenv("APP_ENV", "production")
    _insert_user(
        employee_id="admin",
        role_name="SYS_ADMIN",
        source_system="bootstrap_admin",
        totp_enabled=1,
    )

    response = _client().post(
        "/api/auth/login",
        json={"employee_id": "admin", "password": "CurrentPass!234"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["require_2fa"] is True
    assert body["mid_token"]
    assert not response.headers.get_list("set-cookie")


def test_seed_test_users_requires_explicit_non_production_flag(monkeypatch, tmp_path) -> None:
    """Synthetic test accounts are not seeded by default or in production."""

    _use_tmp_auth_db(monkeypatch, tmp_path)

    try:
        auth_database.seed_test_users()
    except RuntimeError as exc:
        assert "AUTH_SEED_TEST_USERS=true" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("seed_test_users should fail closed by default")

    monkeypatch.setenv("AUTH_SEED_TEST_USERS", "true")
    monkeypatch.setenv("APP_ENV", "production")
    try:
        auth_database.seed_test_users()
    except RuntimeError as exc:
        assert "synthetic auth users are blocked" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("seed_test_users should fail closed in production")
