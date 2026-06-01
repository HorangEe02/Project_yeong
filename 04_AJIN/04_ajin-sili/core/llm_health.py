"""Circuit Breaker 기반 프로바이더 헬스 레지스트리.

CLOSED → OPEN 전환: threshold (기본 3) 회 연속 실패.
OPEN → HALF_OPEN 전환: recovery_sec (기본 60s) 경과 후 다음 is_available() 호출 시.
HALF_OPEN → CLOSED 전환: record_success 시.
HALF_OPEN → OPEN 재진입: record_failure 시.

인증 실패 (HTTP 401) 는 1회만으로도 즉시 OPEN — 키 잘못된 채 폴백을 도배하지 않게 한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from time import monotonic
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class ProviderHealth:
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_ts: float = 0.0
    last_error_kind: str | None = None  # "auth" | "timeout" | "5xx" | "connection" | "unknown"


def _classify_error(error: BaseException) -> str:
    """예외 → 에러 카테고리. httpx 와 core.llm_types 의존성을 lazy import 로 분리."""
    try:
        import httpx
    except ImportError:
        httpx = None  # type: ignore[assignment]

    if httpx is not None:
        if isinstance(error, httpx.HTTPStatusError):
            status = getattr(error.response, "status_code", 0) if error.response else 0
            if status == 401 or status == 403:
                return "auth"
            if 500 <= status < 600:
                return "5xx"
            return "4xx"
        if isinstance(error, httpx.TimeoutException):
            return "timeout"
        if isinstance(error, httpx.ConnectError):
            return "connection"

    # core.llm_types.ProviderResponseError — 메시지 패턴으로 401/5xx 추정
    msg = str(error)
    if "401" in msg or "auth" in msg.lower() or "unauthorized" in msg.lower():
        return "auth"
    if "503" in msg or "502" in msg or "500" in msg or "504" in msg:
        return "5xx"
    if "timeout" in msg.lower():
        return "timeout"
    if "connect" in msg.lower():
        return "connection"
    return "unknown"


class HealthRegistry:
    """프로바이더별 Circuit Breaker 상태 머신."""

    def __init__(self, threshold: int = 3, recovery_sec: int = 60) -> None:
        self._states: dict[str, ProviderHealth] = {}
        self.threshold = threshold
        self.recovery_sec = recovery_sec

    def _ensure(self, provider: str) -> ProviderHealth:
        h = self._states.get(provider)
        if h is None:
            h = ProviderHealth()
            self._states[provider] = h
        return h

    def is_available(self, provider: str) -> bool:
        h = self._ensure(provider)
        if h.state is CircuitState.CLOSED:
            return True
        if h.state is CircuitState.OPEN:
            # 60초 경과 시 HALF_OPEN 으로 전이 — 한 번 더 호출 허용
            if monotonic() - h.last_failure_ts >= self.recovery_sec:
                h.state = CircuitState.HALF_OPEN
                return True
            return False
        # HALF_OPEN: 다시 한 번 시도 허용
        return True

    def record_success(self, provider: str) -> None:
        h = self._ensure(provider)
        h.state = CircuitState.CLOSED
        h.failure_count = 0
        h.last_error_kind = None

    def record_failure(self, provider: str, error: BaseException) -> None:
        h = self._ensure(provider)
        kind = _classify_error(error)
        h.last_error_kind = kind
        h.last_failure_ts = monotonic()

        # 인증 실패는 1회 즉시 OPEN
        if kind == "auth":
            h.failure_count = max(h.failure_count, self.threshold)
            h.state = CircuitState.OPEN
            return

        # HALF_OPEN 상태에서 실패하면 즉시 OPEN 으로 복귀
        if h.state is CircuitState.HALF_OPEN:
            h.state = CircuitState.OPEN
            return

        h.failure_count += 1
        if h.failure_count >= self.threshold:
            h.state = CircuitState.OPEN

    def reset(self, provider: str) -> None:
        """수동 리셋 (디버그/관리자용)."""
        if provider in self._states:
            self._states[provider] = ProviderHealth()

    def snapshot(self) -> dict[str, dict[str, object]]:
        """모니터링/디버그용 상태 dump."""
        return {
            p: {
                "state": h.state.value,
                "failure_count": h.failure_count,
                "last_error_kind": h.last_error_kind,
            }
            for p, h in self._states.items()
        }
