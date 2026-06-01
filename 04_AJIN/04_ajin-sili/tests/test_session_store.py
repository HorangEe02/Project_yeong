"""v4.7 Feature E Phase 3 — SessionStore + StateStore 통합 테스트.

Memory backend + Redis backend (fakeredis) 양측 검증:
  - put / get / delete
  - TTL 만료
  - issue() session_id 발급
  - get_session_store() 팩토리 분기
"""

from __future__ import annotations

import pytest


# ── 1) MemorySessionStore ─────────────────────────────────────────


def test_memory_put_get_delete(monkeypatch):
    from core.auth.session_store import MemorySessionStore, reset_session_store_for_tests

    reset_session_store_for_tests()
    store = MemorySessionStore()
    store.put("sid-1", "jwt.token.x", "EMP-1", ttl_seconds=10)
    assert store.get("sid-1") == "jwt.token.x"
    store.delete("sid-1")
    assert store.get("sid-1") is None


def test_memory_ttl_expiry(monkeypatch):
    import time

    from core.auth.session_store import MemorySessionStore

    store = MemorySessionStore()
    store.put("sid-x", "jwt.x", "EMP", ttl_seconds=1)
    assert store.get("sid-x") == "jwt.x"
    time.sleep(1.1)
    assert store.get("sid-x") is None


def test_memory_issue_returns_unique_session_id():
    from core.auth.session_store import MemorySessionStore

    store = MemorySessionStore()
    s1 = store.issue("jwt.1", "EMP-1", ttl_seconds=60)
    s2 = store.issue("jwt.2", "EMP-2", ttl_seconds=60)
    assert s1 != s2
    assert store.get(s1) == "jwt.1"
    assert store.get(s2) == "jwt.2"


# ── 2) RedisSessionStore (fakeredis 로 격리) ──────────────────────


@pytest.fixture
def fake_redis_store(monkeypatch):
    fakeredis = pytest.importorskip("fakeredis")

    from core.auth import session_store as ss

    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(
        ss.RedisSessionStore,
        "__init__",
        lambda self, redis_url=None: setattr(self, "_r", fake),
        raising=False,
    )
    return ss.RedisSessionStore()


def test_redis_put_get_delete(fake_redis_store):
    store = fake_redis_store
    store.put("sid-r1", "jwt.redis", "EMP-R1", ttl_seconds=60)
    assert store.get("sid-r1") == "jwt.redis"
    store.delete("sid-r1")
    assert store.get("sid-r1") is None


def test_redis_ttl_expiry(fake_redis_store):
    import time

    store = fake_redis_store
    store.put("sid-r2", "jwt.short", "EMP-R2", ttl_seconds=1)
    assert store.get("sid-r2") == "jwt.short"
    # fakeredis 는 실제 TTL 작동 — 1초 대기
    time.sleep(1.2)
    assert store.get("sid-r2") is None


def test_redis_key_prefix(fake_redis_store):
    from core.auth.session_store import REDIS_KEY_PREFIX

    store = fake_redis_store
    store.put("sid-pfx", "jwt.x", "EMP", ttl_seconds=60)
    # 내부 키가 prefix 포함
    assert store._r.exists(f"{REDIS_KEY_PREFIX}sid-pfx") == 1
    # 다른 prefix 의 키는 영향 X
    store._r.set("noise:key", "x")
    assert store.get("sid-pfx") == "jwt.x"


# ── 3) Factory ────────────────────────────────────────────────────


def test_factory_returns_memory_by_default(monkeypatch):
    from core.auth.session_store import (
        MemorySessionStore,
        get_session_store,
        reset_session_store_for_tests,
    )

    reset_session_store_for_tests()
    monkeypatch.setenv("SESSION_STORE", "memory")
    store = get_session_store()
    assert isinstance(store, MemorySessionStore)


def test_factory_returns_redis(monkeypatch):
    pytest.importorskip("fakeredis")
    import fakeredis

    from core.auth import session_store as ss

    ss.reset_session_store_for_tests()
    monkeypatch.setenv("SESSION_STORE", "redis")

    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(
        ss.RedisSessionStore,
        "__init__",
        lambda self, redis_url=None: setattr(self, "_r", fake),
        raising=False,
    )

    store = ss.get_session_store()
    assert isinstance(store, ss.RedisSessionStore)


# ── 4) StateStore (재확인) ────────────────────────────────────────


def test_state_store_redis_fakeredis(monkeypatch):
    pytest.importorskip("fakeredis")
    import fakeredis

    from core.auth import state_store as st

    monkeypatch.setenv("SESSION_STORE", "redis")
    st.reset_state_store_for_tests()
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(
        st.RedisStateStore,
        "__init__",
        lambda self, redis_url=None: setattr(self, "_r", fake),
        raising=False,
    )

    store = st.get_state_store()
    assert isinstance(store, st.RedisStateStore)
    token = store.issue({"provider": "oidc", "next_url": "/x"})
    p = store.consume(token)
    assert p == {"provider": "oidc", "next_url": "/x"}
    # 1회 소비
    assert store.consume(token) is None
