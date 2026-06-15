"""v4.7 Feature E PR-E3 — SAML 2.0 Provider 활성화 구현.

`python3-saml` (OneLogin SAML toolkit) 기반. IdP metadata URL 에서 endpoint/
인증서를 자동 발견하고, SP 측은 env (`SAML_SP_ENTITY_ID`, `SAML_SP_ACS_URL`,
`SAML_X509_CERT_PATH`) 로 설정한다.

지원 IdP: Okta, Azure AD, ADFS, Keycloak, OneLogin 등 SAML 2.0 표준 호환 IdP.

흐름:
  1. `authorize_url(state, redirect_uri)` → SAML AuthnRequest 생성 (HTTP-Redirect binding)
  2. (사용자 IdP 인증 후 POST callback) `/auth/idp/saml/acs` 에서 SAMLResponse 수신
  3. `exchange_code(saml_response_b64, ...)` → SAMLResponse 검증 + assertion 추출
  4. `fetch_userinfo(tokens)` → SAML attributes → IdPUserInfo
  5. `map_to_internal_user(info)` → OIDC 와 동일한 JIT provisioning 패턴

표준 attribute 매핑:
  - email: `urn:oid:0.9.2342.19200300.100.1.3` | `mail` | `email`
  - name : `urn:oid:2.5.4.42` | `givenName` | `displayName`
  - department: `department` | `urn:oid:2.5.4.11`
  - groups: `memberOf` | `http://schemas.xmlsoap.org/claims/Group` | `groups`
"""

from __future__ import annotations

import logging
import os
from typing import Any
from urllib.parse import urlencode

from core.data_lineage import lineage_values
from core.auth.idp_provider import IdPProvider, IdPUserInfo, InternalUser

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# 표준 SAML attribute 별칭 (대소문자/별칭 모두 수용)
# ─────────────────────────────────────────────────────────────────────
_EMAIL_KEYS = (
    "urn:oid:0.9.2342.19200300.100.1.3",
    "mail",
    "email",
    "emailaddress",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
)
_NAME_KEYS = (
    "urn:oid:2.5.4.42",
    "givenName",
    "displayName",
    "name",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
)
_DEPARTMENT_KEYS = (
    "department",
    "urn:oid:2.5.4.11",
    "ou",
)
_GROUPS_KEYS = (
    "memberOf",
    "http://schemas.xmlsoap.org/claims/Group",
    "groups",
    "http://schemas.microsoft.com/ws/2008/06/identity/claims/groups",
)


def _pick_attr(attrs: dict[str, Any], keys: tuple[str, ...]) -> str:
    """SAML attributes dict 에서 첫 매칭 키의 값(스칼라)을 반환."""
    if not attrs:
        return ""
    # python3-saml 은 attribute 를 list[str] 으로 돌려준다. 대소문자도 흔히 갈리므로
    # 1차로 정확 매칭, 2차로 lower-case 비교.
    lowered = {k.lower(): k for k in attrs.keys()}
    for k in keys:
        if k in attrs:
            v = attrs[k]
            return v[0] if isinstance(v, list) and v else (v or "")
        lk = k.lower()
        if lk in lowered:
            v = attrs[lowered[lk]]
            return v[0] if isinstance(v, list) and v else (v or "")
    return ""


def _pick_attr_list(attrs: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    """SAML attributes 중 list 값 (예: groups/memberOf) 을 추출."""
    if not attrs:
        return []
    lowered = {k.lower(): k for k in attrs.keys()}
    for k in keys:
        target = None
        if k in attrs:
            target = attrs[k]
        elif k.lower() in lowered:
            target = attrs[lowered[k.lower()]]
        if target is None:
            continue
        if isinstance(target, list):
            return [str(x) for x in target if x]
        return [str(target)]
    return []


class SAMLProvider(IdPProvider):
    """SAML 2.0 Identity Provider — python3-saml 기반."""

    name = "saml"

    def __init__(
        self,
        idp_metadata_url: str | None = None,
        sp_entity_id: str | None = None,
        sp_acs_url: str | None = None,
        x509_cert_path: str | None = None,
    ) -> None:
        self.idp_metadata_url = (
            idp_metadata_url or os.environ.get("SAML_IDP_METADATA_URL", "")
        ).strip()
        self.sp_entity_id = (
            sp_entity_id or os.environ.get("SAML_SP_ENTITY_ID", "")
        ).strip()
        self.sp_acs_url = (
            sp_acs_url or os.environ.get("SAML_SP_ACS_URL", "")
        ).strip()
        self.x509_cert_path = (
            x509_cert_path or os.environ.get("SAML_X509_CERT_PATH", "")
        ).strip()
        # IdP metadata cache (lazy)
        self._idp_meta: dict[str, Any] | None = None

    def _require_config(self) -> None:
        if not self.idp_metadata_url or not self.sp_entity_id or not self.sp_acs_url:
            raise ValueError(
                "SAML 설정 누락: SAML_IDP_METADATA_URL / SAML_SP_ENTITY_ID / "
                "SAML_SP_ACS_URL 가 모두 필요합니다."
            )

    def _load_idp_metadata(self) -> dict[str, Any]:
        """IdP metadata URL → dict (parsed). 캐시 메모이즈."""
        if self._idp_meta is not None:
            return self._idp_meta
        self._require_config()
        from onelogin.saml2.idp_metadata_parser import OneLogin_Saml2_IdPMetadataParser

        try:
            self._idp_meta = OneLogin_Saml2_IdPMetadataParser.parse_remote(
                self.idp_metadata_url, timeout=10
            )
        except Exception as e:
            raise ValueError(f"SAML IdP metadata 로드 실패: {e}") from e
        return self._idp_meta

    def _build_settings(self) -> dict[str, Any]:
        """python3-saml settings dict 빌드 (IdP metadata + SP env)."""
        meta = self._load_idp_metadata()
        idp_section = meta.get("idp", {}) if isinstance(meta, dict) else {}

        sp_x509_cert = ""
        sp_private_key = ""
        if self.x509_cert_path:
            try:
                with open(self.x509_cert_path, "r", encoding="utf-8") as fh:
                    sp_x509_cert = fh.read()
            except Exception as e:  # pragma: no cover
                logger.warning("SAML SP cert 로드 실패: %s", e)

        return {
            "strict": True,
            "debug": False,
            "sp": {
                "entityId": self.sp_entity_id,
                "assertionConsumerService": {
                    "url": self.sp_acs_url,
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
                },
                "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
                "x509cert": sp_x509_cert,
                "privateKey": sp_private_key,
            },
            "idp": idp_section,
        }

    # ──────────────────────────────────────────────────────────────
    # IdPProvider interface
    # ──────────────────────────────────────────────────────────────

    async def authorize_url(self, state: str, redirect_uri: str) -> str:
        """SAML AuthnRequest 생성 → HTTP-Redirect binding URL.

        Args:
            state: RelayState 로 IdP 에 전달 (callback 시 그대로 반환됨).
            redirect_uri: 본 구현에서는 SP_ACS_URL 이 metadata 에 고정되므로 미사용.
        """
        from onelogin.saml2.auth import OneLogin_Saml2_Auth

        settings = self._build_settings()
        # OneLogin_Saml2_Auth 는 request_data dict 를 받지만, login() 호출 시 SSO URL
        # 만 필요. 최소 더미 request_data 로 충분.
        request_data = {
            "https": "on" if self.sp_acs_url.startswith("https") else "off",
            "http_host": _extract_host(self.sp_acs_url),
            "server_port": "443" if self.sp_acs_url.startswith("https") else "80",
            "script_name": "/api/auth/idp/saml/acs",
            "get_data": {},
            "post_data": {},
        }
        auth = OneLogin_Saml2_Auth(request_data, old_settings=settings)
        # `return_to` 가 RelayState 로 전달된다.
        url = auth.login(return_to=state, stay=True)
        return url

    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        """SAML 의 ``code`` 는 base64 SAMLResponse (POST binding 으로 수신).

        Returns: ``{"saml_response": <b64>, "relay_state": <state>}`` (token dict 모사).
        실제 attribute 추출은 fetch_userinfo 에서 수행.
        """
        return {"saml_response": code, "relay_state": redirect_uri or ""}

    async def fetch_userinfo(self, tokens: dict[str, Any]) -> IdPUserInfo:
        """SAMLResponse 검증 + assertion attributes → IdPUserInfo 정규화."""
        from onelogin.saml2.auth import OneLogin_Saml2_Auth

        saml_response = tokens.get("saml_response", "")
        if not saml_response:
            raise ValueError("SAML: saml_response 누락")

        settings = self._build_settings()
        request_data = {
            "https": "on" if self.sp_acs_url.startswith("https") else "off",
            "http_host": _extract_host(self.sp_acs_url),
            "server_port": "443" if self.sp_acs_url.startswith("https") else "80",
            "script_name": "/api/auth/idp/saml/acs",
            "get_data": {},
            "post_data": {"SAMLResponse": saml_response},
        }
        auth = OneLogin_Saml2_Auth(request_data, old_settings=settings)
        try:
            auth.process_response()
        except Exception as e:
            raise ValueError(f"SAML 응답 처리 실패: {e}") from e

        errors = auth.get_errors()
        if errors:
            reason = auth.get_last_error_reason() or ",".join(errors)
            raise ValueError(f"SAML 검증 실패: {reason}")
        if not auth.is_authenticated():
            raise ValueError("SAML 미인증 응답")

        attrs = auth.get_attributes() or {}
        nameid = auth.get_nameid() or ""

        email = _pick_attr(attrs, _EMAIL_KEYS) or nameid
        name = _pick_attr(attrs, _NAME_KEYS)
        department = _pick_attr(attrs, _DEPARTMENT_KEYS)
        groups = _pick_attr_list(attrs, _GROUPS_KEYS)

        return IdPUserInfo(
            subject=str(nameid or email),
            email=str(email or "").lower(),
            name=str(name or ""),
            department=str(department or ""),
            groups=groups,
            raw_claims={"attributes": attrs, "nameid": nameid},
        )

    async def map_to_internal_user(self, info: IdPUserInfo) -> InternalUser:
        """SAML 사용자 → 내부 사용자 (JIT provisioning).

        OIDC 와 동일한 매핑 룰:
          1. info.email 로 employees.db 직원 검색 → employee_id 결정
          2. auth.db users 에 없으면 INSERT (role=EMPLOYEE, password='!SAML!')
          3. 이미 있으면 SKIP (기존 role/username 보존)
        """
        from core.auth.database import get_auth_db

        if not info.email:
            raise ValueError("SAML: email attribute 누락 — JIT provisioning 불가")

        employee_id = _resolve_employee_id(info.email)
        if not employee_id:
            raise ValueError(f"SAML 사용자 매핑 실패 — 사내 직원 아님: {info.email}")

        conn = get_auth_db()
        try:
            lineage = lineage_values("real", "idp_saml", "SAML JIT provisioning")
            row = conn.execute(
                """SELECT u.*, r.role_name, r.role_level
                   FROM users u JOIN roles r ON u.role_id = r.role_id
                   WHERE u.employee_id = ?""",
                (employee_id,),
            ).fetchone()

            if not row:
                role = conn.execute(
                    "SELECT role_id, role_level FROM roles WHERE role_name = 'EMPLOYEE'"
                ).fetchone()
                if not role:
                    raise ValueError("auth.db: EMPLOYEE 역할 누락")
                conn.execute(
                    """INSERT INTO users
                       (employee_id, username, password_hash, role_id, is_active, must_change_pw,
                        email, department, data_class, source_system, source_label, source_updated_at)
                       VALUES (?, ?, ?, ?, 1, 0, ?, ?, ?, ?, ?, ?)""",
                    (
                        employee_id,
                        info.name or employee_id,
                        "!SAML!",
                        role["role_id"],
                        info.email,
                        info.department,
                        lineage["data_class"],
                        lineage["source_system"],
                        lineage["source_label"],
                        lineage["source_updated_at"],
                    ),
                )
                conn.commit()
                row = conn.execute(
                    """SELECT u.*, r.role_name, r.role_level
                       FROM users u JOIN roles r ON u.role_id = r.role_id
                       WHERE u.employee_id = ?""",
                    (employee_id,),
                ).fetchone()
            else:
                conn.execute(
                    """UPDATE users
                          SET email = COALESCE(NULLIF(?, ''), email),
                              department = COALESCE(NULLIF(?, ''), department),
                              data_class = ?,
                              source_system = ?,
                              source_label = ?,
                              source_updated_at = ?,
                              updated_at = datetime('now')
                        WHERE employee_id = ?""",
                    (
                        info.email,
                        info.department,
                        lineage["data_class"],
                        lineage["source_system"],
                        lineage["source_label"],
                        lineage["source_updated_at"],
                        employee_id,
                    ),
                )
                conn.commit()

            if not row or not row["is_active"]:
                raise ValueError(f"비활성 계정: {employee_id}")

            return InternalUser(
                employee_id=row["employee_id"],
                username=row["username"],
                role_name=row["role_name"],
                role_level=int(row["role_level"]),
                department=(row["department"] or "") if "department" in row.keys() else "",
                is_active=bool(row["is_active"]),
            )
        finally:
            conn.close()


# ─────────────────────────────────────────────────────────────────────
# 헬퍼
# ─────────────────────────────────────────────────────────────────────


def _extract_host(url: str) -> str:
    """URL → host (port 포함). e.g. https://ajin.local/x → ajin.local"""
    if not url:
        return "localhost"
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return parsed.netloc or "localhost"


def _resolve_employee_id(email: str) -> str | None:
    """OIDC 와 동일한 employee_id 역추적 (employees.db → auth.db → email local pattern).

    OIDCProvider._resolve_employee_id 와 동일 로직 — provider 공통 유틸.
    """
    if not email:
        return None
    # 1) employees.db
    try:
        from features.search.employee.database import EmployeeDatabase

        db = EmployeeDatabase()
        row = db.conn.execute(
            "SELECT employee_id FROM employees WHERE LOWER(email) = ?",
            (email.lower(),),
        ).fetchone()
        if row:
            return row[0] if not isinstance(row, dict) else row.get("employee_id")
    except Exception as e:
        logger.debug("employees.db email 조회 실패: %s", e)

    # 2) auth.db users.email
    try:
        from core.auth.database import get_auth_db

        conn = get_auth_db()
        try:
            row = conn.execute(
                "SELECT employee_id FROM users WHERE LOWER(email) = ?",
                (email.lower(),),
            ).fetchone()
            if row:
                return row["employee_id"]
        finally:
            conn.close()
    except Exception as e:
        logger.debug("auth.db email 조회 실패: %s", e)

    # 3) email local part 가 사번 패턴
    local = email.split("@", 1)[0]
    if local and "-" in local and len(local) <= 20:
        return local.upper()

    return None
