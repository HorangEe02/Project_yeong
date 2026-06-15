"""v4.7 PR-E2 — UserCache 단위 테스트.

- 임시 auth.db (tmp_path) 로 격리.
- IdP provider 는 stub 으로 주입.
- TTL 은 monkeypatch 로 짧게 조정.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest

import core.auth.database as db_mod
import core.auth.user_cache as uc_mod
from core.auth.idp_provider import IdPProvider, IdPUserInfo, InternalUser


# ── 픽스처 ──────────────────────────────────────────────────────


@pytest.fixture
def tmp_auth_db(tmp_path, monkeypatch):
    """tmp_path 에 빈 auth.db 를 만들고 init/seed 한다."""
    db_path = tmp_path / "auth.db"
    monkeypatch.setattr(db_mod, "AUTH_DB_PATH", db_path)
    db_mod.init_auth_db()
    # 테스트용 EMPLOYEE row 1개 직접 INSERT
    conn = db_mod.get_auth_db()
    role = conn.execute("SELECT role_id FROM roles WHERE role_name='EMPLOYEE'").fetchone()
    conn.execute(
        """INSERT INTO users
           (employee_id, username, password_hash, role_id, is_active, must_change_pw,
            email, department)
           VALUES (?, ?, ?, ?, 1, 0, ?, ?)""",
        ("E-0001", "테스트유저", "!hash!", role["role_id"],
         "old@ajin.co.kr", "품질보증팀"),
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def disable_idp(monkeypatch):
    monkeypatch.setenv("IDP_PROVIDER", "disabled")


@pytest.fixture
def enable_idp_ldap(monkeypatch):
    monkeypatch.setenv("IDP_PROVIDER", "ldap")
    monkeypatch.setenv("USER_CACHE_TTL_SECONDS", "3600")


# ── stub provider ──────────────────────────────────────────────


class _StubProvider(IdPProvider):
    """fetch_userinfo_by_subject 를 노출하는 테스트 stub."""

    name = "stub"

    def __init__(self, info: Optional[IdPUserInfo] = None, raise_exc: Optional[Exception] = None):
        self._info = info
        self._raise = raise_exc
        self.calls: list[str] = []

    async def authorize_url(self, state, redirect_uri):  # pragma: no cover
        raise NotImplementedError

    async def exchange_code(self, code, redirect_uri):  # pragma: no cover
        raise NotImplementedError

    async def fetch_userinfo(self, tokens):  # pragma: no cover
        raise NotImplementedError

    async def map_to_internal_user(self, info) -> InternalUser:  # pragma: no cover
        raise NotImplementedError

    def fetch_userinfo_by_subject(self, employee_id: str) -> Optional[IdPUserInfo]:
        self.calls.append(employee_id)
        if self._raise is not None:
            raise self._raise
        return self._info


def _mark_fresh(employee_id: str, when: Optional[datetime] = None):
    when = when or datetime.now(timezone.utc)
    ts = when.strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = db_mod.get_auth_db()
    conn.execute(
        "UPDATE users SET cached_at = ? WHERE employee_id = ?",
        (ts, employee_id),
    )
    conn.commit()
    conn.close()


# ── 테스트 ──────────────────────────────────────────────────────


def test_idp_disabled_returns_existing_row(tmp_auth_db, disable_idp):
    cache = uc_mod.UserCache()
    row = cache.get_or_fetch("E-0001")
    assert row is not None
    assert row["employee_id"] == "E-0001"
    assert row["email"] == "old@ajin.co.kr"


def test_cache_hit_within_ttl(tmp_auth_db, enable_idp_ldap):
    # cached_at 을 방금 시각으로 세팅 → fresh
    _mark_fresh("E-0001")
    stub = _StubProvider(info=IdPUserInfo(subject="X", email="new@ajin.co.kr"))
    cache = uc_mod.UserCache(provider=stub)
    row = cache.get_or_fetch("E-0001")
    assert row is not None
    # fresh 이므로 provider 호출 없음 — 기존 email 유지
    assert row["email"] == "old@ajin.co.kr"
    assert stub.calls == []


def test_cache_miss_triggers_fetch(tmp_auth_db, enable_idp_ldap):
    # cached_at NULL — miss
    stub = _StubProvider(info=IdPUserInfo(
        subject="X", email="new@ajin.co.kr", name="새이름", department="IT전략팀",
    ))
    cache = uc_mod.UserCache(provider=stub)
    row = cache.get_or_fetch("E-0001")
    assert row is not None
    assert stub.calls == ["E-0001"]
    assert row["email"] == "new@ajin.co.kr"
    assert row["username"] == "새이름"
    assert row["department"] == "IT전략팀"
    assert row["cached_at"] is not None


def test_cache_expired_triggers_refetch(tmp_auth_db, enable_idp_ldap, monkeypatch):
    # TTL = 60s, cached_at 을 2h 전으로 설정 → expired
    monkeypatch.setenv("USER_CACHE_TTL_SECONDS", "60")
    _mark_fresh("E-0001", when=datetime.now(timezone.utc) - timedelta(hours=2))
    stub = _StubProvider(info=IdPUserInfo(subject="X", email="refetched@ajin.co.kr"))
    cache = uc_mod.UserCache(provider=stub)
    row = cache.get_or_fetch("E-0001")
    assert stub.calls == ["E-0001"]
    assert row["email"] == "refetched@ajin.co.kr"


def test_invalidate_clears_cached_at(tmp_auth_db, enable_idp_ldap):
    _mark_fresh("E-0001")
    cache = uc_mod.UserCache(provider=_StubProvider())
    assert cache.is_fresh("E-0001") is True
    cache.invalidate("E-0001")
    assert cache.is_fresh("E-0001") is False


def test_invalidate_all_clears_all(tmp_auth_db, enable_idp_ldap):
    # 두 번째 사용자 추가 후 둘 다 fresh → invalidate_all → 둘 다 stale
    conn = db_mod.get_auth_db()
    role = conn.execute("SELECT role_id FROM roles WHERE role_name='EMPLOYEE'").fetchone()
    conn.execute(
        """INSERT INTO users
           (employee_id, username, password_hash, role_id, is_active, must_change_pw,
            email, department)
           VALUES (?, ?, ?, ?, 1, 0, ?, ?)""",
        ("E-0002", "두번째", "!h!", role["role_id"], "two@ajin.co.kr", "IT전략팀"),
    )
    conn.commit()
    conn.close()

    _mark_fresh("E-0001")
    _mark_fresh("E-0002")
    cache = uc_mod.UserCache(provider=_StubProvider())
    assert cache.is_fresh("E-0001") is True
    assert cache.is_fresh("E-0002") is True
    cache.invalidate_all()
    assert cache.is_fresh("E-0001") is False
    assert cache.is_fresh("E-0002") is False


def test_is_fresh_within_ttl(tmp_auth_db, enable_idp_ldap):
    _mark_fresh("E-0001")
    cache = uc_mod.UserCache(provider=_StubProvider())
    assert cache.is_fresh("E-0001") is True


def test_is_fresh_after_ttl(tmp_auth_db, enable_idp_ldap, monkeypatch):
    monkeypatch.setenv("USER_CACHE_TTL_SECONDS", "60")
    _mark_fresh("E-0001", when=datetime.now(timezone.utc) - timedelta(hours=2))
    cache = uc_mod.UserCache(provider=_StubProvider())
    assert cache.is_fresh("E-0001") is False


def test_fetch_failure_returns_stale(tmp_auth_db, enable_idp_ldap, monkeypatch):
    # expired + provider 가 예외 → stale row 반환
    monkeypatch.setenv("USER_CACHE_TTL_SECONDS", "60")
    _mark_fresh("E-0001", when=datetime.now(timezone.utc) - timedelta(hours=2))
    stub = _StubProvider(raise_exc=RuntimeError("network down"))
    cache = uc_mod.UserCache(provider=stub)
    row = cache.get_or_fetch("E-0001")
    assert row is not None
    # stub 호출됨 + 기존 email 유지 (갱신 실패)
    assert stub.calls == ["E-0001"]
    assert row["email"] == "old@ajin.co.kr"


def test_idp_disabled_is_fresh_always_true(tmp_auth_db, disable_idp):
    # IdP 비활성 시 is_fresh 는 캐시 개념 자체가 없으므로 True
    cache = uc_mod.UserCache()
    assert cache.is_fresh("E-0001") is True
    assert cache.is_fresh("nonexistent") is True


def test_get_or_fetch_unknown_returns_none(tmp_auth_db, disable_idp):
    cache = uc_mod.UserCache()
    assert cache.get_or_fetch("NOT-EXIST") is None
    assert cache.get_or_fetch("") is None


def test_provider_without_fetch_method_returns_stale(tmp_auth_db, enable_idp_ldap, monkeypatch):
    # provider 가 fetch_userinfo_by_subject 미지원 → stale row 그대로
    monkeypatch.setenv("USER_CACHE_TTL_SECONDS", "60")
    _mark_fresh("E-0001", when=datetime.now(timezone.utc) - timedelta(hours=2))

    class _Bare(IdPProvider):
        name = "bare"
        async def authorize_url(self, state, redirect_uri): raise NotImplementedError
        async def exchange_code(self, code, redirect_uri): raise NotImplementedError
        async def fetch_userinfo(self, tokens): raise NotImplementedError
        async def map_to_internal_user(self, info): raise NotImplementedError

    cache = uc_mod.UserCache(provider=_Bare())
    row = cache.get_or_fetch("E-0001")
    assert row is not None
    assert row["email"] == "old@ajin.co.kr"  # stale 그대로
