"""v4.7 Feature E — LDAP / Active Directory Provider 구현.

`ldap3` 기반 direct-bind 인증.

흐름:
  1. `verify_credentials(username, password)` — user_dn 추정 → 사용자 자격증명으로
     직접 bind 시도. bind 성공 시 attribute 조회 (mail/displayName/department/memberOf).
  2. `map_to_internal_user(info)` — OIDCProvider 와 동일 JIT provisioning 패턴.

LDAP/AD 는 OIDC/SAML 과 달리 redirect-callback 흐름이 없으므로 `authorize_url`,
`exchange_code`, `fetch_userinfo` 는 NotImplementedError 를 발생시키고,
`backend/routers/idp.py` 의 `/auth/idp/ldap/login` form endpoint 가
`verify_credentials` 를 직접 호출한다.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from core.data_lineage import lineage_values
from core.auth.idp_provider import IdPProvider, IdPUserInfo, InternalUser

logger = logging.getLogger(__name__)


class LDAPProvider(IdPProvider):
    """LDAP / Active Directory Identity Provider (direct-bind)."""

    name = "ldap"

    # ldap3 의 client_strategy 를 외부에서 override 할 수 있도록 — 테스트에서 MOCK_SYNC 주입.
    # None 인 경우 ldap3 기본 (SYNC) 사용.
    _client_strategy: Any = None

    # MOCK_SYNC 테스트용 — Connection 생성 직후 mock entry 를 prepopulate 한다.
    _mock_entries: Optional[dict[str, dict[str, Any]]] = None

    def __init__(
        self,
        server_url: str,
        bind_dn: str = "",
        bind_password: str = "",
        user_base_dn: str = "",
        group_base_dn: str = "",
        user_filter: str = "(uid={username})",
        attributes: Optional[list[str]] = None,
    ) -> None:
        self.server_url = (server_url or "").strip()
        self.bind_dn = (bind_dn or "").strip()
        self.bind_password = bind_password or ""
        self.user_base_dn = (user_base_dn or "").strip()
        self.group_base_dn = (group_base_dn or "").strip()
        self.user_filter = user_filter or "(uid={username})"
        self.attributes = attributes or [
            "mail",
            "displayName",
            "department",
            "memberOf",
        ]

    # ── 비-LDAP 흐름은 미지원 ──────────────────────────────────────

    async def authorize_url(self, state: str, redirect_uri: str) -> str:
        raise NotImplementedError("LDAP 은 direct-bind, redirect 없음")

    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        raise NotImplementedError("LDAP 은 direct-bind, redirect 없음")

    async def fetch_userinfo(self, tokens: dict[str, Any]) -> IdPUserInfo:
        raise NotImplementedError("LDAP 은 direct-bind, redirect 없음")

    # ── direct-bind 인증 ──────────────────────────────────────────

    def _build_user_dn(self, username: str) -> str:
        """user_filter 와 user_base_dn 으로 user_dn 을 조립.

        예: user_filter='(uid={username})', user_base_dn='ou=people,dc=ajin,dc=co,dc=kr'
            → 'uid=alice,ou=people,dc=ajin,dc=co,dc=kr'
        """
        # `(uid={username})` 같은 filter 에서 RDN 부분만 추출
        filt = self.user_filter.format(username=username)
        rdn = filt.strip("()")  # `uid=alice`
        if self.user_base_dn:
            return f"{rdn},{self.user_base_dn}"
        return rdn

    def _create_connection(self, user_dn: str, password: str):
        """ldap3 Connection 생성 — strategy 가 주입되어 있으면 사용."""
        from ldap3 import Connection, Server

        server = Server(self.server_url, get_info=None)
        kwargs: dict[str, Any] = {
            "user": user_dn,
            "password": password,
            "auto_bind": False,
        }
        if self._client_strategy is not None:
            kwargs["client_strategy"] = self._client_strategy
        conn = Connection(server, **kwargs)
        # MOCK_SYNC 인 경우 prepopulate
        if self._mock_entries:
            for dn, attrs in self._mock_entries.items():
                try:
                    conn.strategy.add_entry(dn, attrs)
                except Exception:  # 이미 있을 수 있음
                    pass
        return conn

    async def verify_credentials(
        self, username: str, password: str
    ) -> Optional[IdPUserInfo]:
        """user_dn 으로 직접 bind → 성공 시 IdPUserInfo, 실패 시 None."""
        if not username or not password:
            return None
        user_dn = self._build_user_dn(username)
        try:
            conn = self._create_connection(user_dn, password)
            ok = conn.bind()
            if not ok:
                logger.info("LDAP bind 실패: %s (result=%s)", user_dn, conn.result)
                return None

            # attribute 조회 — 자기 자신 entry
            from ldap3 import BASE

            conn.search(
                search_base=user_dn,
                search_filter="(objectClass=*)",
                search_scope=BASE,
                attributes=self.attributes,
            )
            entry_attrs: dict[str, Any] = {}
            if conn.entries:
                entry = conn.entries[0]
                for attr in self.attributes:
                    if attr in entry:
                        entry_attrs[attr] = entry[attr].value

            email = self._first_string(entry_attrs.get("mail", "") or "").lower()
            display_name = self._first_string(entry_attrs.get("displayName", "") or "")
            department = self._first_string(entry_attrs.get("department", "") or "")
            member_of = entry_attrs.get("memberOf", []) or []
            if isinstance(member_of, str):
                member_of = [member_of]

            conn.unbind()

            return IdPUserInfo(
                subject=user_dn,
                email=email,
                name=display_name or username,
                department=department,
                groups=list(member_of),
                raw_claims={
                    "dn": user_dn,
                    "username": username,
                    "attributes": entry_attrs,
                },
            )
        except Exception as e:
            # ldap3 는 잘못된 자격증명에 LDAPBindError 또는 LDAPInvalidCredentialsResult 를 raise 함
            logger.info("LDAP verify_credentials 실패 (%s): %s", user_dn, e)
            return None

    @staticmethod
    def _first_string(value: Any) -> str:
        """ldap3 attribute value 는 단일 값 또는 리스트일 수 있음 — 첫 문자열을 추출."""
        if value is None:
            return ""
        if isinstance(value, (list, tuple)):
            return str(value[0]) if value else ""
        return str(value)

    # ── JIT provisioning (OIDCProvider 패턴 재사용) ────────────────

    async def map_to_internal_user(self, info: IdPUserInfo) -> InternalUser:
        """LDAP 사용자 → 내부 사용자 (JIT provisioning).

        OIDCProvider 와 동일한 매핑 룰을 따른다:
          1. info.email 로 employee_id 결정 (employees.db / auth.db / local-part 패턴)
          2. auth.db users 에 없으면 INSERT (role=EMPLOYEE, password_hash='!LDAP!')
        """
        from core.auth.database import get_auth_db

        if not info.email:
            # LDAP 은 username 그 자체로도 매핑 시도 — subject (user_dn) 에서 RDN 추출
            raise ValueError("LDAP: mail attribute 누락 — JIT provisioning 불가")

        employee_id = self._resolve_employee_id(info.email)
        if not employee_id:
            raise ValueError(f"LDAP 사용자 매핑 실패 — 사내 직원 아님: {info.email}")

        conn = get_auth_db()
        try:
            lineage = lineage_values("real", "idp_ldap", "LDAP JIT provisioning")
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
                        "!LDAP!",
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
        """OIDCProvider._resolve_employee_id 와 동일 로직 재사용."""
        if not email:
            return None
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

        local = email.split("@", 1)[0]
        if local and "-" in local and len(local) <= 20:
            return local.upper()

        return None
