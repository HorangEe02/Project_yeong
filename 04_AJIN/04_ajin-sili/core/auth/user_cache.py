"""User Cache — IdP 를 source-of-truth 로 두고 auth.db 의 user 정보를 캐시화.

설계 원칙:
  - IDP_PROVIDER=disabled (default): 캐시 비활성. 기존 users 테이블 SELECT 그대로 (역호환 보장).
  - IDP_PROVIDER=ldap/oidc/saml: TTL=1h. miss/expired 시 provider 에서 신규 fetch + cached_at 갱신.
  - fetch 실패 (network down) 시 stale 데이터를 그대로 반환 (가용성 우선).
  - 야간 reconcile job (user_cache_reconcile.py) 가 mismatch 검출.

provider API 의존성:
  - 모든 IdPProvider 는 `verify_credentials` (LDAP) 또는 redirect-callback flow (OIDC/SAML) 만 노출.
  - 비밀번호 없이 username/employee_id 로 fetch 하는 일반 API 는 현재 표준화되지 않음.
  - 따라서 본 캐시는 보수적으로 동작: provider 에 `fetch_userinfo_by_subject` 메서드가
    존재할 때만 active fetch 수행. 없으면 기존 row 반환 + cached_at 갱신 (no-op fetch).
"""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

from core.data_lineage import lineage_values
from core.auth.database import get_auth_db
from core.auth.idp_provider import IdPProvider, get_idp_provider

logger = logging.getLogger(__name__)


def _ttl_seconds() -> int:
    """매 호출마다 env 를 재평가해 테스트에서 monkeypatch 가능."""
    try:
        return int(os.environ.get("USER_CACHE_TTL_SECONDS", "3600"))
    except ValueError:
        return 3600


def _idp_enabled() -> bool:
    """IDP_PROVIDER 가 활성 상태인지 (disabled/none/빈값이면 False)."""
    pname = (os.environ.get("IDP_PROVIDER", "disabled") or "").strip().lower()
    return pname not in ("", "disabled", "none")


def _utcnow_iso() -> str:
    """ISO8601 UTC, 초 단위."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        # 'Z' 또는 '+00:00' 둘 다 허용
        if ts.endswith("Z"):
            return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(ts)
    except Exception:
        return None


class UserCache:
    """auth.users 테이블 위에 얹는 IdP 캐시 레이어."""

    def __init__(self, provider: Optional[IdPProvider] = None) -> None:
        # provider 를 명시 주입하면 그것을 우선 사용 (테스트). 아니면 env 기반 lazy lookup.
        self._explicit_provider = provider

    def _get_provider(self) -> Optional[IdPProvider]:
        if self._explicit_provider is not None:
            return self._explicit_provider
        if not _idp_enabled():
            return None
        try:
            return get_idp_provider()
        except Exception as e:
            logger.warning("user_cache: provider 초기화 실패 — %s", e)
            return None

    # ── 핵심 API ─────────────────────────────────────────────────

    def get_or_fetch(self, employee_id: str) -> Optional[dict]:
        """employee_id 로 user row 를 반환.

        IDP_PROVIDER=disabled: 캐시 무시, 기존 row 그대로 반환.
        활성: 캐시 hit (TTL 내) → 즉시 반환. miss/expired → IdP fetch 시도 + 갱신.
              fetch 실패 시 stale row 반환.
        """
        if not employee_id:
            return None

        row = self._read_row(employee_id)
        if row is None:
            return None

        if not _idp_enabled():
            # 역호환: cached_at 무시, 그대로 반환
            return row

        # IdP 활성 — TTL 검사
        if self._is_fresh_row(row):
            return row

        # miss/expired → fetch 시도
        provider = self._get_provider()
        refreshed = self._refresh_from_provider(employee_id, provider)
        if refreshed is not None:
            return refreshed

        # fetch 실패 → stale 반환 (가용성)
        logger.info(
            "user_cache: %s — fetch 실패, stale 반환 (cached_at=%s)",
            employee_id, row.get("cached_at"),
        )
        return row

    def is_fresh(self, employee_id: str) -> bool:
        """TTL 내인지 여부. IdP 비활성 시 항상 True (캐시 개념 없음)."""
        if not _idp_enabled():
            return True
        row = self._read_row(employee_id)
        if row is None:
            return False
        return self._is_fresh_row(row)

    def invalidate(self, employee_id: str) -> None:
        """단일 사용자 cached_at NULL 처리."""
        if not employee_id:
            return
        conn = get_auth_db()
        try:
            conn.execute(
                "UPDATE users SET cached_at = NULL WHERE employee_id = ?",
                (employee_id,),
            )
            conn.commit()
        finally:
            conn.close()

    def invalidate_all(self) -> None:
        """전체 사용자 cached_at NULL 처리."""
        conn = get_auth_db()
        try:
            conn.execute("UPDATE users SET cached_at = NULL")
            conn.commit()
        finally:
            conn.close()

    # ── 내부 헬퍼 ────────────────────────────────────────────────

    def _read_row(self, employee_id: str) -> Optional[dict]:
        conn = get_auth_db()
        try:
            r = conn.execute(
                """SELECT u.*, r.role_name, r.role_level
                   FROM users u JOIN roles r ON u.role_id = r.role_id
                   WHERE u.employee_id = ?""",
                (employee_id,),
            ).fetchone()
            return dict(r) if r else None
        except sqlite3.Error as e:
            logger.warning("user_cache: SELECT 실패 (%s) — %s", employee_id, e)
            return None
        finally:
            conn.close()

    def _is_fresh_row(self, row: dict) -> bool:
        cached_at = row.get("cached_at")
        if not cached_at:
            return False
        parsed = _parse_iso(cached_at)
        if parsed is None:
            return False
        age = datetime.now(timezone.utc) - parsed
        return age <= timedelta(seconds=_ttl_seconds())

    def _refresh_from_provider(
        self, employee_id: str, provider: Optional[IdPProvider]
    ) -> Optional[dict]:
        """provider 에서 사용자 정보 fetch 후 row 갱신.

        provider 가 None 이거나 fetch_userinfo_by_subject 미지원이면 None 반환.
        성공 시 갱신된 row 반환.
        """
        if provider is None:
            return None
        fetch_fn = getattr(provider, "fetch_userinfo_by_subject", None)
        if fetch_fn is None or not callable(fetch_fn):
            # provider 가 username 기반 직접 fetch 미지원 — cached_at 만 touch (best-effort)
            return None

        try:
            info = fetch_fn(employee_id)
        except Exception as e:
            logger.info("user_cache: provider fetch 실패 (%s) — %s", employee_id, e)
            return None

        if info is None:
            return None

        return self._upsert_from_idp(
            employee_id,
            info,
            provider_name=getattr(provider, "name", "idp"),
        )

    def _upsert_from_idp(
        self,
        employee_id: str,
        info,
        *,
        provider_name: str = "idp",
    ) -> Optional[dict]:
        """Reflect IdPUserInfo into users and refresh cache/source labels.

        Args:
            employee_id: Internal employee ID.
            info: IdPUserInfo or dict-compatible profile.
            provider_name: Provider name such as ``ldap``, ``oidc``, or ``saml``.

        Returns:
            Updated auth user row, or None if the row no longer exists.
        """
        # info 는 IdPUserInfo 또는 dict
        def _g(attr: str, default: str = "") -> str:
            if hasattr(info, attr):
                return getattr(info, attr) or default
            if isinstance(info, dict):
                return info.get(attr, default) or default
            return default

        email = _g("email")
        name = _g("name")
        department = _g("department")
        provider_key = (provider_name or "idp").strip().lower()
        lineage = lineage_values(
            "real",
            f"idp_{provider_key}",
            f"IdP cache refresh:{provider_key}",
        )

        conn = get_auth_db()
        try:
            updates = []
            params: list = []
            if email:
                updates.append("email = ?")
                params.append(email)
            if name:
                updates.append("username = ?")
                params.append(name)
            if department:
                updates.append("department = ?")
                params.append(department)
            updates.append("cached_at = ?")
            params.append(_utcnow_iso())
            for col in ("data_class", "source_system", "source_label", "source_updated_at"):
                updates.append(f"{col} = ?")
                params.append(lineage[col])
            params.append(employee_id)

            conn.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE employee_id = ?",
                params,
            )
            conn.commit()

            r = conn.execute(
                """SELECT u.*, r.role_name, r.role_level
                   FROM users u JOIN roles r ON u.role_id = r.role_id
                   WHERE u.employee_id = ?""",
                (employee_id,),
            ).fetchone()
            return dict(r) if r else None
        finally:
            conn.close()
