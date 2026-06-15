"""v4.7 Feature E — OIDC (OpenID Connect) Provider 구현.

authlib `AsyncOAuth2Client` 기반. discovery URL 로 endpoint/JWK 자동 로드.

지원 IdP: Keycloak, Okta, Azure AD, Google Workspace 등 OIDC 표준 호환 IdP.

JIT provisioning:
  1. IdP id_token / userinfo → email/sub 추출
  2. employees.db 에 email 매칭되는 직원 검색 → employee_id 결정
  3. auth.db users 에 없으면 INSERT (role=EMPLOYEE 기본), 있으면 SKIP
  4. mint_from_idp → 백엔드 JWT 발급
"""

from __future__ import annotations

import logging
import os
from typing import Any

from core.data_lineage import lineage_values
from core.auth.idp_provider import IdPProvider, IdPUserInfo, InternalUser

logger = logging.getLogger(__name__)


class OIDCProvider(IdPProvider):
    """OIDC 표준 흐름. discovery URL → endpoint + JWK 자동 발견."""

    name = "oidc"

    def __init__(
        self,
        discovery_url: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> None:
        self.discovery_url = (discovery_url or os.environ.get("OIDC_DISCOVERY_URL", "")).strip()
        self.client_id = (client_id or os.environ.get("OIDC_CLIENT_ID", "")).strip()
        self.client_secret = (client_secret or os.environ.get("OIDC_CLIENT_SECRET", "")).strip()
        self._meta: dict[str, Any] | None = None
        self._jwks: dict[str, Any] | None = None

    def _require_config(self) -> None:
        if not self.discovery_url or not self.client_id:
            raise ValueError(
                "OIDC 설정 누락: OIDC_DISCOVERY_URL 와 OIDC_CLIENT_ID 가 필요합니다."
            )

    async def _discover(self) -> dict[str, Any]:
        """OIDC discovery 문서를 lazy load (메모이즈)."""
        if self._meta is not None:
            return self._meta
        self._require_config()
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(self.discovery_url)
            resp.raise_for_status()
            self._meta = resp.json()
        return self._meta

    async def _get_jwks(self) -> dict[str, Any]:
        """JWK 세트 lazy load — id_token 서명 검증용."""
        if self._jwks is not None:
            return self._jwks
        meta = await self._discover()
        jwks_uri = meta.get("jwks_uri")
        if not jwks_uri:
            raise ValueError("OIDC discovery 에 jwks_uri 누락")
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(jwks_uri)
            resp.raise_for_status()
            self._jwks = resp.json()
        return self._jwks

    async def authorize_url(self, state: str, redirect_uri: str) -> str:
        """authorization endpoint + query 조립."""
        meta = await self._discover()
        endpoint = meta.get("authorization_endpoint")
        if not endpoint:
            raise ValueError("OIDC discovery 에 authorization_endpoint 누락")
        from urllib.parse import urlencode

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": "openid email profile",
            "state": state,
        }
        return f"{endpoint}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        """authorization code → tokens (RFC 6749 §4.1.3)."""
        meta = await self._discover()
        token_endpoint = meta.get("token_endpoint")
        if not token_endpoint:
            raise ValueError("OIDC discovery 에 token_endpoint 누락")
        import httpx

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(token_endpoint, data=data)
            resp.raise_for_status()
            return resp.json()

    async def fetch_userinfo(self, tokens: dict[str, Any]) -> IdPUserInfo:
        """id_token 디코드 + userinfo endpoint 호출 → IdPUserInfo 정규화."""
        id_token = tokens.get("id_token", "")
        access_token = tokens.get("access_token", "")

        claims: dict[str, Any] = {}
        # 1) id_token 우선 — 서명 검증 후 claim 추출
        if id_token:
            try:
                claims = await self._verify_id_token(id_token)
            except Exception as e:
                logger.warning("OIDC id_token 검증 실패 — userinfo endpoint 폴백 시도: %s", e)
                claims = {}

        # 2) userinfo endpoint 보강 (id_token 누락된 field 채움)
        if access_token:
            try:
                userinfo = await self._fetch_userinfo_endpoint(access_token)
                # id_token claim 우선, userinfo 는 보강
                for k, v in userinfo.items():
                    claims.setdefault(k, v)
            except Exception as e:
                logger.warning("OIDC userinfo endpoint 호출 실패: %s", e)

        if not claims:
            raise ValueError("OIDC: id_token / userinfo 모두 사용 불가")

        return IdPUserInfo(
            subject=str(claims.get("sub", "")),
            email=str(claims.get("email", "") or "").lower(),
            name=str(claims.get("name", "") or claims.get("preferred_username", "")),
            department=str(claims.get("department", "") or ""),
            groups=list(claims.get("groups", []) or []),
            raw_claims=claims,
        )

    async def _verify_id_token(self, id_token: str) -> dict[str, Any]:
        """JWK 로 id_token 서명을 검증하고 claim 을 반환."""
        from authlib.jose import JsonWebToken  # type: ignore

        meta = await self._discover()
        jwks = await self._get_jwks()
        issuer = meta.get("issuer", "")

        jwt = JsonWebToken(["RS256", "ES256", "HS256"])
        claims = jwt.decode(
            id_token,
            jwks,
            claims_options={
                "iss": {"essential": True, "value": issuer} if issuer else {"essential": False},
                "aud": {"essential": True, "value": self.client_id},
            },
        )
        claims.validate()
        return dict(claims)

    async def _fetch_userinfo_endpoint(self, access_token: str) -> dict[str, Any]:
        meta = await self._discover()
        endpoint = meta.get("userinfo_endpoint")
        if not endpoint:
            return {}
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(endpoint, headers={"Authorization": f"Bearer {access_token}"})
            resp.raise_for_status()
            return resp.json()

    async def map_to_internal_user(self, info: IdPUserInfo) -> InternalUser:
        """IdP 사용자 → 내부 사용자 (JIT provisioning).

        매핑 룰:
          1. info.email 로 employees.db 직원 검색 → employee_id 결정
          2. auth.db users 에 없으면 INSERT (role=EMPLOYEE, password_hash='!OIDC!')
          3. 이미 있으면 username/department 만 sync
        """
        from core.auth.database import get_auth_db

        if not info.email:
            raise ValueError("OIDC: email claim 누락 — JIT provisioning 불가")

        employee_id = self._resolve_employee_id(info.email)
        if not employee_id:
            raise ValueError(f"OIDC 사용자 매핑 실패 — 사내 직원 아님: {info.email}")

        conn = get_auth_db()
        try:
            lineage = lineage_values("real", "idp_oidc", "OIDC JIT provisioning")
            row = conn.execute(
                """SELECT u.*, r.role_name, r.role_level
                   FROM users u JOIN roles r ON u.role_id = r.role_id
                   WHERE u.employee_id = ?""",
                (employee_id,),
            ).fetchone()

            if not row:
                # JIT INSERT — EMPLOYEE role, 비밀번호 사용 불가 placeholder
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
                        "!OIDC!",  # password 로그인 차단 placeholder
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

    @staticmethod
    def _resolve_employee_id(email: str) -> str | None:
        """employees.db 또는 auth.db.users.email 로 employee_id 역추적.

        우선순위:
          1. employees.db employees 테이블에서 email 매칭 → employee_id
          2. auth.db users.email 매칭 → employee_id
          3. email local part 가 사번 패턴이면 그대로 사용 (e.g. it-0001@ajin.co.kr → IT-0001)
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
        except Exception as e:  # employees.db 없거나 schema 미스
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
