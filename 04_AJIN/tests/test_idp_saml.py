"""v4.7 Feature E PR-E3 — SAMLProvider 단위 테스트.

onelogin.saml2 호출을 monkeypatch 로 mock — 실 IdP 서버 불필요.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.auth.idp_saml import SAMLProvider, _extract_host, _pick_attr, _pick_attr_list
from core.auth.idp_provider import IdPUserInfo, get_idp_provider


# ── 공통 픽스처 ──────────────────────────────────────────────────────


def _make_saml(**kwargs) -> SAMLProvider:
    defaults = dict(
        idp_metadata_url="https://idp.example.com/saml/metadata",
        sp_entity_id="https://ajin.local/saml",
        sp_acs_url="https://ajin.local/api/auth/idp/saml/acs",
        x509_cert_path="",
    )
    defaults.update(kwargs)
    return SAMLProvider(**defaults)


# ── 1) 기본 메타 ──────────────────────────────────────────────────────


def test_provider_name():
    p = _make_saml()
    assert p.name == "saml"


def test_extract_host_https():
    assert _extract_host("https://ajin.local/path") == "ajin.local"


def test_extract_host_empty_returns_localhost():
    assert _extract_host("") == "localhost"


# ── 2) authorize_url — AuthnRequest 생성 ─────────────────────────────


@pytest.mark.asyncio
async def test_authorize_url_generates_authn_request(monkeypatch):
    """_load_idp_metadata + OneLogin_Saml2_Auth.login() 을 mock."""
    p = _make_saml()

    fake_meta = {
        "idp": {
            "entityId": "https://idp.example.com",
            "singleSignOnService": {
                "url": "https://idp.example.com/sso",
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "x509cert": "FAKECERT",
        }
    }
    monkeypatch.setattr(p, "_load_idp_metadata", lambda: fake_meta)

    mock_auth = MagicMock()
    mock_auth.login.return_value = "https://idp.example.com/sso?SAMLRequest=encoded&RelayState=mystate"

    with patch("core.auth.idp_saml.OneLogin_Saml2_Auth", return_value=mock_auth, create=True):
        # onelogin import 경로를 직접 patch
        with patch.dict("sys.modules", {
            "onelogin": MagicMock(),
            "onelogin.saml2": MagicMock(),
            "onelogin.saml2.auth": MagicMock(OneLogin_Saml2_Auth=MagicMock(return_value=mock_auth)),
        }):
            # _build_settings 도 mock 하여 import 없이 실행
            monkeypatch.setattr(p, "_build_settings", lambda: {"sp": {}, "idp": {}})
            import sys
            saml2_auth_mod = MagicMock()
            saml2_auth_mod.OneLogin_Saml2_Auth = MagicMock(return_value=mock_auth)
            sys.modules["onelogin.saml2.auth"] = saml2_auth_mod

            url = await p.authorize_url(state="mystate", redirect_uri="https://ajin.local/cb")

    assert "SAMLRequest" in url or url.startswith("https://")
    mock_auth.login.assert_called_once_with(return_to="mystate", stay=True)


# ── 3) attribute 매핑 헬퍼 ────────────────────────────────────────────


def test_pick_attr_exact_key():
    attrs = {"email": ["user@example.com"]}
    result = _pick_attr(attrs, ("email",))
    assert result == "user@example.com"


def test_pick_attr_urn_key():
    attrs = {"urn:oid:0.9.2342.19200300.100.1.3": ["samluser@ajin.co.kr"]}
    from core.auth.idp_saml import _EMAIL_KEYS
    result = _pick_attr(attrs, _EMAIL_KEYS)
    assert result == "samluser@ajin.co.kr"


def test_pick_attr_case_insensitive():
    attrs = {"Mail": ["mixed@ajin.co.kr"]}
    from core.auth.idp_saml import _EMAIL_KEYS
    result = _pick_attr(attrs, _EMAIL_KEYS)
    assert result == "mixed@ajin.co.kr"


def test_pick_attr_empty_attrs():
    result = _pick_attr({}, ("email",))
    assert result == ""


def test_pick_attr_list_groups():
    attrs = {"memberOf": ["cn=TeamA,ou=g,dc=x", "cn=TeamB,ou=g,dc=x"]}
    from core.auth.idp_saml import _GROUPS_KEYS
    result = _pick_attr_list(attrs, _GROUPS_KEYS)
    assert len(result) == 2
    assert "cn=TeamA,ou=g,dc=x" in result


def test_pick_attr_list_empty():
    from core.auth.idp_saml import _GROUPS_KEYS
    result = _pick_attr_list({}, _GROUPS_KEYS)
    assert result == []


# ── 4) fetch_userinfo — SAMLResponse 파싱 ────────────────────────────


@pytest.mark.asyncio
async def test_fetch_userinfo_from_mock_response(monkeypatch):
    """OneLogin_Saml2_Auth.process_response + get_attributes mock."""
    p = _make_saml()
    monkeypatch.setattr(p, "_build_settings", lambda: {"sp": {}, "idp": {}})

    mock_auth = MagicMock()
    mock_auth.get_errors.return_value = []
    mock_auth.is_authenticated.return_value = True
    mock_auth.get_nameid.return_value = "saml-user-001"
    mock_auth.get_attributes.return_value = {
        "email": ["saml.user@ajin.co.kr"],
        "displayName": ["SAML사용자"],
        "department": ["품질팀"],
        "memberOf": ["cn=QA,ou=groups,dc=ajin,dc=co,dc=kr"],
    }

    import sys
    saml2_auth_mod = MagicMock()
    saml2_auth_mod.OneLogin_Saml2_Auth = MagicMock(return_value=mock_auth)
    sys.modules["onelogin.saml2.auth"] = saml2_auth_mod

    info = await p.fetch_userinfo({"saml_response": "base64encodedSAMLResponse=="})

    assert isinstance(info, IdPUserInfo)
    assert info.subject == "saml-user-001"
    assert info.email == "saml.user@ajin.co.kr"
    assert info.name == "SAML사용자"
    assert info.department == "품질팀"
    assert "cn=QA,ou=groups,dc=ajin,dc=co,dc=kr" in info.groups


@pytest.mark.asyncio
async def test_fetch_userinfo_missing_saml_response():
    p = _make_saml()
    with pytest.raises(ValueError, match="saml_response"):
        await p.fetch_userinfo({})


@pytest.mark.asyncio
async def test_fetch_userinfo_invalid_signature_raises(monkeypatch):
    """SAML 서명 검증 실패 → ValueError."""
    p = _make_saml()
    monkeypatch.setattr(p, "_build_settings", lambda: {"sp": {}, "idp": {}})

    mock_auth = MagicMock()
    mock_auth.get_errors.return_value = ["invalid_signature"]
    mock_auth.get_last_error_reason.return_value = "Signature validation failed"
    mock_auth.is_authenticated.return_value = False

    import sys
    saml2_auth_mod = MagicMock()
    saml2_auth_mod.OneLogin_Saml2_Auth = MagicMock(return_value=mock_auth)
    sys.modules["onelogin.saml2.auth"] = saml2_auth_mod

    with pytest.raises(ValueError, match="SAML 검증 실패"):
        await p.fetch_userinfo({"saml_response": "bad=="})


# ── 5) exchange_code — passthrough ───────────────────────────────────


@pytest.mark.asyncio
async def test_exchange_code_returns_passthrough():
    p = _make_saml()
    tokens = await p.exchange_code(code="b64SAMLResponse==", redirect_uri="relaystate")
    assert tokens["saml_response"] == "b64SAMLResponse=="
    assert tokens["relay_state"] == "relaystate"


# ── 6) JIT provisioning ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_map_to_internal_user_jit_insert(tmp_path, monkeypatch):
    """새 SAML 사용자 → JIT INSERT + EMPLOYEE 권한."""
    monkeypatch.setattr(
        "core.auth.database.AUTH_DB_PATH", tmp_path / "auth.db", raising=False
    )
    from core.auth import database as _db

    monkeypatch.setattr(_db, "AUTH_DB_PATH", tmp_path / "auth.db", raising=False)
    _db.init_auth_db()

    p = _make_saml()
    info = IdPUserInfo(
        subject="saml-uid-jit",
        email="new-8888@ajin.co.kr",
        name="신규SAML사용자",
        department="신설팀",
        groups=["cn=Staff,ou=groups,dc=ajin,dc=co,dc=kr"],
    )
    internal = await p.map_to_internal_user(info)

    assert internal.employee_id == "NEW-8888"
    assert internal.role_name == "EMPLOYEE"
    assert internal.username == "신규SAML사용자"
    assert internal.is_active is True
    conn = _db.get_auth_db()
    try:
        row = conn.execute(
            "SELECT data_class, source_system FROM users WHERE employee_id='NEW-8888'"
        ).fetchone()
    finally:
        conn.close()
    assert row["data_class"] == "real"
    assert row["source_system"] == "idp_saml"


@pytest.mark.asyncio
async def test_map_to_internal_user_unknown_email_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "core.auth.database.AUTH_DB_PATH", tmp_path / "auth.db", raising=False
    )
    from core.auth import database as _db

    monkeypatch.setattr(_db, "AUTH_DB_PATH", tmp_path / "auth.db", raising=False)
    _db.init_auth_db()

    p = _make_saml()
    info = IdPUserInfo(subject="x", email="outsider@external.com", name="외부인")
    with pytest.raises(ValueError, match="사내 직원"):
        await p.map_to_internal_user(info)


@pytest.mark.asyncio
async def test_map_to_internal_user_missing_email_raises():
    p = _make_saml()
    info = IdPUserInfo(subject="x", email="", name="이메일없음")
    with pytest.raises(ValueError, match="email attribute"):
        await p.map_to_internal_user(info)


# ── 7) factory ───────────────────────────────────────────────────────


def test_factory_returns_saml_when_env_set(monkeypatch):
    monkeypatch.setenv("IDP_PROVIDER", "saml")
    monkeypatch.setenv("SAML_IDP_METADATA_URL", "https://idp.example.com/saml/metadata")
    monkeypatch.setenv("SAML_SP_ENTITY_ID", "https://ajin.local/saml")
    monkeypatch.setenv("SAML_SP_ACS_URL", "https://ajin.local/api/auth/idp/saml/acs")
    p = get_idp_provider()
    assert p is not None
    assert p.name == "saml"
    assert isinstance(p, SAMLProvider)


def test_factory_returns_none_when_idp_disabled(monkeypatch):
    monkeypatch.setenv("IDP_PROVIDER", "disabled")
    assert get_idp_provider() is None
