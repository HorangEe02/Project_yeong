"""v4.7 Feature E — LDAPProvider 단위 테스트.

`ldap3.MOCK_SYNC` strategy 로 실 LDAP 서버 없이 bind/search 동작을 검증한다.
"""

from __future__ import annotations

import pytest
from ldap3 import MOCK_SYNC

from core.auth.idp_ldap import LDAPProvider
from core.auth.idp_provider import IdPUserInfo, get_idp_provider


# ── 공통 mock LDAP entry 시드 ────────────────────────────────────

_USER_DN = "uid=jpark,ou=people,dc=ajin,dc=co,dc=kr"
_USER_ATTRS = {
    "objectClass": ["inetOrgPerson", "top"],
    "uid": "jpark",
    "mail": "jpark@ajin.co.kr",
    "displayName": "박준영",
    "department": "품질팀",
    "memberOf": ["cn=TeamLead,ou=groups,dc=ajin,dc=co,dc=kr"],
    "userPassword": "correct_pw",
}


def _make_ldap(mock_entries: dict | None = None) -> LDAPProvider:
    p = LDAPProvider(
        server_url="ldap://fake.ajin.local:389",
        bind_dn="cn=admin,dc=ajin,dc=co,dc=kr",
        bind_password="admin-pw",
        user_base_dn="ou=people,dc=ajin,dc=co,dc=kr",
        group_base_dn="ou=groups,dc=ajin,dc=co,dc=kr",
        user_filter="(uid={username})",
    )
    p._client_strategy = MOCK_SYNC
    p._mock_entries = mock_entries if mock_entries is not None else {_USER_DN: dict(_USER_ATTRS)}
    return p


# ── 1) 기본 메타 ──────────────────────────────────────────────────


def test_provider_name():
    p = _make_ldap()
    assert p.name == "ldap"


def test_build_user_dn_with_uid_filter():
    p = _make_ldap()
    assert p._build_user_dn("alice") == "uid=alice,ou=people,dc=ajin,dc=co,dc=kr"


# ── 2) redirect 흐름 NotImplementedError ─────────────────────────


@pytest.mark.asyncio
async def test_authorize_url_raises():
    p = _make_ldap()
    with pytest.raises(NotImplementedError):
        await p.authorize_url(state="s", redirect_uri="r")


@pytest.mark.asyncio
async def test_exchange_code_raises():
    p = _make_ldap()
    with pytest.raises(NotImplementedError):
        await p.exchange_code(code="c", redirect_uri="r")


@pytest.mark.asyncio
async def test_fetch_userinfo_raises():
    p = _make_ldap()
    with pytest.raises(NotImplementedError):
        await p.fetch_userinfo({})


# ── 3) verify_credentials — direct bind ──────────────────────────


@pytest.mark.asyncio
async def test_verify_credentials_success_extracts_attributes():
    p = _make_ldap()
    info = await p.verify_credentials("jpark", "correct_pw")

    assert info is not None
    assert isinstance(info, IdPUserInfo)
    assert info.subject == _USER_DN
    assert info.email == "jpark@ajin.co.kr"
    assert info.name == "박준영"
    assert info.department == "품질팀"
    # memberOf 그룹 매핑 (test_groups_from_memberof 겸용)
    assert "cn=TeamLead,ou=groups,dc=ajin,dc=co,dc=kr" in info.groups


@pytest.mark.asyncio
async def test_verify_credentials_invalid_password():
    p = _make_ldap()
    info = await p.verify_credentials("jpark", "WRONG")
    assert info is None


@pytest.mark.asyncio
async def test_verify_credentials_unknown_user():
    p = _make_ldap()
    info = await p.verify_credentials("ghost", "anything")
    assert info is None


@pytest.mark.asyncio
async def test_verify_credentials_empty_inputs():
    p = _make_ldap()
    assert await p.verify_credentials("", "pw") is None
    assert await p.verify_credentials("jpark", "") is None


# ── 4) JIT provisioning (auth.db 격리) ───────────────────────────


@pytest.mark.asyncio
async def test_map_to_internal_user_jit_insert(tmp_path, monkeypatch):
    """기존 사용자 없음 → JIT INSERT 후 EMPLOYEE 권한 부여."""
    monkeypatch.setattr(
        "core.auth.database.AUTH_DB_PATH", tmp_path / "auth.db", raising=False
    )
    from core.auth import database as _db

    monkeypatch.setattr(_db, "AUTH_DB_PATH", tmp_path / "auth.db", raising=False)
    _db.init_auth_db()

    p = _make_ldap()
    # email local-part 'new-9999' → employee_id 'NEW-9999' (OIDC 와 동일 패턴)
    info = IdPUserInfo(
        subject="uid=new9999,ou=people,dc=ajin,dc=co,dc=kr",
        email="new-9999@ajin.co.kr",
        name="신규LDAP사용자",
        department="신설팀",
        groups=["cn=Staff,ou=groups,dc=ajin,dc=co,dc=kr"],
    )
    internal = await p.map_to_internal_user(info)

    assert internal.employee_id == "NEW-9999"
    assert internal.role_name == "EMPLOYEE"
    assert internal.username == "신규LDAP사용자"
    assert internal.is_active is True
    conn = _db.get_auth_db()
    try:
        row = conn.execute(
            "SELECT data_class, source_system FROM users WHERE employee_id='NEW-9999'"
        ).fetchone()
    finally:
        conn.close()
    assert row["data_class"] == "real"
    assert row["source_system"] == "idp_ldap"


# ── 5) factory ───────────────────────────────────────────────────


def test_factory_returns_ldap_when_env_set(monkeypatch):
    monkeypatch.setenv("IDP_PROVIDER", "ldap")
    monkeypatch.setenv("LDAP_SERVER_URL", "ldap://x.ajin.local")
    monkeypatch.setenv("LDAP_USER_BASE_DN", "ou=people,dc=ajin,dc=co,dc=kr")
    p = get_idp_provider()
    assert p is not None
    assert p.name == "ldap"
    assert isinstance(p, LDAPProvider)


def test_factory_returns_none_when_idp_disabled(monkeypatch):
    monkeypatch.setenv("IDP_PROVIDER", "disabled")
    assert get_idp_provider() is None
