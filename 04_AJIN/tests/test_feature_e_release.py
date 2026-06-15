"""Feature E release hardening verifier and cookie auth tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import Response

import scripts.verify_feature_e_release as verifier
from backend.csrf_middleware import CookieCSRFMiddleware
from backend.routers import auth as auth_router
from backend.routers import idp as idp_router
from core.auth import database as auth_database
from core.auth.password import hash_password
from core.auth.session_store import reset_session_store_for_tests


def _use_tmp_auth_db(monkeypatch, tmp_path: Path) -> None:
    """Initialize a temporary auth DB for router tests."""

    monkeypatch.setattr(auth_database, "AUTH_DB_PATH", tmp_path / "auth.db")
    monkeypatch.setenv("SESSION_STORE", "memory")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    monkeypatch.delenv("ALLOW_BEARER_AUTH", raising=False)
    reset_session_store_for_tests()
    auth_database.init_auth_db()


def _insert_user(employee_id: str = "E001", password: str = "CurrentPass!234") -> None:
    """Insert an active employee test user."""

    conn = auth_database.get_auth_db()
    role = conn.execute("SELECT role_id FROM roles WHERE role_name = 'EMPLOYEE'").fetchone()
    conn.execute(
        """INSERT INTO users
             (employee_id, username, password_hash, role_id, is_active, must_change_pw)
           VALUES (?, ?, ?, ?, 1, 0)""",
        (employee_id, "테스트사용자", hash_password(password), role["role_id"]),
    )
    conn.commit()
    conn.close()


def _client() -> TestClient:
    """Create a minimal app with auth router and CSRF middleware."""

    app = FastAPI()
    app.add_middleware(CookieCSRFMiddleware)
    app.include_router(auth_router.router, prefix="/api")
    return TestClient(app, raise_server_exceptions=False)


def _idp_client() -> TestClient:
    """Create a minimal app for IdP callback and LDAP route tests."""

    app = FastAPI()
    app.add_middleware(CookieCSRFMiddleware)
    app.include_router(idp_router.router, prefix="/api/auth/idp")
    return TestClient(app, raise_server_exceptions=False)


def _csrf(client: TestClient) -> str:
    token = client.cookies.get("ajin_csrf")
    assert token
    return token


def test_endpoint_surface_passes_current_openapi() -> None:
    """Current OpenAPI should expose the expected Feature E surface."""

    result = verifier.verify_endpoint_surface(verifier.FeatureEConfig())

    assert result.status == "pass"
    assert result.details["counts"] == {
        "auth": 12,
        "idp": 5,
        "admin": 48,
        "admin-scenarios": 9,
    }


def test_cookie_attributes_are_release_safe_in_production(monkeypatch) -> None:
    """Cookie helper should emit the expected attributes in production."""

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("AUTH_COOKIE_SECURE", raising=False)

    from core.auth.cookies import set_auth_cookies

    response = Response()
    set_auth_cookies(response, "access.jwt", "refresh.jwt")
    cookies = response.headers.getlist("set-cookie")

    access = next(value for value in cookies if value.startswith("ajin_access="))
    refresh = next(value for value in cookies if value.startswith("ajin_refresh="))
    csrf = next(value for value in cookies if value.startswith("ajin_csrf="))

    assert "HttpOnly" in access
    assert "HttpOnly" in refresh
    assert "HttpOnly" not in csrf
    assert "Secure" in access and "Secure" in refresh and "Secure" in csrf
    assert "SameSite=lax" in access
    assert "Path=/api;" in access
    assert "Path=/api/auth;" in refresh
    assert "Path=/;" in csrf


def test_frontend_token_posture_passes_current_sources() -> None:
    """Frontend should not persist access/refresh tokens or parse token query params."""

    result = verifier.verify_frontend_token_posture(verifier.FeatureEConfig())

    assert result.status == "pass"


def test_production_environment_gate_fails_without_secret_and_redis(monkeypatch) -> None:
    """Production release must have explicit JWT secret and Redis session store."""

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("AJIN_JWT_SECRET", raising=False)
    monkeypatch.setenv("SESSION_STORE", "memory")
    monkeypatch.delenv("REDIS_URL", raising=False)

    result = verifier.verify_production_environment_gate(verifier.FeatureEConfig())

    assert result.status == "fail"
    assert "AJIN_JWT_SECRET_missing_or_too_short" in result.details["blockers"]
    assert "SESSION_STORE_must_be_redis" in result.details["blockers"]
    assert "REDIS_URL_missing" in result.details["blockers"]


def test_default_account_gate_blocks_active_demo_in_production(tmp_path, monkeypatch) -> None:
    """Active default/demo accounts are production blockers."""

    db_path = tmp_path / "auth.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE users (employee_id TEXT, username TEXT, is_active INTEGER)")
    conn.execute("INSERT INTO users VALUES ('SYS-0001', 'demo sys', 1)")
    conn.commit()
    conn.close()
    monkeypatch.setenv("APP_ENV", "production")

    result = verifier.verify_default_account_gate(verifier.FeatureEConfig(auth_db_path=db_path))

    assert result.status == "fail"
    assert result.details["active_default_or_demo_accounts"] == ["SYS-0001"]


def test_login_sets_httponly_cookies_without_token_body(monkeypatch, tmp_path) -> None:
    """Password login should set cookies and avoid token values in JSON body."""

    _use_tmp_auth_db(monkeypatch, tmp_path)
    _insert_user()
    client = _client()

    response = client.post(
        "/api/auth/login",
        json={"employee_id": "E001", "password": "CurrentPass!234"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "access_token" not in body
    assert "refresh_token" not in body
    assert body["token_type"] == "cookie"
    cookies = response.headers.get_list("set-cookie")
    assert any(value.startswith("ajin_access=") and "HttpOnly" in value for value in cookies)
    assert any(value.startswith("ajin_refresh=") and "HttpOnly" in value for value in cookies)
    assert any(value.startswith("ajin_csrf=") and "HttpOnly" not in value for value in cookies)

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["employee_id"] == "E001"


def test_two_factor_verify_sets_cookies_without_token_body(monkeypatch, tmp_path) -> None:
    """2FA final verification should issue cookies, not token body fields."""

    from cryptography.fernet import Fernet
    import pyotp
    from features.admin import totp

    _use_tmp_auth_db(monkeypatch, tmp_path)
    monkeypatch.setenv("TOTP_SECRET_FERNET_KEY", Fernet.generate_key().decode())
    _insert_user()
    enroll = totp.enroll_user("E001")
    assert totp.confirm_enrollment("E001", pyotp.TOTP(enroll["secret_b32"]).now()) is True

    client = _client()
    login = client.post(
        "/api/auth/login",
        json={"employee_id": "E001", "password": "CurrentPass!234"},
    )
    assert login.status_code == 200
    assert login.json()["require_2fa"] is True
    assert "access_token" not in login.json()
    assert not login.headers.get_list("set-cookie")

    verify = client.post(
        "/api/auth/2fa/verify",
        json={
            "mid_token": login.json()["mid_token"],
            "code": pyotp.TOTP(enroll["secret_b32"]).now(),
        },
    )
    assert verify.status_code == 200
    assert "access_token" not in verify.json()
    assert "refresh_token" not in verify.json()
    assert any(value.startswith("ajin_access=") for value in verify.headers.get_list("set-cookie"))


def test_cookie_auth_unsafe_methods_require_csrf(monkeypatch, tmp_path) -> None:
    """Unsafe cookie-auth methods should require the X-CSRF-Token header."""

    _use_tmp_auth_db(monkeypatch, tmp_path)
    _insert_user()
    client = _client()
    assert client.post(
        "/api/auth/login",
        json={"employee_id": "E001", "password": "CurrentPass!234"},
    ).status_code == 200

    blocked = client.post(
        "/api/auth/change-password",
        json={"current_password": "CurrentPass!234", "new_password": "NewStrong!2345"},
    )
    allowed = client.post(
        "/api/auth/change-password",
        json={"current_password": "CurrentPass!234", "new_password": "NewStrong!2345"},
        headers={"X-CSRF-Token": _csrf(client)},
    )

    assert blocked.status_code == 403
    assert allowed.status_code == 200


def test_refresh_rotation_and_logout_revoke_cookie_session(monkeypatch, tmp_path) -> None:
    """Refresh should rotate allowlist entries and logout should revoke the session."""

    _use_tmp_auth_db(monkeypatch, tmp_path)
    _insert_user()
    client = _client()
    assert client.post(
        "/api/auth/login",
        json={"employee_id": "E001", "password": "CurrentPass!234"},
    ).status_code == 200
    old_refresh = client.cookies.get("ajin_refresh")
    old_csrf = _csrf(client)
    assert old_refresh

    refresh = client.post("/api/auth/refresh", json={}, headers={"X-CSRF-Token": old_csrf})
    assert refresh.status_code == 200
    assert "access_token" not in refresh.json()
    assert client.cookies.get("ajin_refresh") != old_refresh

    replay = _client().post(
        "/api/auth/refresh",
        headers={
            "Cookie": f"ajin_refresh={old_refresh}; ajin_csrf={old_csrf}",
            "X-CSRF-Token": old_csrf,
        },
    )
    assert replay.status_code == 401

    logout = client.post("/api/auth/logout", json={}, headers={"X-CSRF-Token": _csrf(client)})
    assert logout.status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_oidc_callback_sets_cookie_redirect_without_token_query(monkeypatch, tmp_path) -> None:
    """OIDC callback should redirect with only a non-secret IdP flag."""

    _use_tmp_auth_db(monkeypatch, tmp_path)

    class Store:
        def consume(self, state: str):
            return {"provider": "oidc", "next_url": "/"}

    class Provider:
        name = "oidc"

        async def exchange_code(self, code: str, redirect_uri: str):
            return {"id_token": "provider-token"}

        async def fetch_userinfo(self, tokens):
            return SimpleNamespace(subject="subject-1")

        async def map_to_internal_user(self, info):
            return SimpleNamespace(
                employee_id="OIDC-001",
                username="Oidc User",
                role_name="EMPLOYEE",
                role_level=1,
            )

    monkeypatch.setattr(idp_router, "_enabled_providers", lambda: ["oidc"])
    monkeypatch.setattr(idp_router, "get_state_store", lambda: Store())
    monkeypatch.setattr(idp_router, "get_idp_provider", lambda provider=None: Provider())

    response = _idp_client().get(
        "/api/auth/idp/oidc/callback?code=ok&state=state",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/?ajin_idp=oidc"
    assert "ajin_access" not in response.headers["location"]
    assert "ajin_refresh" not in response.headers["location"]
    assert any(value.startswith("ajin_access=") for value in response.headers.get_list("set-cookie"))


def test_ldap_login_sets_cookies_without_token_body(monkeypatch, tmp_path) -> None:
    """LDAP direct login should return user metadata and cookie session only."""

    _use_tmp_auth_db(monkeypatch, tmp_path)

    class Provider:
        name = "ldap"

        async def verify_credentials(self, username: str, password: str):
            return SimpleNamespace(subject=username)

        async def map_to_internal_user(self, info):
            return SimpleNamespace(
                employee_id="LDAP-001",
                username="Ldap User",
                role_name="EMPLOYEE",
                role_level=1,
            )

    monkeypatch.setattr(idp_router, "_enabled_providers", lambda: ["ldap"])
    monkeypatch.setattr(idp_router, "get_idp_provider", lambda provider=None: Provider())

    response = _idp_client().post(
        "/api/auth/idp/ldap/login",
        data={"username": "ldap.user", "password": "Password!234"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "cookie"
    assert "access_token" not in body
    assert "refresh_token" not in body
    assert any(value.startswith("ajin_access=") for value in response.headers.get_list("set-cookie"))


def test_bearer_auth_requires_explicit_allow_flag(monkeypatch, tmp_path) -> None:
    """Bearer JWTs are automation-only and require ALLOW_BEARER_AUTH=true."""

    _use_tmp_auth_db(monkeypatch, tmp_path)
    _insert_user()
    from core.auth.jwt_handler import create_access_token

    token = create_access_token("E001", "테스트사용자", "EMPLOYEE", 1)
    client = _client()
    blocked = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    monkeypatch.setenv("ALLOW_BEARER_AUTH", "true")
    allowed = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert blocked.status_code == 401
    assert allowed.status_code == 200
