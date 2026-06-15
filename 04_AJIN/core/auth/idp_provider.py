"""v4.7 Feature E — 외부 IdP 추상화 레이어.

OIDC / SAML / future IdP 공통 인터페이스. 백엔드 핵심 로직은
provider-agnostic 으로 유지되며, provider 변경은 env (`IDP_PROVIDER`) 만 바꿔도
무영향 회귀를 보장한다.

흐름:
  1. `authorize_url(state, redirect_uri)` → IdP 로그인 페이지 redirect URL
  2. (사용자 IdP 인증 후 callback) `exchange_code(code, redirect_uri)` → tokens
  3. `fetch_userinfo(tokens)` → IdPUserInfo (정규화된 사용자 프로필)
  4. `map_to_internal_user(info)` → 내부 employee_id + role JIT provisioning
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from pydantic import BaseModel, Field


class IdPUserInfo(BaseModel):
    """IdP 사용자 정보 — provider-agnostic 정규화 모델."""

    subject: str  # IdP 고유 식별자 (OIDC `sub`, SAML `NameID`)
    email: str = ""
    name: str = ""
    department: str = ""
    groups: list[str] = Field(default_factory=list)
    raw_claims: dict[str, Any] = Field(default_factory=dict)


class InternalUser(BaseModel):
    """내부 시스템 사용자 — JIT 매핑 결과."""

    employee_id: str
    username: str
    role_name: str
    role_level: int
    department: str = ""
    is_active: bool = True


class IdPProvider(ABC):
    """외부 IdP 공통 인터페이스."""

    name: str = "abstract"

    @abstractmethod
    async def authorize_url(self, state: str, redirect_uri: str) -> str:
        """IdP 로그인 페이지 URL 을 생성한다."""
        raise NotImplementedError

    @abstractmethod
    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        """authorization code → tokens (access_token, id_token, refresh_token...)."""
        raise NotImplementedError

    @abstractmethod
    async def fetch_userinfo(self, tokens: dict[str, Any]) -> IdPUserInfo:
        """tokens → IdPUserInfo (정규화)."""
        raise NotImplementedError

    @abstractmethod
    async def map_to_internal_user(self, info: IdPUserInfo) -> InternalUser:
        """IdP 사용자 → 내부 사용자.

        JIT provisioning: employees.db 조회 → users 테이블 INSERT (이미 있으면 SKIP).
        매핑 실패 시 ValueError raise.
        """
        raise NotImplementedError

    async def verify_credentials(
        self, username: str, password: str
    ) -> Optional[IdPUserInfo]:
        """Direct-bind 방식 (LDAP/AD). OIDC/SAML provider 는 NotImplementedError.

        반환값:
          - 인증 성공: IdPUserInfo
          - 인증 실패 (잘못된 자격증명): None
        """
        raise NotImplementedError(
            f"{self.name} provider 는 direct-bind 미지원 (OIDC/SAML callback flow 사용)"
        )


def get_idp_provider(name: str | None = None) -> IdPProvider | None:
    """IdP provider 팩토리.

    Args:
        name: provider 명. None 이면 env `IDP_PROVIDER` 사용. `disabled` 또는 미지원 시 None.

    Returns:
        IdPProvider 인스턴스 또는 None.
    """
    import os

    pname = (name or os.environ.get("IDP_PROVIDER", "disabled")).strip().lower()
    if pname in ("", "disabled", "none"):
        return None

    if pname == "oidc":
        from core.auth.idp_oidc import OIDCProvider
        return OIDCProvider()
    if pname == "saml":
        from core.auth.idp_saml import SAMLProvider
        return SAMLProvider()
    if pname == "ldap":
        from core.auth.idp_ldap import LDAPProvider
        return LDAPProvider(
            server_url=os.environ["LDAP_SERVER_URL"],
            bind_dn=os.environ.get("LDAP_BIND_DN", ""),
            bind_password=os.environ.get("LDAP_BIND_PASSWORD", ""),
            user_base_dn=os.environ["LDAP_USER_BASE_DN"],
            group_base_dn=os.environ.get("LDAP_GROUP_BASE_DN", ""),
            user_filter=os.environ.get("LDAP_USER_FILTER", "(uid={username})"),
        )

    return None
