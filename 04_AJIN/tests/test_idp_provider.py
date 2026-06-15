"""v4.7 Feature E Phase 1 — OIDCProvider 단위 테스트.

mock 된 discovery / token / userinfo endpoint 로 5 시나리오 검증.
authlib JWT 서명 검증 대신 fetch_userinfo 의 userinfo endpoint 폴백 경로를 사용해
mock issuer 없이도 흐름을 검증한다.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from core.auth.idp_provider import IdPUserInfo, get_idp_provider
from core.auth.idp_oidc import OIDCProvider
from core.auth.state_store import (
    MemoryStateStore,
    RedisStateStore,  # noqa: F401  (import 가능성만 검증)
    get_state_store,
    reset_state_store_for_tests,
)


_DISCOVERY = {
    "issuer": "https://idp.example.com",
    "authorization_endpoint": "https://idp.example.com/auth",
    "token_endpoint": "https://idp.example.com/token",
    "userinfo_endpoint": "https://idp.example.com/userinfo",
    "jwks_uri": "https://idp.example.com/jwks",
}


def _make_oidc() -> OIDCProvider:
    p = OIDCProvider(
        discovery_url="https://idp.example.com/.well-known/openid-configuration",
        client_id="ajin-app",
        client_secret="topsecret",
    )
    p._meta = _DISCOVERY  # type: ignore[assignment]
    return p


# ── 1) authorize_url ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_authorize_url_includes_state_and_redirect():
    p = _make_oidc()
    url = await p.authorize_url(state="abc123", redirect_uri="https://ajin.local/cb")

    assert url.startswith("https://idp.example.com/auth?")
    assert "client_id=ajin-app" in url
    assert "state=abc123" in url
    assert "redirect_uri=https%3A%2F%2Fajin.local%2Fcb" in url
    assert "scope=openid+email+profile" in url
    assert "response_type=code" in url


# ── 2) exchange_code (httpx mock) ─────────────────────────────────


@pytest.mark.asyncio
async def test_exchange_code_posts_to_token_endpoint():
    p = _make_oidc()

    class _MockResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"access_token": "at", "id_token": "it", "token_type": "Bearer"}

    class _MockClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def post(self, url, data=None):
            assert url == "https://idp.example.com/token"
            assert data["grant_type"] == "authorization_code"
            assert data["code"] == "the-code"
            return _MockResp()

    with patch("httpx.AsyncClient", _MockClient):
        tokens = await p.exchange_code(code="the-code", redirect_uri="https://ajin.local/cb")

    assert tokens["access_token"] == "at"
    assert tokens["id_token"] == "it"


# ── 3) fetch_userinfo via userinfo endpoint (id_token 검증 skip) ──


@pytest.mark.asyncio
async def test_fetch_userinfo_uses_userinfo_endpoint_when_id_token_invalid():
    p = _make_oidc()

    class _MockResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {
                "sub": "idp-uid-42",
                "email": "Strong.User@AJIN.co.kr",
                "name": "강사용",
                "department": "IT전략팀",
                "groups": ["it", "all"],
            }

    class _MockClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, url, headers=None):
            assert url == "https://idp.example.com/userinfo"
            assert headers["Authorization"] == "Bearer at"
            return _MockResp()

    # id_token 디코드는 의도적으로 fail → userinfo endpoint 폴백 경로 검증
    with patch("httpx.AsyncClient", _MockClient), \
         patch.object(p, "_verify_id_token", AsyncMock(side_effect=ValueError("no jwks"))):
        info = await p.fetch_userinfo({"access_token": "at", "id_token": "invalid.token"})

    assert isinstance(info, IdPUserInfo)
    assert info.subject == "idp-uid-42"
    assert info.email == "strong.user@ajin.co.kr"
    assert info.name == "강사용"
    assert info.department == "IT전략팀"
    assert info.groups == ["it", "all"]


# ── 4) map_to_internal_user — JIT provisioning ────────────────────


@pytest.mark.asyncio
async def test_map_to_internal_user_jit_insert(tmp_path, monkeypatch):
    """기존 사용자 없음 → JIT INSERT 후 EMPLOYEE 권한 부여."""
    # auth.db 를 임시 경로로 격리
    monkeypatch.setattr(
        "core.auth.database.AUTH_DB_PATH",
        tmp_path / "auth.db",
        raising=False,
    )
    # idp_oidc 안에서 다시 import 되므로 module-level 도 patch
    from core.auth import database as _db

    monkeypatch.setattr(_db, "AUTH_DB_PATH", tmp_path / "auth.db", raising=False)
    _db.init_auth_db()

    p = _make_oidc()
    # email 로 employee_id 결정 — local part 가 사번 패턴 (NEW-9999)
    info = IdPUserInfo(
        subject="idp-uid-99",
        email="new-9999@ajin.co.kr",
        name="신규사용자",
        department="신설팀",
    )

    internal = await p.map_to_internal_user(info)
    assert internal.employee_id == "NEW-9999"
    assert internal.role_name == "EMPLOYEE"
    assert internal.username == "신규사용자"
    assert internal.is_active is True
    conn = _db.get_auth_db()
    try:
        row = conn.execute(
            "SELECT data_class, source_system FROM users WHERE employee_id='NEW-9999'"
        ).fetchone()
    finally:
        conn.close()
    assert row["data_class"] == "real"
    assert row["source_system"] == "idp_oidc"


@pytest.mark.asyncio
async def test_map_to_internal_user_existing_user(tmp_path, monkeypatch):
    """기존 사용자 있음 → INSERT skip + 기존 role 그대로."""
    monkeypatch.setattr("core.auth.database.AUTH_DB_PATH", tmp_path / "auth.db", raising=False)
    from core.auth import database as _db

    monkeypatch.setattr(_db, "AUTH_DB_PATH", tmp_path / "auth.db", raising=False)
    _db.init_auth_db()

    # 기존 사용자 시드 (TEAM_LEAD)
    conn = _db.get_auth_db()
    role = conn.execute("SELECT role_id FROM roles WHERE role_name='TEAM_LEAD'").fetchone()
    conn.execute(
        """INSERT INTO users
           (employee_id, username, password_hash, role_id, is_active, must_change_pw, email)
           VALUES ('IT-0001','김민수','!OIDC!',?,1,0,'kim.minsoo@ajin.co.kr')""",
        (role["role_id"],),
    )
    conn.commit()
    conn.close()

    p = _make_oidc()
    info = IdPUserInfo(
        subject="idp-uid-1",
        email="kim.minsoo@ajin.co.kr",
        name="김민수(IdP)",
    )
    internal = await p.map_to_internal_user(info)
    assert internal.employee_id == "IT-0001"
    assert internal.role_name == "TEAM_LEAD"
    # 기존 username 보존 — IdP 가 사용자명을 덮지 않음
    assert internal.username == "김민수"


@pytest.mark.asyncio
async def test_map_to_internal_user_unknown_email(tmp_path, monkeypatch):
    """매핑 불가 이메일 → ValueError."""
    monkeypatch.setattr("core.auth.database.AUTH_DB_PATH", tmp_path / "auth.db", raising=False)
    from core.auth import database as _db

    monkeypatch.setattr(_db, "AUTH_DB_PATH", tmp_path / "auth.db", raising=False)
    _db.init_auth_db()

    p = _make_oidc()
    info = IdPUserInfo(subject="x", email="randomstranger@example.com", name="외부인")
    with pytest.raises(ValueError, match="사내 직원"):
        await p.map_to_internal_user(info)


# ── 5) get_idp_provider 팩토리 / state store ─────────────────────


def test_get_idp_provider_disabled(monkeypatch):
    monkeypatch.setenv("IDP_PROVIDER", "disabled")
    assert get_idp_provider() is None


def test_get_idp_provider_oidc(monkeypatch):
    monkeypatch.setenv("IDP_PROVIDER", "oidc")
    p = get_idp_provider()
    assert p is not None
    assert p.name == "oidc"


def test_state_store_memory_issue_consume(monkeypatch):
    monkeypatch.setenv("SESSION_STORE", "memory")
    reset_state_store_for_tests()
    store = get_state_store()
    assert isinstance(store, MemoryStateStore)

    token = store.issue({"provider": "oidc", "next_url": "/admin"})
    # 1회 소비
    payload = store.consume(token)
    assert payload == {"provider": "oidc", "next_url": "/admin"}
    # 재사용 차단
    assert store.consume(token) is None
    # 빈/위조 토큰
    assert store.consume("") is None
    assert store.consume("garbage") is None
