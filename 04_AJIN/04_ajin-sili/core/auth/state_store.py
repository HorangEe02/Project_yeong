"""v4.7 Feature E — OAuth state CSRF 방어 저장소.

OIDC/OAuth2 흐름에서 IdP 로 redirect 하기 전 state 토큰을 생성하고,
callback 시점에 매칭/소비한다.

요구사항:
  - TTL 10분 (사용자가 IdP 로그인 페이지에서 머무는 최대 시간)
  - 1회 소비 (consume after match — replay 방지)
  - backend = `SESSION_STORE` env (`redis` | `memory`)

Cloud Run 멀티 인스턴스 환경에선 Redis 필수 (메모리 백엔드는 dev 전용).
"""

from __future__ import annotations

import os
import secrets
import time
from abc import ABC, abstractmethod
from threading import Lock
from typing import Any


STATE_TTL_SECONDS = 600  # 10분
STATE_PREFIX = "ajin:idp:state:"


class StateStore(ABC):
    """OAuth state 저장소 추상."""

    @abstractmethod
    def issue(self, payload: dict[str, Any] | None = None) -> str:
        """새 state 토큰을 생성·저장하고 반환."""
        raise NotImplementedError

    @abstractmethod
    def consume(self, state: str) -> dict[str, Any] | None:
        """state 를 1회 소비. 유효하면 payload, 없거나 만료면 None."""
        raise NotImplementedError


class MemoryStateStore(StateStore):
    """In-memory TTL 맵. 단일 프로세스/dev 전용 — Cloud Run 멀티 인스턴스 부적합."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, dict[str, Any]]] = {}
        self._lock = Lock()

    def issue(self, payload: dict[str, Any] | None = None) -> str:
        token = secrets.token_urlsafe(32)
        expires = time.time() + STATE_TTL_SECONDS
        with self._lock:
            self._store[token] = (expires, payload or {})
            self._gc()
        return token

    def consume(self, state: str) -> dict[str, Any] | None:
        if not state:
            return None
        with self._lock:
            entry = self._store.pop(state, None)
            if not entry:
                return None
            expires, payload = entry
            if time.time() > expires:
                return None
            return payload

    def _gc(self) -> None:
        """만료된 토큰 정리 (호출자가 lock 보유 중)."""
        now = time.time()
        expired = [k for k, (exp, _) in self._store.items() if now > exp]
        for k in expired:
            self._store.pop(k, None)


class RedisStateStore(StateStore):
    """Redis 기반 TTL 저장소 — 운영 환경 (Cloud Run + Memorystore)."""

    def __init__(self, redis_url: str | None = None) -> None:
        import redis  # type: ignore  # noqa: F401

        url = redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        import redis as _redis  # type: ignore

        self._r = _redis.from_url(url, decode_responses=True)

    def issue(self, payload: dict[str, Any] | None = None) -> str:
        import json

        token = secrets.token_urlsafe(32)
        key = f"{STATE_PREFIX}{token}"
        self._r.setex(key, STATE_TTL_SECONDS, json.dumps(payload or {}))
        return token

    def consume(self, state: str) -> dict[str, Any] | None:
        import json

        if not state:
            return None
        key = f"{STATE_PREFIX}{state}"
        # GETDEL 으로 atomic 1회 소비 (Redis 6.2+)
        try:
            raw = self._r.getdel(key)  # type: ignore[attr-defined]
        except Exception:
            # 구버전 fallback
            raw = self._r.get(key)
            if raw:
                self._r.delete(key)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None


_state_store: StateStore | None = None


def get_state_store() -> StateStore:
    """싱글톤 state store. `SESSION_STORE=redis` → RedisStateStore, 그 외 → MemoryStateStore.

    Redis 구성 실패 시 silent fallback 하지 않는다 — 운영자가 설정 의도를
    그대로 신뢰할 수 있도록 fail-loud (ImportError/ConnectionError 그대로 전파).
    """
    global _state_store
    if _state_store is not None:
        return _state_store
    backend = os.environ.get("SESSION_STORE", "memory").strip().lower()
    if backend == "redis":
        _state_store = RedisStateStore()
    else:
        _state_store = MemoryStateStore()
    return _state_store


def reset_state_store_for_tests() -> None:
    """테스트 격리용 — 모듈 싱글톤 초기화."""
    global _state_store
    _state_store = None
